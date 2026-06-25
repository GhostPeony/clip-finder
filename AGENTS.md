# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Project Overview

Memexai is a hosted RAG application for YouTube video, playlist, and channel ingestion. Users save videos into a Supabase-backed library, then humans and agents can search timestamped transcript moments, generate study guides, and build repo-aware implementation briefs through the web app or MCP.

## Development Commands

```bash
# Backend (Terminal 1) - Python FastAPI on port 8080
python backend/server.py
# Or: uvicorn backend.server:app --reload --host 0.0.0.0 --port 8080

# Frontend (Terminal 2) - Vite React
npm run dev

# Install dependencies
pip install -r requirements.txt
npm install

# Standalone backend scripts for testing
python backend/ingest.py "https://www.youtube.com/@ChannelName"
python backend/rag.py  # Interactive search REPL
```

API documentation available at http://localhost:8080/docs when backend is running.

## Architecture

**Tech Stack:**

- Frontend: React 19 + TypeScript + Vite + Tailwind CSS
- Backend: Python FastAPI
- Database/vector store: Supabase Postgres + pgvector
- AI: Google Gemini API (`models/gemini-embedding-001` at 768 dimensions for text transcript embeddings, `gemini-3.1-flash-lite` for bounded LLM extraction/answers)

**Key Data Flow:**

1. **Ingestion** (`/api/ingest` or hosted jobs): YouTube URL → scrapetube discovers videos → youtube-transcript-api extracts captions → transcripts chunked into 60-second segments → embedded via Gemini → stored once in Supabase videos/chunks/source-context tables.
2. **Access grants**: user libraries point at canonical videos through `user_videos` and `user_channels`, so duplicate ingestions reuse embeddings without making the global corpus searchable.
3. **Search** (`/api/search` or `search_video_moments` over MCP): Query → embedded → Supabase `search_chunks` RPC filters by the current user's grants → answer with `[[clip_N]]` citations returned.

**Citation System:** The LLM generates answers with `[[clip_0]]`, `[[clip_1]]` citations. Frontend parses these with regex and renders clickable timestamp links.

## Key Files

| File                           | Purpose                                              |
| ------------------------------ | ---------------------------------------------------- |
| `backend/server.py`            | FastAPI REST routes, public agent docs, MCP endpoint |
| `backend/ingest.py`            | Supabase/pgvector YouTube ingestion pipeline         |
| `backend/rag.py`               | User-scoped pgvector search and answer generation    |
| `backend/mcp_adapter.py`       | Stateless JSON-RPC MCP resources, tools, prompts     |
| `backend/context.py`           | Source context, personal overlays, agent briefs      |
| `src/App.tsx`                  | Main React component, manages ingest/search modes    |
| `components/AnswerSection.tsx` | Parses `[[clip_N]]` citations into clickable links   |
| `src/services/api.ts`          | Frontend HTTP client with SSE handling               |
| `src/types.ts`                 | TypeScript interfaces (VideoClip, SearchState, etc.) |

## Configuration

**Environment:** Create `.env.local` for hosted dev with `SEARCHTUBE_STORAGE=supabase`, Supabase credentials, `API_KEY_ENCRYPTION_KEY`, and `GEMINI_API_KEY`.

**Tunable Constants:**

- Chunk size: `ingest.py` line 33 (`CHUNK_SIZE_SECONDS = 60`)
- Embedding model: `backend/config.py` (`models/gemini-embedding-001`, `EMBEDDING_DIMENSIONS=768`)
- LLM model: `backend/config.py` (`gemini-3.1-flash-lite`)
- Top-k results: `rag.py` line 33 (`k=5`)
- System prompt: `rag.py` lines 154-169

## Important Notes

- **Storage mode:** This hosted fork supports Supabase only. The old local ChromaDB runtime path has been removed.
- **LangChain version:** `langchain-google-genai>=4.0.0` is still used for Gemini embedding/chat wrappers. Older embedding models are deprecated.
- **Captions required:** Only videos with captions (including auto-generated) can be indexed.
- **Rate limiting:** Large channels (100+ videos) may trigger rate limits. Backend adds 0.5s delay between videos.
