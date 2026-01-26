# Clip Finder

**AI-powered semantic search for YouTube videos.** Index any channel, playlist, or video and search through transcripts with natural language. Find the exact moment you're looking for.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-green.svg)](https://python.org)
[![Node 18+](https://img.shields.io/badge/Node-18+-green.svg)](https://nodejs.org)

<!-- Add screenshot here -->

## Features

### Search & Discovery
- **Semantic Search** — Find clips by meaning, not just keywords
- **Configurable Results** — Choose 1, 3, 5, or 10 clips per search
- **Intro Skip** — Automatically filters out first 2 minutes to avoid teasers
- **Timestamp Citations** — Click any result to jump to that exact moment

### Content Indexing
- **Index Anything** — Channels, playlists, or individual videos
- **Smart Skip** — Re-running on a channel only indexes new videos
- **No YouTube API Key** — Uses web scraping (scrapetube) for video discovery
- **Real-time Progress** — Live status updates via Server-Sent Events

### Library Management
- **Multiple Views** — Grid layout or grouped by channel
- **Filter & Sort** — Search by name, sort by date added
- **Compact/Large Modes** — Choose your preferred density
- **Search History** — Quick access to your last 20 searches
- **Delete Videos** — Remove individual videos from your index
- **Rename Channels** — Fix "Unknown Channel" labels via API

### Transcripts
- **60-Second Chunks** — Precise segments for accurate timestamps
- **SRT Export** — Download any video's transcript as subtitles
- **Full Text View** — Read complete transcript for each clip

### Developer Experience
- **BYOK** — Bring Your Own Gemini API Key (stored locally in browser)
- **REST API** — Full API with OpenAPI documentation at `/docs`
- **Local Storage** — All data stored on your machine in ChromaDB

---

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 18+
- [Gemini API Key](https://aistudio.google.com/apikey) (free tier available)

### Installation

```bash
# Clone the repository
git clone https://github.com/GhostPeony/clip-finder.git
cd clip-finder

# Create and activate a virtual environment (recommended)
python -m venv venv
# Windows:
venv\Scripts\activate
# Mac/Linux:
# source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Install Node dependencies
npm install
```

### Configuration

Create a `.env.local` file in the project root:

```env
GEMINI_API_KEY=your_gemini_api_key_here
```

Or use BYOK mode — add your API key in the app's Settings after launching.

### Running

**Terminal 1 — Backend (FastAPI on port 8080):**
```bash
python backend/server.py
```

**Terminal 2 — Frontend (Vite on port 3001):**
```bash
npm run dev
```

Open **http://localhost:3001** in your browser.

---

## Usage

### Index Videos

1. Go to the **Home** page
2. Paste a YouTube URL in the search box:
   - Channel: `https://www.youtube.com/@ChannelName`
   - Playlist: `https://www.youtube.com/playlist?list=PLxxxxx`
   - Video: `https://www.youtube.com/watch?v=xxxxx`
3. Click **Index** and watch the progress stream in real-time

**Note:** Only videos with captions (including auto-generated) can be indexed.

### Search Your Library

1. Check the **Search Library** checkbox
2. Type a natural language query (e.g., "What did they say about machine learning?")
3. Choose how many results you want (1-10)
4. Click **Search**

### Browse Results

- **Left sidebar** — Click any clip thumbnail to select it
- **Main area** — Video player starts at that timestamp
- **Below video** — Full transcript of the selected segment
- **Share button** — Copy a YouTube link with timestamp

### Manage Library

1. Click **Library** in the navigation
2. Use the filter box to search by channel or video name
3. Toggle between **Grid** and **By Channel** views
4. Choose **Compact** or **Large** thumbnail sizes
5. Sort by **Default** or **Recently Added**
6. Hover over any video to **Download transcript** or **Delete**

### Download Transcripts

- In Library view, hover over a video and click the download icon
- Transcript downloads as an SRT subtitle file

---

## API Reference

The backend runs on `http://localhost:8080` with interactive docs at `/docs`.

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Health check, returns `{ status, hasApiKey }` |
| `GET` | `/api/library` | Get all indexed content grouped by channel |
| `POST` | `/api/ingest` | Index YouTube content (SSE streaming) |
| `POST` | `/api/search` | Semantic search with optional BYOK header |
| `GET` | `/api/transcript/{video_id}` | Download transcript as SRT file |
| `DELETE` | `/api/video/{video_id}` | Delete a video and all its clips |
| `POST` | `/api/channel/rename` | Rename a channel in the database |

### Example: Search

```bash
curl -X POST http://localhost:8080/api/search \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_gemini_key" \
  -d '{"query": "How does the creator handle errors?", "limit": 5}'
```

### Example: Rename Channel

```bash
curl -X POST http://localhost:8080/api/channel/rename \
  -H "Content-Type: application/json" \
  -d '{"old_name": "Unknown Channel", "new_name": "Actual Channel Name"}'
```

---

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `GEMINI_API_KEY` | Google Gemini API key for embeddings and search | Yes* |

*Or use BYOK mode via the Settings modal in the app.

### Tunable Constants

| Setting | File | Default | Description |
|---------|------|---------|-------------|
| Chunk size | `backend/ingest.py` | 60 seconds | Transcript segment length |
| Intro skip | `backend/rag.py` | 120 seconds | Skip clips from first N seconds |
| Top-K results | `backend/rag.py` | 5 | Default number of search results |
| Embedding model | `backend/ingest.py` | `text-embedding-004` | Google embedding model |
| LLM model | `backend/rag.py` | `gemini-2.0-flash` | Model for search |

### Storage

- **Database:** `./channel_chroma_db/` (ChromaDB vector store)
- **API Key:** Browser localStorage (`clipfinder_api_key`)
- **Search History:** Browser localStorage (`clipfinder_search_history`)

To reset: delete `./channel_chroma_db/` folder.

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | React 19, TypeScript, Vite, Tailwind CSS |
| Backend | FastAPI, Python 3.12 |
| AI/ML | Google Gemini (`text-embedding-004`, `gemini-2.0-flash`) |
| Vector DB | ChromaDB (local) |
| Scraping | scrapetube, youtube-transcript-api |

---

## Project Structure

```
clip-finder/
├── backend/
│   ├── server.py          # FastAPI routes and SSE streaming
│   ├── ingest.py          # YouTube indexing pipeline
│   └── rag.py             # Semantic search engine
├── src/
│   ├── App.tsx            # Main React application
│   ├── components/
│   │   ├── UnifiedSearchView.tsx  # Home page (index + search)
│   │   ├── LibraryView.tsx        # Indexed content browser
│   │   ├── VideoPlayer.tsx        # YouTube embed wrapper
│   │   ├── SettingsModal.tsx      # API key management
│   │   ├── AnswerSection.tsx      # Citation rendering
│   │   └── Toast.tsx              # Notifications
│   ├── services/
│   │   └── api.ts         # Backend client + localStorage
│   └── types.ts           # TypeScript interfaces
├── .env.local             # Your API key (create this)
├── requirements.txt       # Python dependencies
├── package.json           # Node dependencies
└── vite.config.ts         # Vite configuration
```

---

## Docker

```bash
# Create .env file
echo "GEMINI_API_KEY=your_key_here" > .env

# Build and run
docker-compose up --build
```

Access at **http://localhost**

---

## Troubleshooting

### "No transcript available"
- The video doesn't have captions (including auto-generated)
- Some videos have captions disabled by the creator

### "Unknown Channel" appearing
- Use the rename API to fix: `POST /api/channel/rename`
- Future indexes will use the correct name

### Rate limiting on large channels
- Channels with 100+ videos may trigger YouTube rate limits
- The backend automatically adds delays between requests
- If issues persist, try indexing in smaller batches

### Search returns no results
- Make sure you've indexed some content first
- Check that your Gemini API key is configured
- Try a broader search query

### Reset everything
```bash
# Delete the database
rm -rf ./channel_chroma_db/

# Clear browser storage (in browser console)
localStorage.clear()
```

---

## Contributing

Contributions welcome! Feel free to:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Setup

```bash
# Backend with auto-reload
uvicorn backend.server:app --reload --host 0.0.0.0 --port 8080

# Frontend with hot reload
npm run dev
```

---

## License

MIT — see [LICENSE](LICENSE)

---

Made by [Ghost Peony](https://ghostpeony.com) · [GitHub](https://github.com/ghostpeony) · [LinkedIn](https://linkedin.com/in/cadecrussell)
