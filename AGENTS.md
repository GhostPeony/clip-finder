# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Project Overview

ClipSeek is a full-stack RAG application for YouTube channel indexing and semantic search. Users can index entire YouTube channels and then search across video transcripts with AI-powered answers that include timestamp citations.

## Development Commands

```bash
# Backend (Terminal 1) - Python FastAPI on port 8000
python backend/server.py
# Or: uvicorn backend.server:app --reload --host 0.0.0.0 --port 8000

# Frontend (Terminal 2) - Vite React on port 3000
npm run dev

# Install dependencies
pip install -r requirements.txt
npm install

# Standalone backend scripts for testing
python backend/ingest.py "https://www.youtube.com/@ChannelName"
python backend/rag.py  # Interactive search REPL
```

API documentation available at http://localhost:8000/docs when backend is running.

## Architecture

**Tech Stack:**

- Frontend: React 19 + TypeScript + Vite + Tailwind CSS
- Backend: Python FastAPI
- Vector DB: ChromaDB (persisted in `./channel_chroma_db/`)
- AI: Google Gemini API (`models/gemini-embedding-001` at 768 dimensions for text transcript embeddings, `gemini-3.1-flash-lite` for bounded LLM extraction/answers)

**Key Data Flow:**

1. **Ingestion** (`/api/ingest`): Channel URL → scrapetube scrapes videos → youtube-transcript-api extracts captions → transcripts chunked into 60-second segments → embedded via Gemini → stored in ChromaDB
2. **Search** (`/api/search`): Query → embedded → ChromaDB similarity search (k=5) → context + query sent to Gemini → answer with `[[clip_N]]` citations returned

**Citation System:** The LLM generates answers with `[[clip_0]]`, `[[clip_1]]` citations. Frontend parses these with regex and renders clickable timestamp links.

## Key Files

| File                           | Purpose                                              |
| ------------------------------ | ---------------------------------------------------- |
| `backend/server.py`            | FastAPI routes (3 endpoints: health, ingest, search) |
| `backend/ingest.py`            | YouTube channel indexing pipeline with SSE streaming |
| `backend/rag.py`               | Search logic, vector retrieval, LLM prompting        |
| `src/App.tsx`                  | Main React component, manages ingest/search modes    |
| `components/AnswerSection.tsx` | Parses `[[clip_N]]` citations into clickable links   |
| `src/services/api.ts`          | Frontend HTTP client with SSE handling               |
| `src/types.ts`                 | TypeScript interfaces (VideoClip, SearchState, etc.) |

## Configuration

**Environment:** Create `.env.local` with `GEMINI_API_KEY=your_key_here`

**Tunable Constants:**

- Chunk size: `ingest.py` line 33 (`CHUNK_SIZE_SECONDS = 60`)
- Embedding model: `backend/config.py` (`models/gemini-embedding-001`, `EMBEDDING_DIMENSIONS=768`)
- LLM model: `backend/config.py` (`gemini-3.1-flash-lite`)
- Top-k results: `rag.py` line 33 (`k=5`)
- System prompt: `rag.py` lines 154-169

## Important Notes

- **LangChain version:** Must use `langchain-google-genai>=4.0.0` (consolidated SDK). Older embedding models are deprecated.
- **Captions required:** Only videos with captions (including auto-generated) can be indexed.
- **Rate limiting:** Large channels (100+ videos) may trigger rate limits. Backend adds 0.5s delay between videos.
- **Database reset:** Delete `./channel_chroma_db/` to clear all indexed data.
