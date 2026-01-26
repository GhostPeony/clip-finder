"""
server.py - FastAPI Backend for ClipSeek

Provides REST API for the React frontend:
- GET  /          - Health check
- POST /api/ingest - Index a YouTube channel (SSE stream)
- POST /api/search - Search indexed content (JSON)

Run with: python server.py
Or: uvicorn server:app --reload --host 0.0.0.0 --port 8000

Updated: 2025-12-28
"""

import os
import asyncio
from typing import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# Import our modules
from ingest import ingest_url, get_library, delete_video, get_video_transcript, rename_channel
from rag import search, SearchResult


# Pydantic models for request/response validation
class IngestRequest(BaseModel):
    url: str


class SearchRequest(BaseModel):
    query: str
    limit: int = 5  # Default to 5 results, frontend can override


class RenameChannelRequest(BaseModel):
    old_name: str
    new_name: str


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
    version="1.0.0",
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


@app.get("/api/library")
async def library_endpoint():
    """
    Get all indexed videos organized by channel.

    Returns:
        {
            "channels": [{"name": "...", "videoCount": N, "videos": [...]}],
            "totalVideos": N,
            "totalClips": N
        }
    """
    return get_library()


@app.delete("/api/video/{video_id}")
async def delete_video_endpoint(video_id: str):
    """
    Delete a video and all its clips from the database.

    Args:
        video_id: YouTube video ID to delete

    Returns:
        {"success": true/false, "deletedClips": N}
    """
    return delete_video(video_id)


@app.post("/api/channel/rename")
async def rename_channel_endpoint(request: RenameChannelRequest):
    """
    Rename a channel in the database.

    Updates the channel_name metadata on all clips belonging to the channel.
    Useful for fixing "Unknown Channel" entries after indexing.

    Args:
        old_name: Current channel name to find
        new_name: New channel name to set

    Returns:
        {"success": true/false, "updatedClips": N, "oldName": "...", "newName": "..."}
    """
    return rename_channel(request.old_name, request.new_name)


def format_srt_timestamp(seconds: int) -> str:
    """Convert seconds to SRT timestamp format (HH:MM:SS,mmm)."""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d},000"


@app.get("/api/transcript/{video_id}")
async def transcript_endpoint(video_id: str, format: str = "srt"):
    """
    Download transcript for a video as SRT file.

    Args:
        video_id: YouTube video ID
        format: Output format (currently only 'srt' supported)

    Returns:
        SRT file download
    """
    result = get_video_transcript(video_id)

    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error", "Video not found"))

    chunks = result.get("chunks", [])
    title = result.get("title", video_id)

    # Build SRT content
    srt_lines = []
    for i, chunk in enumerate(chunks, 1):
        start_ts = format_srt_timestamp(chunk['start_seconds'])
        end_ts = format_srt_timestamp(chunk['end_seconds'])
        text = chunk['text'].strip()

        srt_lines.append(f"{i}")
        srt_lines.append(f"{start_ts} --> {end_ts}")
        srt_lines.append(text)
        srt_lines.append("")  # Blank line between entries

    srt_content = "\n".join(srt_lines)

    # Sanitize filename
    safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()[:50]
    filename = f"{safe_title}_{video_id}.srt"

    from fastapi.responses import Response
    return Response(
        content=srt_content,
        media_type="text/plain",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


@app.post("/api/ingest")
async def ingest_endpoint(request: IngestRequest):
    """
    Index a YouTube channel.

    Uses Server-Sent Events (SSE) to stream progress to the frontend.
    The frontend displays these messages in a terminal-style log view.

    SSE Format:
        data: 🔍 Scanning channel...
        data: 📊 Found 50 videos
        data: [DONE]
    """
    async def generate_events() -> AsyncGenerator[str, None]:
        try:
            # Run the synchronous ingest_channel in a thread pool
            # to avoid blocking the async event loop
            loop = asyncio.get_event_loop()

            # We need to iterate through the generator properly
            # Since ingest_channel is a sync generator, we process it in chunks
            def run_ingestion():
                return list(ingest_url(request.url))

            messages = await loop.run_in_executor(None, run_ingestion)

            for message in messages:
                yield f"data: {message}\n\n"
                # Small delay for frontend to render each message
                await asyncio.sleep(0.05)

            # Signal completion
            yield "data: [DONE]\n\n"

        except Exception as e:
            yield f"data: ❌ Error: {str(e)}\n\n"
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
    x_api_key: str = Header(None, alias="X-API-Key")
) -> dict:
    """
    Search indexed videos and generate an answer.

    Headers:
        X-API-Key: Optional user-provided Gemini API key (BYOK)

    Returns:
        {
            "answer": "The creator explains... [[clip_0]] ...",
            "relevantClips": [...]
        }
    """
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    try:
        # Run the synchronous search in a thread pool
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: search(request.query, api_key=x_api_key, limit=request.limit)
        )
        return result
    except ValueError as e:
        # API key not set or other config error
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


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
