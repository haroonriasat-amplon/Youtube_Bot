from fastapi import FastAPI, Query, UploadFile, File
from youtube_transcript_api import YouTubeTranscriptApi
import openai
import numpy as np
import os
import fitz  # PyMuPDF
import chromadb
from dotenv import load_dotenv
import requests
from fastapi.middleware.cors import CORSMiddleware

# Load API key from .env
load_dotenv()
OPENAI_API_KEY = os.getenv("OPEN_AI_KEY")

# Setup OpenAI client
openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)

# Setup Chroma
chroma_client = chromadb.PersistentClient(path="./chroma-db")
yt_collection = chroma_client.get_or_create_collection("youtube_chunks")
pdf_collection = chroma_client.get_or_create_collection("pdf_pages")

# Initialize FastAPI
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Use specific domains in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# PDF URLs to index
PDF_URLS = [
    "https://amplon.io/wp-content/uploads/2025/01/Amplon-getting-started.pdf",
    "https://amplon.io/wp-content/uploads/2025/01/Amplon-Tag-groups-and-Tags.pdf",
    "https://amplon.io/wp-content/uploads/2025/01/Amplon-linking-external-documents.pdf",
    "https://amplon.io/wp-content/uploads/2025/01/Amplon-getting-your-data-to-Excel.pdf",
    "https://amplon.io/wp-content/uploads/2025/01/Amplon-planning-strategic-activities.pdf",
    "https://amplon.io/wp-content/uploads/2025/01/Amplon-execution-management-status-updates.pdf",
    "https://amplon.io/wp-content/uploads/2025/01/Amplon-alignment-builder.pdf"
]


# Helper: get embeddings
def get_embeddings(texts: list[str]) -> list[list[float]]:
    response = openai_client.embeddings.create(
        input=texts,
        model="text-embedding-3-small"
    )
    return [d.embedding for d in response.data]


# ------------------ YOUTUBE INGEST + SEARCH ------------------

def ingest_video(video_id: str):
    transcript = YouTubeTranscriptApi.get_transcript(video_id)
    texts, metadatas, ids = [], [], []
    for i, entry in enumerate(transcript):
        texts.append(entry["text"])
        metadatas.append({
            "video_id": video_id,
            "start": int(entry["start"]),
            "text": entry["text"]
        })
        ids.append(f"{video_id}_{i}")

    embeddings = get_embeddings(texts)
    yt_collection.add(documents=texts, embeddings=embeddings, metadatas=metadatas, ids=ids)


@app.get("/search")
def search_youtube(query: str, top_k: int = 3):
    query_embedding = get_embeddings([query])[0]
    results = yt_collection.query(query_embeddings=[query_embedding], n_results=top_k)

    seen = {}
    final = []
    for id_, metadata in zip(results["ids"][0], results["metadatas"][0]):
        video_id = metadata["video_id"]
        start = metadata["start"]
        if video_id not in seen or all(abs(start - s) > 10 for s in seen[video_id]):
            seen.setdefault(video_id, []).append(start)
            final.append({
                "video_id": video_id,
                "start": start,
                "text": metadata["text"],
                "link": f"https://www.youtube.com/watch?v={video_id}&t={start}s"
            })
    return {"results": final}


# ------------------ PDF INGEST + SEARCH ------------------

def extract_pdf_pages(file_path: str) -> list[dict]:
    doc = fitz.open(file_path)
    pages = []
    for i in range(len(doc)):
        text = doc[i].get_text()
        pages.append({"page": i + 1, "text": text})
    return pages


def download_pdf(url: str, save_folder: str = "uploads") -> str:
    os.makedirs(save_folder, exist_ok=True)
    filename = url.split("/")[-1]
    path = os.path.join(save_folder, filename)
    response = requests.get(url)
    with open(path, "wb") as f:
        f.write(response.content)
    return path


def ingest_remote_pdfs():
    for url in PDF_URLS:
        path = download_pdf(url)
        pages = extract_pdf_pages(path)
        texts = [p["text"] for p in pages]
        embeddings = get_embeddings(texts)
        metadatas = [{"filename": os.path.basename(path), "page": p["page"]} for p in pages]
        ids = [f"{os.path.basename(path)}_p{p['page']}" for p in pages]

        pdf_collection.add(documents=texts, embeddings=embeddings, metadatas=metadatas, ids=ids)
        print(f"Ingested {os.path.basename(path)}")


@app.post("/ingest-pdf")
async def ingest_pdf(file: UploadFile = File(...)):
    contents = await file.read()
    file_path = f"./uploads/{file.filename}"
    os.makedirs("uploads", exist_ok=True)
    with open(file_path, "wb") as f:
        f.write(contents)

    pages = extract_pdf_pages(file_path)
    texts = [p["text"] for p in pages]
    embeddings = get_embeddings(texts)
    metadatas = [{"filename": file.filename, "page": p["page"]} for p in pages]
    ids = [f"{file.filename}_p{p['page']}" for p in pages]

    pdf_collection.add(documents=texts, embeddings=embeddings, metadatas=metadatas, ids=ids)
    return {"message": f"{file.filename} indexed successfully", "pages": len(pages)}


@app.get("/search-pdf")
def search_pdf(query: str, top_k: int = 3):
    query_embedding = get_embeddings([query])[0]
    results = pdf_collection.query(query_embeddings=[query_embedding], n_results=top_k)

    final = []
    for id_, metadata in zip(results["ids"][0], results["metadatas"][0]):
        filename = metadata["filename"]
        page = metadata["page"]
        link = f"https://amplon.io/wp-content/uploads/2025/01/{filename}#page={page}"
        final.append({
            "filename": filename,
            "page": page,
            "link": link
        })
    return {"results": final}


# Ingest on startup
@app.on_event("startup")
def startup_ingest():
    ingest_video("NLg7Wa6HmYI")
    ingest_remote_pdfs()