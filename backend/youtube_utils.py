"""Shared YouTube URL, metadata, and transcript helpers."""

from __future__ import annotations

import json
import re
import time
import urllib.request
from dataclasses import dataclass
from typing import Optional
from urllib.parse import parse_qs, urlparse

from youtube_transcript_api import YouTubeTranscriptApi

CHUNK_SIZE_SECONDS = 60
CHUNK_OVERLAP_SECONDS = 12
CHUNK_MAX_SECONDS = 75


@dataclass(frozen=True)
class TranscriptFetchResult:
    chunks: list[dict]
    skip_reason: str | None = None
    error: str | None = None


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
        chunks.append(
            {
                "text": chunk_text,
                "start_seconds": int(current_entries[0]["start"]),
                "end_seconds": int(chunk_end),
            }
        )

        overlap_start = chunk_end - overlap_seconds
        overlap_entries = [item for item in current_entries if _snippet_end(item) > overlap_start]
        current_entries = overlap_entries if len(overlap_entries) < len(current_entries) else []

    if current_entries:
        chunks.append(
            {
                "text": " ".join(item["text"] for item in current_entries),
                "start_seconds": int(current_entries[0]["start"]),
                "end_seconds": int(_snippet_end(current_entries[-1])),
            }
        )

    return chunks


def classify_transcript_error(exc: Exception) -> str:
    """Map youtube-transcript-api failures into stable hosted skip reasons."""
    name = exc.__class__.__name__.lower()
    message = str(exc).lower()
    combined = f"{name} {message}"

    if "disabled" in combined:
        return "captions_disabled"
    if "notranscript" in combined or "no transcript" in combined:
        return "captions_unavailable"
    if "unavailable" in combined or "video unavailable" in combined:
        return "video_unavailable"
    if "private" in combined:
        return "private_video"
    if "too many" in combined or "ratelimit" in combined or "rate limit" in combined:
        return "rate_limited"
    if "blocked" in combined or "forbidden" in combined:
        return "request_blocked"
    return "transcript_fetch_error"


def describe_transcript_skip(reason: str, video_id: str) -> str:
    descriptions = {
        "captions_disabled": "captions are disabled",
        "captions_unavailable": "captions are unavailable",
        "video_unavailable": "video is unavailable",
        "private_video": "video is private or restricted",
        "rate_limited": "transcript service rate limited the request",
        "request_blocked": "transcript request was blocked",
        "empty_transcript": "transcript returned no usable text",
        "transcript_fetch_error": "transcript fetch failed",
    }
    return f"{descriptions.get(reason, 'transcript unavailable')} for {video_id}"


def fetch_transcript_chunks(video_id: str) -> TranscriptFetchResult:
    """Get transcript chunks plus a stable skip reason when unavailable."""
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            api = YouTubeTranscriptApi()
            fetched = api.fetch(video_id)
            transcript = [
                {"text": snippet.text, "start": snippet.start, "duration": snippet.duration}
                for snippet in fetched
            ]
            if not transcript:
                return TranscriptFetchResult([], "empty_transcript")
            chunks = chunk_transcript_entries(transcript)
            if not chunks:
                return TranscriptFetchResult([], "empty_transcript")
            return TranscriptFetchResult(chunks)
        except Exception as exc:
            last_error = exc
            if attempt == 0:
                time.sleep(0.5)
                continue
            reason = classify_transcript_error(exc)
            return TranscriptFetchResult([], reason, str(exc))

    reason = classify_transcript_error(last_error) if last_error else "transcript_fetch_error"
    return TranscriptFetchResult([], reason, str(last_error) if last_error else None)


def get_transcript_chunks(video_id: str) -> list[dict]:
    """Get transcript and split it into sentence-aware overlapping chunks."""
    return fetch_transcript_chunks(video_id).chunks


def detect_url_type(url: str) -> tuple[str, Optional[str]]:
    """Detect the type of YouTube URL and extract the relevant ID."""
    normalized_url = _normalize_youtube_url(url)
    if _is_channel_handle(normalized_url):
        return ("channel", f"https://www.youtube.com/{normalized_url}")

    parsed = urlparse(normalized_url)
    hostname = parsed.netloc.lower()
    path = parsed.path.rstrip("/")
    query = parse_qs(parsed.query)

    if not _is_supported_youtube_host(hostname):
        return ("unknown", None)

    video_id = _first_query_value(query, "v")
    playlist_id = _first_query_value(query, "list")
    if video_id and _is_youtube_video_id(video_id):
        return ("video", video_id)

    if _is_youtu_be_host(hostname):
        short_id = path.strip("/").split("/", 1)[0]
        if _is_youtube_video_id(short_id):
            return ("video", short_id)

    path_video_match = re.search(
        r"^/(?:embed|v|shorts|live)/([a-zA-Z0-9_-]{11})(?:$|/)",
        path,
    )
    if path_video_match:
        return ("video", path_video_match.group(1))

    if playlist_id and (path == "/playlist" or not _is_youtube_video_id(video_id)):
        return ("playlist", playlist_id)

    channel_patterns = [
        r"^/@[a-zA-Z0-9_.-]+(?:$|/)",
        r"^/channel/[a-zA-Z0-9_-]+(?:$|/)",
        r"^/c/[a-zA-Z0-9_-]+(?:$|/)",
        r"^/user/[a-zA-Z0-9_-]+(?:$|/)",
    ]
    for pattern in channel_patterns:
        if re.search(pattern, path):
            return ("channel", normalized_url)

    return ("unknown", None)


def _normalize_youtube_url(url: str) -> str:
    """Add a scheme for common pasted YouTube URLs while leaving other text alone."""
    stripped = str(url or "").strip()
    if not stripped:
        return ""
    if _is_channel_handle(stripped):
        return stripped
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", stripped):
        return stripped
    if re.match(r"^(?:www\.|m\.|music\.)?youtube\.com(?:/|$)", stripped) or re.match(
        r"^(?:www\.)?youtu\.be(?:/|$)", stripped
    ):
        return f"https://{stripped}"
    return stripped


def _is_supported_youtube_host(hostname: str) -> bool:
    return _is_youtu_be_host(hostname) or hostname in {
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
        "music.youtube.com",
    }


def _is_youtu_be_host(hostname: str) -> bool:
    return hostname in {"youtu.be", "www.youtu.be"}


def _is_channel_handle(value: str) -> bool:
    return bool(re.fullmatch(r"@[a-zA-Z0-9_.-]+", value.strip()))


def _first_query_value(query: dict[str, list[str]], key: str) -> str | None:
    values = query.get(key)
    if not values:
        return None
    value = values[0].strip()
    return value or None


def _is_youtube_video_id(value: str | None) -> bool:
    return bool(value and re.fullmatch(r"[a-zA-Z0-9_-]{11}", value))
