"""
server.py - FastAPI Backend for ClipSeek

Provides REST API for the React frontend:
- GET  /              - Health check (public)
- GET  /api/library   - User's indexed channels & videos (auth)
- POST /api/ingest    - Index a YouTube channel (SSE stream, auth)
- POST /api/search    - Search indexed content (auth)
- GET  /api/transcript/{video_id} - Download SRT transcript (auth)
- DELETE /api/video/{video_id}    - Remove a video (auth)
- GET  /api/usage     - Quota status (auth)
- GET  /api/profile   - User profile (auth)
- PUT  /api/settings/key   - Save Gemini API key (auth)
- DELETE /api/settings/key - Remove Gemini API key (auth)

Run with: python server.py
Or: uvicorn server:app --reload --host 0.0.0.0 --port 8000

Updated: 2026-02-28
"""

import os
import asyncio
from typing import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel

# Import pgvector-backed modules
from ingest_pg import ingest_url_pg
from rag_pg import search_pg, get_library_pg, delete_video_pg, get_video_transcript_pg
from db import (
    get_current_user,
    get_supabase,
    get_user_profile,
    check_search_quota,
    check_index_quota,
    increment_search_usage,
    increment_index_usage,
    get_user_api_key,
)


# Pydantic models for request/response validation
class IngestRequest(BaseModel):
    url: str


class SearchRequest(BaseModel):
    query: str
    limit: int = 5  # Default to 5 results, frontend can override


class ApiKeyRequest(BaseModel):
    api_key: str


# Lifespan handler (replaces deprecated on_startup/on_shutdown)
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("[ClipSeek] Backend Starting...")
    print("   API Docs: http://localhost:8080/docs")
    print("   Health:   http://localhost:8080/")
    yield
    # Shutdown
    print("[ClipSeek] Backend Shutting Down...")


# Create FastAPI app
app = FastAPI(
    title="ClipSeek API",
    description="Intelligent YouTube Video Search powered by Gemini 2.0 Flash",
    version="2.0.0",
    lifespan=lifespan
)

# CORS middleware for frontend
# In development, allow all origins. In production, restrict this.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # React dev server and production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Public endpoints
# ---------------------------------------------------------------------------

@app.get("/")
async def health_check():
    """
    Health check endpoint.
    Frontend polls this to show "Backend Online" status.
    Also reports if server has API key configured.
    """
    has_api_key = bool(os.getenv("GEMINI_API_KEY"))
    return {
        "status": "ok",
        "message": "ClipSeek Backend is running",
        "hasApiKey": has_api_key
    }


# ---------------------------------------------------------------------------
# Authenticated endpoints
# ---------------------------------------------------------------------------

@app.get("/api/library")
async def library_endpoint(user: dict = Depends(get_current_user)):
    """
    Get the authenticated user's indexed videos organized by channel.

    Returns:
        {
            "channels": [{"name": "...", "videoCount": N, "videos": [...]}],
            "totalVideos": N,
            "totalClips": N
        }
    """
    user_id = user["sub"]
    return get_library_pg(user_id)


@app.delete("/api/video/{video_id}")
async def delete_video_endpoint(video_id: str, user: dict = Depends(get_current_user)):
    """
    Delete a video and all its clips from the database.
    Only works if the user is subscribed to the channel owning this video.

    Args:
        video_id: YouTube video ID to delete

    Returns:
        {"deleted": true/false, ...}
    """
    user_id = user["sub"]
    return delete_video_pg(video_id, user_id)


def format_srt_timestamp(seconds: int) -> str:
    """Convert seconds to SRT timestamp format (HH:MM:SS,mmm)."""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d},000"


@app.get("/api/transcript/{video_id}")
async def transcript_endpoint(
    video_id: str,
    format: str = "srt",
    user: dict = Depends(get_current_user),
):
    """
    Download transcript for a video as SRT file.

    Args:
        video_id: YouTube video ID
        format: Output format (currently only 'srt' supported)

    Returns:
        SRT file download
    """
    chunks = get_video_transcript_pg(video_id)

    if not chunks:
        raise HTTPException(status_code=404, detail="Video not found or has no transcript")

    # Build SRT content
    srt_lines = []
    for i, chunk in enumerate(chunks, 1):
        start_ts = format_srt_timestamp(chunk['start_seconds'])
        end_ts = format_srt_timestamp(chunk['end_seconds'])
        text = chunk['content'].strip()

        srt_lines.append(f"{i}")
        srt_lines.append(f"{start_ts} --> {end_ts}")
        srt_lines.append(text)
        srt_lines.append("")  # Blank line between entries

    srt_content = "\n".join(srt_lines)

    # Sanitize filename
    safe_title = video_id  # We don't have title in the transcript response
    filename = f"{safe_title}.srt"

    return Response(
        content=srt_content,
        media_type="text/plain",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


@app.post("/api/ingest")
async def ingest_endpoint(request: IngestRequest, user: dict = Depends(get_current_user)):
    """
    Index a YouTube channel, playlist, or single video.

    Uses Server-Sent Events (SSE) to stream progress to the frontend.
    The frontend displays these messages in a terminal-style log view.

    SSE Format:
        data: Scanning channel for videos...
        data: Found 50 videos in channel
        data: [DONE]
    """
    user_id = user["sub"]

    # Determine API key: user's stored key or server fallback
    supabase = get_supabase()
    profile = get_user_profile(supabase, user_id)
    user_api_key = profile.get("api_key_enc")
    api_key = user_api_key or os.getenv("GEMINI_API_KEY")
    used_own_key = bool(user_api_key)

    async def generate_events() -> AsyncGenerator[str, None]:
        try:
            # Run the synchronous ingest pipeline in a thread pool
            # to avoid blocking the async event loop
            loop = asyncio.get_event_loop()

            def run_ingestion():
                return list(ingest_url_pg(request.url, user_id, api_key))

            messages = await loop.run_in_executor(None, run_ingestion)

            for message in messages:
                yield f"data: {message}\n\n"
                # Small delay for frontend to render each message
                await asyncio.sleep(0.05)

            # Log usage after successful ingestion
            # Count indexed videos from the messages (rough heuristic)
            indexed_count = sum(
                1 for m in messages if "Indexed" in m and "clips" in m
            )
            if indexed_count > 0:
                try:
                    increment_index_usage(supabase, user_id, indexed_count, used_own_key)
                except Exception as usage_err:
                    print(f"[WARN] Failed to log index usage: {usage_err}")

            # Signal completion
            yield "data: [DONE]\n\n"

        except Exception as e:
            yield f"data: Error: {str(e)}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )


@app.post("/api/search", response_model=None)
async def search_endpoint(
    request: SearchRequest,
    user: dict = Depends(get_current_user),
) -> dict:
    """
    Search indexed videos using semantic similarity.

    Returns:
        {
            "answer": "",
            "relevantClips": [...]
        }
    """
    user_id = user["sub"]

    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    # Get user profile and check quota
    supabase = get_supabase()
    profile = get_user_profile(supabase, user_id)

    if not check_search_quota(profile):
        raise HTTPException(
            status_code=429,
            detail="Daily search limit reached. Add your own Gemini API key in Settings to get unlimited searches."
        )

    # Determine API key: user's stored key or server fallback
    user_api_key = profile.get("api_key_enc")
    api_key = user_api_key or os.getenv("GEMINI_API_KEY")
    used_own_key = bool(user_api_key)

    try:
        # Run the synchronous search in a thread pool
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: search_pg(request.query, user_id, api_key, request.limit)
        )

        # Log usage after successful search
        try:
            increment_search_usage(supabase, user_id, used_own_key)
        except Exception as usage_err:
            print(f"[WARN] Failed to log search usage: {usage_err}")

        return result
    except ValueError as e:
        # API key not set or other config error
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


# ---------------------------------------------------------------------------
# User profile & settings
# ---------------------------------------------------------------------------

@app.get("/api/profile")
async def profile_endpoint(user: dict = Depends(get_current_user)):
    """Get user profile info."""
    user_id = user["sub"]
    supabase = get_supabase()
    profile = get_user_profile(supabase, user_id)
    return {
        "id": profile["id"],
        "displayName": profile.get("display_name", "User"),
        "avatarUrl": profile.get("avatar_url", ""),
        "hasOwnKey": bool(profile.get("api_key_enc")),
    }


@app.get("/api/usage")
async def usage_endpoint(user: dict = Depends(get_current_user)):
    """Returns the user's current quota status."""
    user_id = user["sub"]
    supabase = get_supabase()
    profile = get_user_profile(supabase, user_id)
    has_own_key = bool(profile.get("api_key_enc"))
    return {
        "searchesUsedToday": profile.get("free_searches_today", 0),
        "searchLimit": 20,
        "indexesUsedThisMonth": profile.get("free_indexes_this_month", 0),
        "indexLimit": 50,
        "hasOwnKey": has_own_key,
    }


@app.put("/api/settings/key")
async def save_api_key(request: ApiKeyRequest, user: dict = Depends(get_current_user)):
    """Save or update the user's Gemini API key."""
    user_id = user["sub"]
    supabase = get_supabase()
    supabase.table("profiles").update({
        "api_key_enc": request.api_key
    }).eq("id", user_id).execute()
    return {"success": True}


@app.delete("/api/settings/key")
async def delete_api_key(user: dict = Depends(get_current_user)):
    """Remove the user's stored Gemini API key."""
    user_id = user["sub"]
    supabase = get_supabase()
    supabase.table("profiles").update({
        "api_key_enc": None
    }).eq("id", user_id).execute()
    return {"success": True}


# Run with uvicorn if executed directly
if __name__ == "__main__":
    import uvicorn
    import sys
    import io

    # Fix Windows console encoding for Unicode
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

    print("\n" + "=" * 60)
    print("  ClipSeek Backend")
    print("  Intelligent YouTube Video Search")
    print("=" * 60 + "\n")

    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8080,
        reload=False,  # Disable to preserve singleton state (restart manually when needed)
        log_level="warning"  # Suppress routine request logs
    )
