## Clip Finder

Index your favorite YouTube channels, playlists, or individual videos and instantly find the exact quote or conversation you're looking for.

Ever forget where your favorite podcaster dropped that quote you wanted to share with a friend? Can't remember which episode had that perfect explanation? Trying to find a specific scene in a movie that's on YouTube?

Clip Finder solves this.

🎙️ Podcasts — Index entire shows and search for topics, quotes, or guests
🎓 Educational Content — Index coding tutorials and find exact clips on the topics you need help with
🎬 Entertainment — Find that scene, that line, that moment
📺 Any YouTube Content — Channels, playlists, or single videos


https://github.com/user-attachments/assets/a6e21dd1-af9a-433c-9ee8-d6dabdccf92c


## Features

- **Semantic Search** — Search video content using natural language, not just keywords
- **Index Anything** — Channels, playlists, or individual videos
- **Jump to Timestamp** — Click any clip to play from that exact moment
- **Full Transcripts** — View the complete transcript for each relevant clip
- **YouTube-Style Layout** — Clips sidebar, video player, and transcript view
- **Intro Skip** — Automatically filters out teaser/intro clips (first 2 minutes)
- **Configurable Results** — Choose how many clips to return (1, 3, 5, or 10)
- **Library Management** — View all indexed videos, organized by channel
- **Local Storage** — All data stored locally in ChromaDB
- **BYOK** — Bring your own Gemini API key

## Quick Start

### Prerequisites
- Python 3.12+
- Node.js 18+
- [Gemini API Key](https://aistudio.google.com/apikey) (free tier available)

### Installation

```bash
# Clone the repo
git clone https://github.com/GhostPeony/clip-finder.git
cd clip-finder

# Install backend dependencies
cd backend
pip install -r requirements.txt
cd ..

# Install frontend dependencies
npm install
```

### Configuration

Create a `.env.local` file in the root directory:

```env
GEMINI_API_KEY=your_gemini_api_key_here
```

### Running

**Terminal 1 — Backend:**
```bash
cd backend
python server.py
```

**Terminal 2 — Frontend:**
```bash
npm run dev
```

Open **http://localhost:3001** in your browser.

## 📖 How to Use

### 1. Index Videos
- Click **"+ Add"** in the navigation
- Paste a YouTube URL (channel, playlist, or video)
- Click **"Index"** and wait for processing
- A spinner shows status updates during indexing

### 2. Search Your Library
- Go to **"Search"** view
- Type a natural language query (e.g., "What did they say about AI safety?")
- Set the number of results you want (1-10)
- Click **"Clip Finder Search"**

### 3. Browse Results
- **Left sidebar** — Click any clip to select it
- **Center** — Video player jumps to that timestamp
- **Below video** — Full transcript of the selected clip

### 4. Manage Library
- Click **"Library"** to see all indexed content
- Videos are organized by channel
- Click any video to open it on YouTube
- Hover over a video to see the delete button

## 🛠 Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | React, TypeScript, Vite, Tailwind CSS |
| Backend | FastAPI, Python 3.12 |
| AI/ML | LangChain, Google Gemini Embeddings |
| Database | ChromaDB (local vector store) |
| Transcripts | youtube-transcript-api |

## 📁 Project Structure

```
clip-finder/
├── backend/
│   ├── server.py      # FastAPI REST API
│   ├── ingest.py      # YouTube indexing logic
│   ├── rag.py         # Search/retrieval logic
│   └── requirements.txt
├── src/
│   ├── App.tsx        # Main React app
│   ├── components/    # React components
│   │   ├── IngestionView.tsx
│   │   ├── LibraryView.tsx
│   │   ├── VideoPlayer.tsx
│   │   └── SettingsModal.tsx
│   ├── services/
│   │   └── api.ts     # API client
│   └── types.ts       # TypeScript types
├── .env.local         # Your API key (create this)
├── .env.example       # Template
└── package.json
```

## 🐳 Docker (Optional)

For containerized deployment:

```bash
# Create .env file with your API key
echo "GEMINI_API_KEY=your_key_here" > .env

# Build and run
docker-compose up --build
```

Access at **http://localhost**

## ⚙️ Configuration

| Environment Variable | Description | Required |
|---------------------|-------------|----------|
| `GEMINI_API_KEY` | Your Google Gemini API key | Yes |

## 📝 Notes

- **API Key Usage**: The Gemini API is used for generating embeddings during both indexing and search. Each search makes 1 API call.
- **Storage**: Indexed data is stored locally in `channel_chroma_db/`. Back up this folder to preserve your library.
- **Intro Filter**: Search results automatically skip clips from the first 2 minutes of videos to avoid teaser content.

## 🤝 Contributing

Contributions welcome! Feel free to open issues or submit PRs.

## 📄 License

MIT — see [LICENSE](LICENSE)

---

Made with ❤️ by [Ghost Peony](https://github.com/ghostpeony)
