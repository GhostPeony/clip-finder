"""Shared YouTube URL, metadata, and transcript helpers."""

from __future__ import annotations

import json
import re
import time
import urllib.request
from typing import Optional

from youtube_transcript_api import YouTubeTranscriptApi

CHUNK_SIZE_SECONDS = 60
CHUNK_OVERLAP_SECONDS = 12
CHUNK_MAX_SECONDS = 75


def extract_video_title(video: dict) -> str:
    """Safely extract a video title from a scrapetube response."""
    try:
        title_obj = video.get("title", {})
        if isinstance(title_obj, dict):
            runs = title_obj.get("runs", [])
            if runs:
                return runs[0].get("text", "Unknown Title")
        return str(title_obj) if title_obj else "Unknown Title"
    except Exception:
        return "Unknown Title"


def extract_channel_name(video: dict) -> str:
    """Safely extract a channel name from a scrapetube response."""
    try:
        for key in ("ownerText", "longBylineText", "shortBylineText"):
            value = video.get(key, {})
            if isinstance(value, dict):
                runs = value.get("runs", [])
                if runs:
                    return runs[0].get("text", "Unknown Channel")
        return "Unknown Channel"
    except Exception:
        return "Unknown Channel"


def fetch_video_metadata(video_id: str) -> tuple[str, str]:
    """Fetch video title and channel name using YouTube oEmbed."""
    try:
        url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read().decode())
            return (
                data.get("title", f"Video {video_id}"),
                data.get("author_name", "Unknown Channel"),
            )
    except Exception:
        return (f"Video {video_id}", "Unknown Channel")


def _snippet_end(entry: dict) -> float:
    return float(entry.get("start", 0)) + float(entry.get("duration", 0))


def _chunk_span(entries: list[dict]) -> float:
    if not entries:
        return 0
    return _snippet_end(entries[-1]) - float(entries[0].get("start", 0))


def _is_sentence_boundary(text: str) -> bool:
    return text.rstrip().endswith((".", "!", "?", "…"))


def chunk_transcript_entries(
    transcript: list[dict],
    chunk_seconds: int = CHUNK_SIZE_SECONDS,
    overlap_seconds: int = CHUNK_OVERLAP_SECONDS,
    max_seconds: int = CHUNK_MAX_SECONDS,
) -> list[dict]:
    """Split timestamped transcript entries into sentence-aware chunks with overlap."""
    chunks = []
    current_entries: list[dict] = []

    for entry in transcript:
        text = entry.get("text", "").strip()
        if not text:
            continue

        normalized = {
            "text": text,
            "start": float(entry.get("start", 0)),
            "duration": float(entry.get("duration", 0)),
        }
        current_entries.append(normalized)

        chunk_text = " ".join(item["text"] for item in current_entries)
        duration = _chunk_span(current_entries)
        should_close = duration >= chunk_seconds and (
            _is_sentence_boundary(chunk_text) or duration >= max_seconds
        )
        if not should_close:
            continue

        chunk_end = _snippet_end(current_entries[-1])
        chunks.append({
            "text": chunk_text,
            "start_seconds": int(current_entries[0]["start"]),
            "end_seconds": int(chunk_end),
        })

        overlap_start = chunk_end - overlap_seconds
        overlap_entries = [
            item for item in current_entries if _snippet_end(item) > overlap_start
        ]
        current_entries = overlap_entries if len(overlap_entries) < len(current_entries) else []

    if current_entries:
        chunks.append({
            "text": " ".join(item["text"] for item in current_entries),
            "start_seconds": int(current_entries[0]["start"]),
            "end_seconds": int(_snippet_end(current_entries[-1])),
        })

    return chunks


def get_transcript_chunks(video_id: str) -> list[dict]:
    """Get transcript and split it into sentence-aware overlapping chunks."""
    for attempt in range(2):
        try:
            api = YouTubeTranscriptApi()
            fetched = api.fetch(video_id)
            transcript = [
                {"text": snippet.text, "start": snippet.start, "duration": snippet.duration}
                for snippet in fetched
            ]
            if not transcript:
                return []
            return chunk_transcript_entries(transcript)
        except Exception:
            if attempt == 0:
                time.sleep(0.5)
                continue
            return []


def detect_url_type(url: str) -> tuple[str, Optional[str]]:
    """Detect the type of YouTube URL and extract the relevant ID."""
    playlist_patterns = [
        r"[?&]list=([a-zA-Z0-9_-]+)",
        r"youtube\.com/playlist\?list=([a-zA-Z0-9_-]+)",
    ]

    video_patterns = [
        r"[?&]v=([a-zA-Z0-9_-]{11})",
        r"youtu\.be/([a-zA-Z0-9_-]{11})",
        r"youtube\.com/embed/([a-zA-Z0-9_-]{11})",
        r"youtube\.com/v/([a-zA-Z0-9_-]{11})",
        r"youtube\.com/shorts/([a-zA-Z0-9_-]{11})",
    ]

    channel_patterns = [
        r"youtube\.com/@([a-zA-Z0-9_.-]+)",
        r"youtube\.com/channel/([a-zA-Z0-9_-]+)",
        r"youtube\.com/c/([a-zA-Z0-9_-]+)",
        r"youtube\.com/user/([a-zA-Z0-9_-]+)",
    ]

    for pattern in playlist_patterns:
        match = re.search(pattern, url)
        if match:
            return ("playlist", match.group(1))

    for pattern in video_patterns:
        match = re.search(pattern, url)
        if match:
            return ("video", match.group(1))

    for pattern in channel_patterns:
        if re.search(pattern, url):
            return ("channel", url)

    return ("unknown", None)
