# ClipSeek Multi-User Web App Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Convert ClipSeek from a single-user self-hosted app to a multi-user web app with Supabase auth, pgvector storage, shared-on-demand data model, and BYOK + free tier metering.

**Architecture:** Supabase handles auth (Google/GitHub OAuth) and data storage (PostgreSQL + pgvector). FastAPI stays as the compute backend for ingestion and search, now validating JWTs and writing to Supabase instead of ChromaDB. Frontend adds Supabase SDK for auth and attaches JWTs to all API calls.

**Tech Stack:** React 19, TypeScript, Vite, Tailwind CSS, Supabase (Auth + PostgreSQL + pgvector), FastAPI, Python, `gemini-embedding-001`, `gemini-2.5-flash-lite`

**Design doc:** `docs/plans/2026-02-27-multi-user-webapp-design.md`

---

## Task 1: Supabase Project Setup & Database Schema

**Files:**
- Create: `backend/supabase/migrations/001_initial_schema.sql`
- Create: `.env.example`
- Modify: `.gitignore`

This task is done manually in the Supabase dashboard + locally. The SQL migration file is for documentation and reproducibility.

**Step 1: Create Supabase project**

Go to https://supabase.com/dashboard, create a new project. Note the project URL, anon key, and service role key.

**Step 2: Enable pgvector extension**

Run in Supabase SQL Editor:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

**Step 3: Write the migration file**

Create `backend/supabase/migrations/001_initial_schema.sql`:

```sql
-- Enable pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- Profiles (extends Supabase auth.users)
CREATE TABLE profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    display_name TEXT,
    avatar_url TEXT,
    api_key_enc TEXT,  -- Encrypted Gemini API key (nullable)
    free_searches_today INT NOT NULL DEFAULT 0,
    free_indexes_this_month INT NOT NULL DEFAULT 0,
    last_search_reset DATE NOT NULL DEFAULT CURRENT_DATE,
    last_index_reset DATE NOT NULL DEFAULT (DATE_TRUNC('month', CURRENT_DATE))::DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Auto-create profile on user signup
CREATE OR REPLACE FUNCTION handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO profiles (id, display_name, avatar_url)
    VALUES (
        NEW.id,
        COALESCE(NEW.raw_user_meta_data->>'full_name', NEW.raw_user_meta_data->>'name', 'User'),
        COALESCE(NEW.raw_user_meta_data->>'avatar_url', NEW.raw_user_meta_data->>'picture', '')
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION handle_new_user();

-- Channels
CREATE TABLE channels (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    youtube_handle TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL DEFAULT 'Unknown Channel',
    total_videos INT NOT NULL DEFAULT 0,
    indexed_at TIMESTAMPTZ,
    indexed_by UUID REFERENCES profiles(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- User-channel subscriptions (shared-on-demand join table)
CREATE TABLE user_channels (
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    channel_id UUID NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
    added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, channel_id)
);

-- Videos
CREATE TABLE videos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    channel_id UUID NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
    youtube_video_id TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL DEFAULT 'Unknown Title',
    thumbnail_url TEXT NOT NULL DEFAULT '',
    indexed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Transcript chunks with vector embeddings
CREATE TABLE chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    video_id UUID NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    start_seconds INT NOT NULL,
    end_seconds INT NOT NULL,
    embedding VECTOR(768) NOT NULL
);

-- Index for vector similarity search
CREATE INDEX chunks_embedding_idx ON chunks
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Index for filtering by video
CREATE INDEX chunks_video_id_idx ON chunks(video_id);

-- Index for video lookup by youtube ID
CREATE INDEX videos_youtube_id_idx ON videos(youtube_video_id);

-- Usage logs
CREATE TABLE usage_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    action TEXT NOT NULL CHECK (action IN ('search', 'index')),
    video_count INT,
    used_own_key BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX usage_logs_user_date_idx ON usage_logs(user_id, created_at);

-- Search history
CREATE TABLE search_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    query TEXT NOT NULL,
    result_chunk_ids UUID[] DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX search_history_user_idx ON search_history(user_id, created_at DESC);

-- Row-Level Security Policies
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE channels ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_channels ENABLE ROW LEVEL SECURITY;
ALTER TABLE videos ENABLE ROW LEVEL SECURITY;
ALTER TABLE chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE usage_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE search_history ENABLE ROW LEVEL SECURITY;

-- Profiles: users can read/update their own profile
CREATE POLICY profiles_select ON profiles FOR SELECT USING (auth.uid() = id);
CREATE POLICY profiles_update ON profiles FOR UPDATE USING (auth.uid() = id);

-- Channels: anyone authenticated can read, insert handled by backend service role
CREATE POLICY channels_select ON channels FOR SELECT TO authenticated USING (true);

-- User_channels: users see their own subscriptions
CREATE POLICY user_channels_select ON user_channels FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY user_channels_insert ON user_channels FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY user_channels_delete ON user_channels FOR DELETE USING (auth.uid() = user_id);

-- Videos: anyone authenticated can read (shared data)
CREATE POLICY videos_select ON videos FOR SELECT TO authenticated USING (true);

-- Chunks: anyone authenticated can read (shared data, search scoping done in query)
CREATE POLICY chunks_select ON chunks FOR SELECT TO authenticated USING (true);

-- Usage logs: users see their own
CREATE POLICY usage_logs_select ON usage_logs FOR SELECT USING (auth.uid() = user_id);

-- Search history: users see their own
CREATE POLICY search_history_select ON search_history FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY search_history_insert ON search_history FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY search_history_delete ON search_history FOR DELETE USING (auth.uid() = user_id);
```

**Step 4: Run migration in Supabase SQL Editor**

Copy and paste the SQL above into the Supabase SQL Editor and execute.

**Step 5: Configure OAuth providers**

In Supabase Dashboard > Authentication > Providers:
- Enable Google: Add OAuth client ID and secret from Google Cloud Console
- Enable GitHub: Add OAuth app client ID and secret from GitHub Settings > Developer Settings

**Step 6: Create `.env.example`**

```bash
# Supabase (public - safe to expose in frontend)
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-key-here

# Supabase (secret - backend only, NEVER expose in frontend)
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key-here

# Gemini API (server-side free tier key)
GEMINI_API_KEY=your-gemini-api-key-here

# Backend URL for frontend (optional, defaults to localhost:8080)
VITE_API_URL=http://localhost:8080
```

**Step 7: Update `.gitignore`**

Ensure these lines exist:

```
.env.local
.env
.env.production
channel_chroma_db/
```

**Step 8: Commit**

```bash
git add backend/supabase/migrations/001_initial_schema.sql .env.example .gitignore
git commit -m "feat: add Supabase database schema and env config"
```

---

## Task 2: Backend Dependencies & Supabase Client

**Files:**
- Modify: `requirements.txt`
- Create: `backend/db.py`

**Step 1: Update `requirements.txt`**

Add Supabase and remove ChromaDB dependencies:

```
# Supabase
supabase>=2.0.0
python-jose[cryptography]>=3.3.0  # JWT validation

# Remove these (keep for now during migration, remove in Task 7):
# langchain-chroma>=1.1.0
```

Actually, keep `langchain-chroma` for now -- we'll remove it after migration is complete. Add the new deps:

```
# Supabase
supabase>=2.0.0
python-jose[cryptography]>=3.3.0
```

**Step 2: Install dependencies**

Run: `pip install supabase python-jose[cryptography]`

**Step 3: Create `backend/db.py` -- Supabase client + auth helpers**

```python
"""
db.py - Supabase database client and auth utilities

Provides:
- Supabase client singleton (service role for backend operations)
- JWT validation middleware for FastAPI
- Quota checking helpers
"""

import os
from functools import lru_cache
from datetime import date

from dotenv import load_dotenv
from supabase import create_client, Client
from jose import jwt, JWTError
from fastapi import HTTPException, Header, Depends
from typing import Optional

# Load environment
env_path = os.path.join(os.path.dirname(__file__), '..', '.env.local')
load_dotenv(env_path)

SUPABASE_URL = os.getenv("VITE_SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")

# Free tier limits
FREE_SEARCHES_PER_DAY = 20
FREE_INDEXES_PER_MONTH = 50


def get_supabase() -> Client:
    """Get Supabase client with service role key (full database access)."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


async def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    """
    FastAPI dependency: extract and validate user from JWT.

    Usage:
        @app.get("/api/protected")
        async def protected(user: dict = Depends(get_current_user)):
            user_id = user["sub"]
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")

    token = authorization.replace("Bearer ", "")

    try:
        # Supabase JWTs are signed with the JWT secret from project settings
        payload = jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated"
        )
        return payload
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")


def get_user_profile(supabase: Client, user_id: str) -> dict:
    """Fetch user profile, resetting quotas if needed."""
    result = supabase.table("profiles").select("*").eq("id", user_id).single().execute()
    profile = result.data

    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    # Reset daily search counter if new day
    today = date.today().isoformat()
    if profile.get("last_search_reset") != today:
        supabase.table("profiles").update({
            "free_searches_today": 0,
            "last_search_reset": today
        }).eq("id", user_id).execute()
        profile["free_searches_today"] = 0

    # Reset monthly index counter if new month
    current_month = date.today().replace(day=1).isoformat()
    if profile.get("last_index_reset") != current_month:
        supabase.table("profiles").update({
            "free_indexes_this_month": 0,
            "last_index_reset": current_month
        }).eq("id", user_id).execute()
        profile["free_indexes_this_month"] = 0

    return profile


def check_search_quota(profile: dict) -> bool:
    """Check if user can perform a search. Returns True if allowed."""
    if profile.get("api_key_enc"):
        return True  # BYOK users have no limits
    return profile.get("free_searches_today", 0) < FREE_SEARCHES_PER_DAY


def check_index_quota(profile: dict, video_count: int) -> bool:
    """Check if user can index N videos. Returns True if allowed."""
    if profile.get("api_key_enc"):
        return True  # BYOK users have no limits
    remaining = FREE_INDEXES_PER_MONTH - profile.get("free_indexes_this_month", 0)
    return remaining >= video_count


def increment_search_usage(supabase: Client, user_id: str, used_own_key: bool):
    """Increment search counter and log usage."""
    if not used_own_key:
        supabase.rpc("increment_field", {
            "table_name": "profiles",
            "field_name": "free_searches_today",
            "row_id": user_id
        }).execute()

    supabase.table("usage_logs").insert({
        "user_id": user_id,
        "action": "search",
        "used_own_key": used_own_key
    }).execute()


def increment_index_usage(supabase: Client, user_id: str, video_count: int, used_own_key: bool):
    """Increment index counter and log usage."""
    if not used_own_key:
        # Increment by video_count
        profile = supabase.table("profiles").select("free_indexes_this_month").eq("id", user_id).single().execute()
        current = profile.data.get("free_indexes_this_month", 0)
        supabase.table("profiles").update({
            "free_indexes_this_month": current + video_count
        }).eq("id", user_id).execute()

    supabase.table("usage_logs").insert({
        "user_id": user_id,
        "action": "index",
        "video_count": video_count,
        "used_own_key": used_own_key
    }).execute()
```

**Step 4: Commit**

```bash
git add requirements.txt backend/db.py
git commit -m "feat: add Supabase client, JWT auth, and quota helpers"
```

---

## Task 3: Migrate Embedding Model

**Files:**
- Modify: `backend/rag.py` (line 40: `EMBEDDING_MODEL`)
- Modify: `backend/ingest.py` (line 35: `EMBEDDING_MODEL`)

The old `text-embedding-004` model is deprecated. Migrate to `gemini-embedding-001` before building the new pipeline.

**Step 1: Update embedding model in `backend/rag.py`**

Change line 40:

```python
# Before:
EMBEDDING_MODEL = "models/text-embedding-004"
# After:
EMBEDDING_MODEL = "models/gemini-embedding-001"
```

**Step 2: Update embedding model in `backend/ingest.py`**

Change line 35:

```python
# Before:
EMBEDDING_MODEL = "models/text-embedding-004"
# After:
EMBEDDING_MODEL = "models/gemini-embedding-001"
```

**Step 3: Update LLM model in `backend/rag.py`**

Change line 41:

```python
# Before:
LLM_MODEL = "gemini-2.0-flash"
# After:
LLM_MODEL = "gemini-2.5-flash-lite"
```

**Step 4: Test that embeddings still work**

Run: `python backend/rag.py` and try a search query.

If ChromaDB complains about embedding dimension mismatch (768 vs 3072), you'll need to either:
- Delete `channel_chroma_db/` and re-index (simplest, fine for dev)
- Or configure `output_dimensionality=768` in the embedding call

For the migration to pgvector, we'll use 768 dimensions (matching the schema) by setting `output_dimensionality=768` when creating embeddings.

**Step 5: Commit**

```bash
git add backend/rag.py backend/ingest.py
git commit -m "feat: migrate to gemini-embedding-001 and gemini-2.5-flash-lite"
```

---

## Task 4: New Ingestion Pipeline (pgvector)

**Files:**
- Create: `backend/ingest_pg.py`

This is the new ingestion module that writes to Supabase/pgvector instead of ChromaDB. The YouTube scraping logic stays identical -- only the storage layer changes.

**Step 1: Create `backend/ingest_pg.py`**

```python
"""
ingest_pg.py - YouTube Indexer for Supabase/pgvector

Same YouTube scraping pipeline as ingest.py, but writes to
Supabase PostgreSQL with pgvector embeddings instead of ChromaDB.

Implements shared-on-demand: if a channel is already indexed,
new users just subscribe without re-indexing.
"""

import os
import time
from typing import Generator, Optional
from dotenv import load_dotenv

import scrapetube
from youtube_transcript_api import YouTubeTranscriptApi
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from db import get_supabase

# Load environment
env_path = os.path.join(os.path.dirname(__file__), '..', '.env.local')
load_dotenv(env_path)

CHUNK_SIZE_SECONDS = 60
EMBEDDING_MODEL = "models/gemini-embedding-001"

# Reuse helpers from original ingest.py
from ingest import (
    detect_url_type,
    extract_video_title,
    extract_channel_name,
    fetch_video_metadata,
    get_transcript_chunks,
)


_embeddings_instance = None
_embeddings_api_key = None


def get_embeddings(api_key: str = None) -> GoogleGenerativeAIEmbeddings:
    """Get embeddings instance, with 768-dim output for pgvector compatibility."""
    global _embeddings_instance, _embeddings_api_key

    key_to_use = api_key or os.getenv("GEMINI_API_KEY")
    if not key_to_use or key_to_use == "PLACEHOLDER_API_KEY":
        raise ValueError("No API key provided.")

    if _embeddings_instance is not None and _embeddings_api_key == key_to_use:
        return _embeddings_instance

    _embeddings_api_key = key_to_use
    _embeddings_instance = GoogleGenerativeAIEmbeddings(
        model=EMBEDDING_MODEL,
        google_api_key=key_to_use,
        task_type="RETRIEVAL_DOCUMENT",
    )
    return _embeddings_instance


def get_or_create_channel(supabase, youtube_handle: str, channel_name: str, user_id: str) -> dict:
    """
    Get existing channel or create new one. Returns channel record.
    Also creates user_channels subscription.
    """
    # Check if channel exists
    result = supabase.table("channels").select("*").eq("youtube_handle", youtube_handle).maybe_single().execute()

    if result.data:
        channel = result.data
        # Subscribe user to existing channel
        supabase.table("user_channels").upsert({
            "user_id": user_id,
            "channel_id": channel["id"]
        }).execute()
        return channel

    # Create new channel
    result = supabase.table("channels").insert({
        "youtube_handle": youtube_handle,
        "name": channel_name,
        "indexed_by": user_id,
    }).execute()
    channel = result.data[0]

    # Subscribe user
    supabase.table("user_channels").insert({
        "user_id": user_id,
        "channel_id": channel["id"]
    }).execute()

    return channel


def get_indexed_video_ids_pg(supabase, channel_id: str) -> set:
    """Get set of YouTube video IDs already indexed for a channel."""
    result = supabase.table("videos").select("youtube_video_id").eq("channel_id", channel_id).execute()
    return {row["youtube_video_id"] for row in (result.data or [])}


def index_video_to_pg(
    supabase,
    video_id: str,
    title: str,
    channel_name: str,
    channel_id: str,
    chunks: list[dict],
    api_key: str = None
) -> int:
    """
    Embed and store video chunks in pgvector.
    Returns number of chunks indexed.
    """
    embeddings = get_embeddings(api_key)

    # Create video record
    video_result = supabase.table("videos").insert({
        "channel_id": channel_id,
        "youtube_video_id": video_id,
        "title": title,
        "thumbnail_url": f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg",
    }).execute()
    db_video_id = video_result.data[0]["id"]

    # Embed all chunks in batch
    texts = [chunk["text"] for chunk in chunks]
    vectors = embeddings.embed_documents(texts)

    # Insert chunks with embeddings
    chunk_rows = []
    for chunk, vector in zip(chunks, vectors):
        chunk_rows.append({
            "video_id": db_video_id,
            "content": chunk["text"],
            "start_seconds": chunk["start_seconds"],
            "end_seconds": chunk["end_seconds"],
            "embedding": vector,
        })

    # Batch insert (Supabase handles this efficiently)
    supabase.table("chunks").insert(chunk_rows).execute()

    return len(chunk_rows)


def ingest_single_video_pg(video_id: str, user_id: str, api_key: str = None) -> Generator[str, None, None]:
    """Index a single YouTube video to pgvector."""
    supabase = get_supabase()

    yield f"Processing single video: {video_id}"

    # Fetch metadata
    yield "Fetching video info..."
    video_title, channel_name = fetch_video_metadata(video_id)
    yield f"{video_title} by {channel_name}"

    # Derive a handle from the channel name
    youtube_handle = f"@{channel_name.replace(' ', '')}"

    # Get or create channel + subscribe user
    channel = get_or_create_channel(supabase, youtube_handle, channel_name, user_id)

    # Check if already indexed
    indexed_ids = get_indexed_video_ids_pg(supabase, channel["id"])
    if video_id in indexed_ids:
        yield "This video is already indexed!"
        return

    # Get transcript
    yield "Fetching transcript..."
    chunks = get_transcript_chunks(video_id)
    if not chunks:
        yield "No transcript available for this video"
        return

    yield f"Found {len(chunks)} transcript chunks"

    # Index
    try:
        count = index_video_to_pg(supabase, video_id, video_title, channel_name, channel["id"], chunks, api_key)
        supabase.table("channels").update({
            "total_videos": channel.get("total_videos", 0) + 1,
            "indexed_at": "now()"
        }).eq("id", channel["id"]).execute()
        yield f"Indexed {count} clips from video"
    except Exception as e:
        yield f"Error indexing: {str(e)}"
        return

    yield "Complete!"


def ingest_channel_pg(channel_url: str, user_id: str, api_key: str = None) -> Generator[str, None, None]:
    """Index all videos from a YouTube channel to pgvector."""
    supabase = get_supabase()

    yield "Scanning channel for videos..."

    try:
        videos = list(scrapetube.get_channel(
            channel_url=channel_url,
            sort_by='oldest',
            sleep=1.5,
        ))
    except Exception as e:
        yield f"Error scanning channel: {str(e)}"
        return

    total_videos = len(videos)
    yield f"Found {total_videos} videos in channel"

    # Get channel name from first video
    channel_name = "Unknown Channel"
    if videos:
        first_video_id = videos[0].get('videoId')
        if first_video_id:
            _, channel_name = fetch_video_metadata(first_video_id)
    yield f"Channel: {channel_name}"

    # Extract handle from URL
    import re
    handle_match = re.search(r'youtube\.com/@([a-zA-Z0-9_-]+)', channel_url)
    youtube_handle = f"@{handle_match.group(1)}" if handle_match else f"@{channel_name.replace(' ', '')}"

    # Get or create channel + subscribe user
    channel = get_or_create_channel(supabase, youtube_handle, channel_name, user_id)
    channel_id = channel["id"]

    # Check already indexed
    indexed_ids = get_indexed_video_ids_pg(supabase, channel_id)
    yield f"Database contains {len(indexed_ids)} previously indexed videos"

    new_videos = [v for v in videos if v.get('videoId') not in indexed_ids]
    if not new_videos:
        yield "All videos already indexed! Nothing new to process."
        return

    yield f"{len(new_videos)} new videos to index"

    indexed_count = 0
    skipped_count = 0

    for i, video in enumerate(new_videos, 1):
        vid = video.get('videoId')
        title = extract_video_title(video)

        yield f"[{i}/{len(new_videos)}] Processing: {title[:50]}..."

        chunks = get_transcript_chunks(vid)
        if not chunks:
            yield f"   Skipped (no transcript available)"
            skipped_count += 1
            continue

        try:
            count = index_video_to_pg(supabase, vid, title, channel_name, channel_id, chunks, api_key)
            indexed_count += 1
            yield f"   Indexed {count} clips"
        except Exception as e:
            yield f"   Error indexing: {str(e)}"
            skipped_count += 1

        time.sleep(0.5)

    # Update channel stats
    supabase.table("channels").update({
        "total_videos": len(indexed_ids) + indexed_count,
        "indexed_at": "now()"
    }).eq("id", channel_id).execute()

    yield f"Complete! Indexed {indexed_count} videos ({skipped_count} skipped)"


def ingest_playlist_pg(playlist_id: str, user_id: str, api_key: str = None) -> Generator[str, None, None]:
    """Index all videos from a YouTube playlist to pgvector."""
    supabase = get_supabase()

    yield f"Scanning playlist: {playlist_id}"

    try:
        videos = list(scrapetube.get_playlist(playlist_id))
    except Exception as e:
        yield f"Error scanning playlist: {str(e)}"
        return

    total_videos = len(videos)
    yield f"Found {total_videos} videos in playlist"

    indexed_count = 0
    skipped_count = 0

    for i, video in enumerate(videos, 1):
        vid = video.get('videoId')
        title = extract_video_title(video)
        channel_name = extract_channel_name(video)

        yield f"[{i}/{total_videos}] Processing: {title[:50]}..."

        # Each video in a playlist might be from a different channel
        youtube_handle = f"@{channel_name.replace(' ', '')}"
        channel = get_or_create_channel(supabase, youtube_handle, channel_name, user_id)

        # Check if already indexed
        indexed_ids = get_indexed_video_ids_pg(supabase, channel["id"])
        if vid in indexed_ids:
            yield f"   Already indexed, skipping"
            continue

        chunks = get_transcript_chunks(vid)
        if not chunks:
            yield f"   Skipped (no transcript available)"
            skipped_count += 1
            continue

        try:
            count = index_video_to_pg(supabase, vid, title, channel_name, channel["id"], chunks, api_key)
            indexed_count += 1
            yield f"   Indexed {count} clips"

            supabase.table("channels").update({
                "total_videos": channel.get("total_videos", 0) + 1,
                "indexed_at": "now()"
            }).eq("id", channel["id"]).execute()
        except Exception as e:
            yield f"   Error indexing: {str(e)}"
            skipped_count += 1

        time.sleep(0.5)

    yield f"Complete! Indexed {indexed_count} videos ({skipped_count} skipped)"


def ingest_url_pg(url: str, user_id: str, api_key: str = None) -> Generator[str, None, None]:
    """Smart ingestion that auto-detects URL type. Writes to pgvector."""
    url_type, extracted_id = detect_url_type(url)

    yield f"Detected URL type: {url_type.upper()}"

    if url_type == 'channel':
        yield from ingest_channel_pg(url, user_id, api_key)
    elif url_type == 'playlist':
        yield from ingest_playlist_pg(extracted_id, user_id, api_key)
    elif url_type == 'video':
        yield from ingest_single_video_pg(extracted_id, user_id, api_key)
    else:
        yield "Could not detect URL type. Please provide a valid YouTube channel, playlist, or video URL."
```

**Step 2: Commit**

```bash
git add backend/ingest_pg.py
git commit -m "feat: add pgvector ingestion pipeline with shared-on-demand model"
```

---

## Task 5: New Search Engine (pgvector)

**Files:**
- Create: `backend/rag_pg.py`

**Step 1: Create `backend/rag_pg.py`**

```python
"""
rag_pg.py - Search Engine for Supabase/pgvector

Performs semantic similarity search scoped to the user's subscribed channels.
Uses pgvector for vector similarity with SQL filtering in a single query.
"""

import os
from typing import TypedDict
from dotenv import load_dotenv

from langchain_google_genai import GoogleGenerativeAIEmbeddings
from db import get_supabase

env_path = os.path.join(os.path.dirname(__file__), '..', '.env.local')
load_dotenv(env_path)

EMBEDDING_MODEL = "models/gemini-embedding-001"
SKIP_INTRO_SECONDS = 120

_embeddings_instance = None
_embeddings_api_key = None


class VideoClip(TypedDict):
    id: str
    videoId: str
    title: str
    channelName: str
    startSeconds: int
    endSeconds: int
    content: str
    thumbnailUrl: str


class SearchResult(TypedDict):
    answer: str
    relevantClips: list[VideoClip]


def get_embeddings(api_key: str = None) -> GoogleGenerativeAIEmbeddings:
    global _embeddings_instance, _embeddings_api_key

    key_to_use = api_key or os.getenv("GEMINI_API_KEY")
    if not key_to_use or key_to_use == "PLACEHOLDER_API_KEY":
        raise ValueError("No API key provided.")

    if _embeddings_instance is not None and _embeddings_api_key == key_to_use:
        return _embeddings_instance

    _embeddings_api_key = key_to_use
    _embeddings_instance = GoogleGenerativeAIEmbeddings(
        model=EMBEDDING_MODEL,
        google_api_key=key_to_use,
        task_type="RETRIEVAL_QUERY",
    )
    return _embeddings_instance


def search_pg(query: str, user_id: str, api_key: str = None, limit: int = 5) -> SearchResult:
    """
    Search indexed videos scoped to the user's subscribed channels.
    Uses pgvector similarity search with SQL join filtering.
    """
    supabase = get_supabase()
    embeddings = get_embeddings(api_key)

    # Embed the query
    query_vector = embeddings.embed_query(query)

    # pgvector similarity search scoped to user's channels
    # Using a Supabase RPC function for the vector search
    result = supabase.rpc("search_chunks", {
        "query_embedding": query_vector,
        "match_user_id": user_id,
        "match_limit": limit * 2,  # Get extra to filter intros
        "min_start_seconds": SKIP_INTRO_SECONDS,
    }).execute()

    rows = result.data or []

    clips: list[VideoClip] = []
    for i, row in enumerate(rows):
        if len(clips) >= limit:
            break

        clip: VideoClip = {
            "id": f"clip_{i}",
            "videoId": row["youtube_video_id"],
            "title": row["title"],
            "channelName": row["channel_name"],
            "startSeconds": row["start_seconds"],
            "endSeconds": row["end_seconds"],
            "content": row["content"],
            "thumbnailUrl": row["thumbnail_url"],
        }
        clips.append(clip)

    return {
        "answer": "",
        "relevantClips": clips,
    }


def get_library_pg(user_id: str) -> dict:
    """Get user's subscribed channels with their videos."""
    supabase = get_supabase()

    # Get user's channel subscriptions with channel details
    result = supabase.table("user_channels") \
        .select("channel_id, channels(id, name, youtube_handle, total_videos)") \
        .eq("user_id", user_id) \
        .execute()

    channels_list = []
    total_videos = 0
    total_clips = 0

    for row in (result.data or []):
        channel = row.get("channels")
        if not channel:
            continue

        # Get videos for this channel
        videos_result = supabase.table("videos") \
            .select("youtube_video_id, title, thumbnail_url, indexed_at") \
            .eq("channel_id", channel["id"]) \
            .execute()

        videos = []
        for v in (videos_result.data or []):
            # Get clip count
            clip_count_result = supabase.table("chunks") \
                .select("id", count="exact") \
                .eq("video_id", v.get("id", "")) \
                .execute()

            # Count clips via a separate query on video_id
            clips_result = supabase.rpc("count_chunks_by_youtube_video", {
                "vid": v["youtube_video_id"]
            }).execute()
            clip_count = clips_result.data if isinstance(clips_result.data, int) else 0

            videos.append({
                "videoId": v["youtube_video_id"],
                "title": v["title"],
                "thumbnailUrl": v["thumbnail_url"],
                "clipCount": clip_count,
                "indexedAt": v.get("indexed_at"),
            })

        total_videos += len(videos)
        channels_list.append({
            "name": channel["name"],
            "videoCount": len(videos),
            "videos": videos,
        })

    return {
        "channels": channels_list,
        "totalVideos": total_videos,
        "totalClips": total_clips,
    }
```

**Step 2: Add the search RPC function to Supabase**

Create `backend/supabase/migrations/002_search_function.sql`:

```sql
-- Vector similarity search scoped to user's subscribed channels
CREATE OR REPLACE FUNCTION search_chunks(
    query_embedding VECTOR(768),
    match_user_id UUID,
    match_limit INT DEFAULT 10,
    min_start_seconds INT DEFAULT 120
)
RETURNS TABLE (
    chunk_id UUID,
    content TEXT,
    start_seconds INT,
    end_seconds INT,
    youtube_video_id TEXT,
    title TEXT,
    channel_name TEXT,
    thumbnail_url TEXT,
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.id AS chunk_id,
        c.content,
        c.start_seconds,
        c.end_seconds,
        v.youtube_video_id,
        v.title,
        ch.name AS channel_name,
        v.thumbnail_url,
        1 - (c.embedding <=> query_embedding) AS similarity
    FROM chunks c
    JOIN videos v ON c.video_id = v.id
    JOIN channels ch ON v.channel_id = ch.id
    JOIN user_channels uc ON ch.id = uc.channel_id
    WHERE uc.user_id = match_user_id
      AND c.start_seconds >= min_start_seconds
    ORDER BY c.embedding <=> query_embedding
    LIMIT match_limit;
END;
$$;

-- Helper function to count chunks by youtube video ID
CREATE OR REPLACE FUNCTION count_chunks_by_youtube_video(vid TEXT)
RETURNS INT
LANGUAGE sql
AS $$
    SELECT COUNT(*)::INT
    FROM chunks c
    JOIN videos v ON c.video_id = v.id
    WHERE v.youtube_video_id = vid;
$$;
```

**Step 3: Run migration in Supabase SQL Editor**

**Step 4: Commit**

```bash
git add backend/rag_pg.py backend/supabase/migrations/002_search_function.sql
git commit -m "feat: add pgvector search engine with user-scoped similarity search"
```

---

## Task 6: Update FastAPI Server for Multi-User

**Files:**
- Modify: `backend/server.py`

**Step 1: Rewrite `backend/server.py` to use new pgvector modules and JWT auth**

Replace the imports and endpoints to use `ingest_pg`, `rag_pg`, and `db` modules. Key changes:

- All endpoints require JWT auth via `Depends(get_current_user)`
- Ingest endpoint checks quota before starting
- Search endpoint checks quota and scopes to user
- Library endpoint scoped to user's subscriptions
- New endpoints: `/api/usage`, `/api/settings/key`
- Delete endpoint removes user subscription (not global data unless orphaned)

The full server.py rewrite should:

1. Import from `db` (`get_current_user`, `get_supabase`, `get_user_profile`, `check_search_quota`, `check_index_quota`, `increment_search_usage`, `increment_index_usage`)
2. Import from `ingest_pg` (`ingest_url_pg`)
3. Import from `rag_pg` (`search_pg`, `get_library_pg`)
4. Add `user: dict = Depends(get_current_user)` to every endpoint
5. Add quota checking before search and ingest operations
6. Add `GET /api/usage` endpoint returning quota status
7. Add `PUT /api/settings/key` endpoint for encrypted API key storage
8. Health check stays public (no auth required)

**Step 2: Commit**

```bash
git add backend/server.py
git commit -m "feat: update server with JWT auth, quota enforcement, and pgvector endpoints"
```

---

## Task 7: Frontend - Add Supabase Auth

**Files:**
- Modify: `package.json` (add `@supabase/supabase-js`)
- Create: `src/lib/supabase.ts`
- Create: `src/contexts/AuthContext.tsx`
- Modify: `src/App.tsx` (wrap in AuthProvider, add login/logout)

**Step 1: Install Supabase JS client**

```bash
npm install @supabase/supabase-js
```

**Step 2: Create `src/lib/supabase.ts`**

```typescript
import { createClient } from '@supabase/supabase-js'

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY

if (!supabaseUrl || !supabaseAnonKey) {
    console.warn('Supabase environment variables not set')
}

export const supabase = createClient(supabaseUrl || '', supabaseAnonKey || '')
```

**Step 3: Create `src/contexts/AuthContext.tsx`**

```typescript
import { createContext, useContext, useEffect, useState, ReactNode } from 'react'
import { Session, User } from '@supabase/supabase-js'
import { supabase } from '../lib/supabase'

interface AuthContextType {
    user: User | null
    session: Session | null
    loading: boolean
    signInWithGoogle: () => Promise<void>
    signInWithGitHub: () => Promise<void>
    signOut: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
    const [user, setUser] = useState<User | null>(null)
    const [session, setSession] = useState<Session | null>(null)
    const [loading, setLoading] = useState(true)

    useEffect(() => {
        // Get initial session
        supabase.auth.getSession().then(({ data: { session } }) => {
            setSession(session)
            setUser(session?.user ?? null)
            setLoading(false)
        })

        // Listen for auth changes
        const { data: { subscription } } = supabase.auth.onAuthStateChange(
            (_event, session) => {
                setSession(session)
                setUser(session?.user ?? null)
                setLoading(false)
            }
        )

        return () => subscription.unsubscribe()
    }, [])

    const signInWithGoogle = async () => {
        await supabase.auth.signInWithOAuth({ provider: 'google' })
    }

    const signInWithGitHub = async () => {
        await supabase.auth.signInWithOAuth({ provider: 'github' })
    }

    const signOut = async () => {
        await supabase.auth.signOut()
    }

    return (
        <AuthContext.Provider value={{ user, session, loading, signInWithGoogle, signInWithGitHub, signOut }}>
            {children}
        </AuthContext.Provider>
    )
}

export function useAuth() {
    const context = useContext(AuthContext)
    if (!context) throw new Error('useAuth must be used within AuthProvider')
    return context
}
```

**Step 4: Update `src/App.tsx`**

Wrap the app in `<AuthProvider>`. Add a login gate: if not authenticated, show a login page. If authenticated, show the existing app.

**Step 5: Commit**

```bash
git add src/lib/supabase.ts src/contexts/AuthContext.tsx src/App.tsx package.json package-lock.json
git commit -m "feat: add Supabase auth with Google/GitHub OAuth"
```

---

## Task 8: Frontend - Update API Client for JWT

**Files:**
- Modify: `src/services/api.ts`

**Step 1: Update all API calls to attach JWT**

Every `fetch()` call needs the `Authorization: Bearer <token>` header. Import the Supabase client to get the current session token:

```typescript
import { supabase } from '../lib/supabase'

async function getAuthHeaders(): Promise<Record<string, string>> {
    const { data: { session } } = await supabase.auth.getSession()
    const headers: Record<string, string> = {
        'Content-Type': 'application/json',
    }
    if (session?.access_token) {
        headers['Authorization'] = `Bearer ${session.access_token}`
    }
    return headers
}
```

Update every API function to use `getAuthHeaders()` instead of manually building headers.

**Step 2: Move search history from localStorage to API**

Replace `saveSearchToHistory`, `getSearchHistory`, `clearSearchHistory`, `deleteSearchHistoryEntry` to call backend endpoints instead of localStorage. (Or keep localStorage as a cache with server sync -- simpler for now.)

**Step 3: Commit**

```bash
git add src/services/api.ts
git commit -m "feat: attach JWT auth headers to all API calls"
```

---

## Task 9: Frontend - Login Page & Auth UI

**Files:**
- Create: `src/components/LoginPage.tsx`
- Modify: `src/App.tsx` (route guard logic)
- Modify: `src/components/SettingsModal.tsx` (API key to server-side)

**Step 1: Create `src/components/LoginPage.tsx`**

A branded login page with Google and GitHub OAuth buttons. Follow the Botanical Brutalist design system from CLAUDE.md -- serif headline, mono buttons with offset shadows, warm cream background.

**Step 2: Update `src/App.tsx` route guard**

```typescript
// In App.tsx render:
if (loading) return <LoadingSpinner />
if (!user) return <LoginPage />
return <MainApp />  // existing app content
```

**Step 3: Update SettingsModal**

- Remove localStorage API key management
- Add a form that POSTs the key to `PUT /api/settings/key` (encrypted server-side)
- Show current usage quota from `GET /api/usage`

**Step 4: Commit**

```bash
git add src/components/LoginPage.tsx src/App.tsx src/components/SettingsModal.tsx
git commit -m "feat: add login page with OAuth and update settings for server-side key storage"
```

---

## Task 10: Cleanup & Remove ChromaDB

**Files:**
- Modify: `requirements.txt` (remove `langchain-chroma`)
- Delete: `backend/ingest.py` (replaced by `ingest_pg.py`) -- or rename
- Delete: `backend/rag.py` (replaced by `rag_pg.py`) -- or rename
- Modify: `backend/server.py` (update imports if not already done)
- Delete: `channel_chroma_db/` directory
- Modify: `docker-compose.yml` (update for new architecture)

Actually, keep the old files around but renamed (e.g., `ingest_chroma.py`, `rag_chroma.py`) until we've verified everything works end-to-end. Then delete them.

**Step 1: Rename old files**

```bash
git mv backend/ingest.py backend/ingest_chroma.py
git mv backend/rag.py backend/rag_chroma.py
git mv backend/ingest_pg.py backend/ingest.py
git mv backend/rag_pg.py backend/rag.py
```

**Step 2: Update imports in `backend/ingest.py`** (the new pgvector one)

Update the import `from ingest import ...` to `from ingest_chroma import ...` for the reused helper functions.

**Step 3: Remove ChromaDB from requirements**

Remove `langchain-chroma>=1.1.0` from `requirements.txt`.

**Step 4: Update `.gitignore`**

Remove `channel_chroma_db/` line (no longer used), add any new Supabase-related ignores.

**Step 5: Commit**

```bash
git add -A
git commit -m "refactor: remove ChromaDB, rename modules for pgvector backend"
```

---

## Task 11: End-to-End Testing

**No new files -- manual verification.**

**Step 1: Start Supabase**

Verify your Supabase project is running and schema is applied.

**Step 2: Start backend**

```bash
cd backend && python server.py
```

Verify it starts without import errors.

**Step 3: Start frontend**

```bash
npm run dev
```

**Step 4: Test auth flow**

1. Open browser, should see login page
2. Click "Sign in with Google" -- OAuth flow completes
3. Redirected back to app, now authenticated
4. Profile created in `profiles` table

**Step 5: Test ingestion**

1. Enter a YouTube video URL
2. Verify SSE streaming shows progress
3. Check Supabase: `channels`, `videos`, `chunks` tables populated
4. Check `user_channels` subscription created

**Step 6: Test search**

1. Search for something in the indexed video
2. Verify results return with correct video metadata
3. Verify results are scoped to subscribed channels only

**Step 7: Test shared-on-demand**

1. Create a second test account
2. Try indexing the same channel
3. Verify it instantly subscribes without re-indexing
4. Verify second user can search the content

**Step 8: Test quota metering**

1. With no BYOK key, perform searches
2. Verify `free_searches_today` increments
3. Verify usage is blocked at limit

---

## Task 12: Update Docker & Deployment Config

**Files:**
- Modify: `Dockerfile.backend`
- Modify: `docker-compose.yml`
- Modify: `nginx.conf` (if needed)

**Step 1: Update `Dockerfile.backend`**

Remove ChromaDB volume mount. Add Supabase env vars.

**Step 2: Update `docker-compose.yml`**

- Remove ChromaDB volume
- Add Supabase environment variables (from host env or `.env` file)
- Frontend build needs `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` at build time

**Step 3: Commit**

```bash
git add Dockerfile.backend docker-compose.yml nginx.conf
git commit -m "chore: update Docker config for Supabase backend"
```

---

## Summary

| Task | Description | Depends on |
|------|-------------|------------|
| 1 | Supabase setup + database schema | None |
| 2 | Backend dependencies + Supabase client | Task 1 |
| 3 | Migrate embedding model | None (can parallel with 1-2) |
| 4 | New ingestion pipeline (pgvector) | Tasks 1, 2, 3 |
| 5 | New search engine (pgvector) | Tasks 1, 2, 3 |
| 6 | Update FastAPI server | Tasks 2, 4, 5 |
| 7 | Frontend Supabase auth | Task 1 |
| 8 | Frontend API client JWT | Task 7 |
| 9 | Login page & auth UI | Tasks 7, 8 |
| 10 | Cleanup ChromaDB | Tasks 4, 5, 6 |
| 11 | End-to-end testing | All above |
| 12 | Docker & deployment | Task 11 |

**Parallelizable:** Tasks 3 + 7 can run alongside Tasks 1-2. Tasks 4 + 5 can be developed in parallel after their deps complete.
