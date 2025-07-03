from fastapi import FastAPI, Query
from youtube_transcript_api import YouTubeTranscriptApi
import openai
import numpy as np
import os

import chromadb

from dotenv import load_dotenv

# Load API key from .env
load_dotenv()
OPENAI_API_KEY = os.getenv("OPEN_AI_KEY")

# Setup OpenAI
openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)

# Setup Chroma
chroma_client = chromadb.PersistentClient(path="./chroma-db")

collection = chroma_client.get_or_create_collection("youtube_chunks")

# Initialize FastAPI
app = FastAPI()


# Helper: get embeddings
def get_embeddings(texts: list[str]) -> list[list[float]]:
    response = openai_client.embeddings.create(
        input=texts,
        model="text-embedding-3-small"
    )
    return [d.embedding for d in response.data]


# ✅ Ingest a single video (NLg7Wa6HmYI)
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
    collection.add(
        documents=texts,
        embeddings=embeddings,
        metadatas=metadatas,
        ids=ids
    )


# ✅ Search endpoint
@app.get("/search")
def search(query: str, top_k: int = 3):
    query_embedding = get_embeddings([query])[0]

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k
    )

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


# 🔄 Optional: Ingest video on server start
@app.on_event("startup")
def startup_ingest():
    ingest_video("NLg7Wa6HmYI")  # ✅ your video
