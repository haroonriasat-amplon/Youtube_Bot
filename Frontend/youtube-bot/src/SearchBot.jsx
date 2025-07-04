import React, { useState } from 'react'

export default function SearchBot() {
  const [query, setQuery] = useState('')
  const [messages, setMessages] = useState([
    {
      id: '1',
      type: 'bot',
      content:
        "Hi! I'm Amplon Search Bot. I can help you find info from YouTube videos and PDFs. What would you like to search for?",
      timestamp: new Date(),
    },
  ])
  const [loading, setLoading] = useState(false)

  const addMessage = (msg) => {
    const newMsg = { ...msg, id: Date.now().toString(), timestamp: new Date() }
    setMessages((prev) => [...prev, newMsg])
    return newMsg.id
  }

  const updateMessage = (id, updates) => {
    setMessages((prev) => prev.map((m) => (m.id === id ? { ...m, ...updates } : m)))
  }

  const formatTime = (s) => `${Math.floor(s / 60)}:${(s % 60).toString().padStart(2, '0')}`

const handleSearch = async () => {
  if (!query.trim()) return;

  addMessage({ type: 'user', content: query });
  const botId = addMessage({ type: 'bot', content: 'Searching…', loading: true });
  setLoading(true);

  try {
    const [ytRes, pdfRes] = await Promise.all([
      fetch(`http://localhost:8000/search?query=${encodeURIComponent(query)}`),
      fetch(`http://localhost:8000/search-pdf?query=${encodeURIComponent(query)}`)
    ]);

    const ytData = await ytRes.json();
    const pdfData = await pdfRes.json();

    updateMessage(botId, {
      content: `Here are the results for "${query}":`,
      ytResults: Array.isArray(ytData.results) ? ytData.results : [],
      pdfResults: Array.isArray(pdfData.results) ? pdfData.results : [],
      loading: false
    });
  } catch (e) {
    updateMessage(botId, {
      content: '❌ Search failed. Try again.',
      loading: false
    });
  } finally {
    setLoading(false);
    setQuery('');
  }
};


  const handleKey = (e) => {
    if (e.key === 'Enter' && !loading) {
      e.preventDefault()
      handleSearch()
    }
  }

  return (
    <div className="h-screen flex flex-col max-w-3xl mx-auto bg-gray-100">
      <header className="bg-white shadow p-4 text-xl font-semibold">Amplon Search Bot</header>
      <main className="flex-1 overflow-auto p-4 space-y-4">
        {messages.map((msg) => (
          <div key={msg.id} className={`flex ${msg.type === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div
              className={`${msg.type === 'user' ? 'bg-blue-600 text-white' : 'bg-white'} p-4 rounded-lg shadow max-w-md`}
            >
              <p className="text-sm mb-2">{msg.content}</p>

              {/* YouTube videos */}
              {msg.ytResults?.map((yt, idx) => (
                <div key={idx} className="mt-4 border rounded-lg overflow-hidden">
                  <iframe
                    width="100%"
                    height="200"
                    src={`https://www.youtube.com/embed/${yt.video_id}?start=${yt.start}`}
                    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                    allowFullScreen
                  ></iframe>
                  <div className="p-2 bg-gray-50">
                    <p className="text-gray-800 mb-1">▶️ {yt.text}</p>
                    <a
                      href={yt.link}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-600 text-sm hover:underline"
                    >
                      Watch from {formatTime(yt.start)}
                    </a>
                  </div>
                </div>
              ))}

              {/* PDF results */}
              {msg.pdfResults?.map((pdf, idx) => (
                <div key={idx} className="mt-4 p-3 border rounded-lg bg-gray-50">
                  <p className="text-gray-800">
                    📄 {pdf.filename} – page {pdf.page}
                  </p>
                  <a
                    href={pdf.link}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-green-600 text-sm hover:underline"
                  >
                    View PDF →
                  </a>
                </div>
              ))}

              {msg.loading && <div className="mt-2 text-gray-500 italic">Loading…</div>}
            </div>
          </div>
        ))}
      </main>

      <footer className="p-4 bg-white border-t flex gap-2">
        <input
          type="text"
          className="flex-1 p-2 border rounded"
          placeholder="Ask me about YouTube or PDFs..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKey}
          disabled={loading}
        />
        <button
          className="bg-blue-600 text-white px-4 rounded disabled:bg-gray-400"
          onClick={handleSearch}
          disabled={loading || !query.trim()}
        >
          {loading ? 'Searching…' : 'Send'}
        </button>
      </footer>
    </div>
  )
}
