# SearchTube

AI-powered semantic search for YouTube transcripts. Index channels, playlists, or single videos, then search by meaning and jump straight to the timestamped clip.

SearchTube is now **dual mode**:

- **Local mode**: default open-source setup. No auth. Uses local ChromaDB in `backend/channel_chroma_db/`.
- **Supabase mode**: optional hosted setup. Uses Supabase Auth, Postgres, pgvector, quotas, server-hosted Gemini keys, and optional encrypted BYOK storage.

## Features

- Semantic transcript search with timestamped YouTube links
- Channel, playlist, and single-video indexing
- Smart skip for already-indexed videos
- Local BYOK support via browser storage
- Hosted hybrid mode with encrypted BYOK for user-paid AI requests
- Library browser, transcript downloads, result count controls, and recent search history
- Retrieval eval harness for testing embedding changes before changing defaults

## Quick Start: Local Mode

Local mode is the default and does not require Supabase.

```bash
git clone https://github.com/GhostPeony/SearchTube.git
cd SearchTube

python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

npm install
```

Create `.env.local`:

```env
SEARCHTUBE_STORAGE=local
SEARCHTUBE_AUTH_MODE=none
GEMINI_API_KEY=your_gemini_api_key_here
VITE_AUTH_MODE=none
VITE_API_URL=http://localhost:8080
```

Run the app:

```bash
# Terminal 1
python backend/server.py

# Terminal 2
npm run dev
```

Open `http://localhost:3001`.

## Optional: Supabase Mode

Supabase mode is for hosted, multi-user deployments.

Required env vars:

```env
SEARCHTUBE_STORAGE=supabase
SEARCHTUBE_AUTH_MODE=supabase
SEARCHTUBE_API_KEY_MODE=hybrid
VITE_AUTH_MODE=supabase

VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-key
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
SUPABASE_JWT_SECRET=your-jwt-secret
API_KEY_ENCRYPTION_KEY=a-long-random-secret

GEMINI_API_KEY=your-server-side-key
EMBEDDING_MODEL=models/gemini-embedding-001
EMBEDDING_DIMENSIONS=768
LLM_MODEL=gemini-3.1-flash-lite
VITE_API_URL=http://localhost:8080

FREE_SEARCHES_PER_MONTH=100
FREE_INDEXED_VIDEOS_TOTAL=15
FREE_INDEXED_TRANSCRIPT_SECONDS_TOTAL=18000
FREE_MAX_IMPORT_VIDEOS=10
FREE_MAX_SEARCH_RESULTS=5
FREE_MAX_ACTIVE_INGESTION_JOBS=1
```

Run the SQL migrations in `backend/supabase/migrations/`, enable Google OAuth in Supabase, then run the same backend/frontend commands. Google OAuth should use only sign-in scopes (`openid`, email, profile); YouTube content indexing starts from pasted public URLs.

## Runtime Modes

| Variable                  | Values                     |                           Default | Purpose                          |
| ------------------------- | -------------------------- | --------------------------------: | -------------------------------- |
| `SEARCHTUBE_STORAGE`      | `local`, `supabase`        |                           `local` | Backend storage engine           |
| `SEARCHTUBE_AUTH_MODE`    | `none`, `supabase`         |                           derived | Backend auth requirement         |
| `SEARCHTUBE_API_KEY_MODE` | `server`, `byok`, `hybrid` | server if `GEMINI_API_KEY` exists | Gemini key resolution            |
| `VITE_AUTH_MODE`          | `none`, `supabase`         |                            `none` | Frontend auth UI mode            |
| `EMBEDDING_MODEL`         | model id                   |     `models/gemini-embedding-001` | Embedding model                  |
| `EMBEDDING_DIMENSIONS`    | integer                    |                             `768` | Embedding vector size            |
| `LLM_MODEL`               | model id                   |           `gemini-3.1-flash-lite` | Optional answer-generation model |

The backend exposes `GET /api/config` so the frontend can discover the active storage/auth/key mode.

Hosted free workspaces can run 100 hosted searches per month, index or access 15 videos
total, and keep up to 5 transcript-hours in their hosted library. BYOK covers AI requests,
but hosted indexing and storage caps still apply.

## API

Backend runs on `http://localhost:8080`.

| Method   | Endpoint                     | Auth in Local | Auth in Supabase | Description                                           |
| -------- | ---------------------------- | ------------: | ---------------: | ----------------------------------------------------- |
| `GET`    | `/`                          |            No |               No | Health check                                          |
| `GET`    | `/api/config`                |            No |               No | Public runtime config                                 |
| `GET`    | `/api/library`               |            No |              Yes | Indexed library                                       |
| `POST`   | `/api/ingest`                |            No |              Yes | Index YouTube content via SSE                         |
| `POST`   | `/api/search`                |            No |              Yes | Semantic transcript search                            |
| `GET`    | `/api/transcript/{video_id}` |            No |              Yes | Download SRT transcript                               |
| `DELETE` | `/api/video/{video_id}`      |            No |              Yes | Delete video or subscription-scoped data              |
| `GET`    | `/api/usage`                 |            No |              Yes | Quota status                                          |
| `PUT`    | `/api/settings/key`          |            No |              Yes | Save encrypted hosted BYOK when user keys are enabled |
| `DELETE` | `/api/settings/key`          |            No |              Yes | Remove hosted BYOK when user keys are enabled         |

Local mode can also send `X-API-Key` for BYOK requests; the frontend stores this in browser localStorage.

## Embeddings and Evals

Default embedding config:

- Model: `models/gemini-embedding-001`
- Dimensions: `768`
- Document task type for indexing
- Query task type for search
- Supabase schema remains `VECTOR(768)`

`models/gemini-embedding-001` remains the default because the current product indexes text transcripts only and the hosted schema is fixed at 768 dimensions. Treat `gemini-embedding-2` as a future multimodal candidate for audio/video/PDF indexing, not a drop-in replacement without retrieval evals and a schema/re-embed plan.

Do not switch embedding models blindly. Run:

```bash
python scripts/evaluate_retrieval.py
```

To compare candidates:

```bash
$env:EVAL_EMBEDDING_CANDIDATES="models/gemini-embedding-001:768"
python scripts/evaluate_retrieval.py
```

Changing models or dimensions in Supabase requires a retrieval eval, schema compatibility check, and full re-embed of existing chunks.

## Development

```bash
npm run build
npm test
python -m compileall backend
python -c "import backend.server"
python -m pytest
```

Run audit checks:

```bash
npm audit --audit-level=moderate
```

## Docker

Local mode:

```bash
docker-compose up --build
```

For Supabase mode, set the Supabase and encryption env vars before building.

## Troubleshooting

- **No transcript available**: the video may not have captions or may be region/age restricted.
- **Backend unavailable**: confirm `python backend/server.py` is running on port `8080`.
- **Supabase auth fails**: check `VITE_AUTH_MODE=supabase`, Google OAuth setup, redirect URLs, and the backend `SUPABASE_ANON_KEY`.
- **Vector dimension error**: `EMBEDDING_DIMENSIONS` must match the vector store schema.
- **Reset local data**: delete `backend/channel_chroma_db/`.

## License

MIT. See [LICENSE](LICENSE).
