"""Preview or import a legacy Chroma transcript corpus into hosted Supabase.

The default mode is a dry run. Applying writes canonical videos/chunks and grants
the supplied user access through user_videos. Applying with Gemini embeddings can
spend real model quota, so keep --apply explicit.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import secrets
import sqlite3
import sys
import time
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env.local")

DEFAULT_CHROMA_DB = ROOT / "backend" / "channel_chroma_db" / "chroma.sqlite3"
DEFAULT_EMBED_BATCH_SIZE = 64
INSERT_BATCH_SIZE = 50


@dataclass(frozen=True)
class LegacyChunk:
    legacy_id: int
    youtube_video_id: str
    title: str
    channel_name: str
    start_seconds: int
    end_seconds: int
    content: str
    thumbnail_url: str
    source_url: str
    embedding: list[float] | None = None


@dataclass(frozen=True)
class LegacyVideo:
    youtube_video_id: str
    title: str
    channel_name: str
    thumbnail_url: str
    source_url: str
    transcript_seconds: int
    chunk_count: int
    content_chars: int


def load_legacy_chunks(db_path: Path) -> list[LegacyChunk]:
    """Read Chroma metadata rows into normalized transcript chunks."""
    if not db_path.exists():
        raise FileNotFoundError(f"Legacy Chroma DB not found: {db_path}")

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            "SELECT id, key, string_value, int_value FROM embedding_metadata ORDER BY id"
        ).fetchall()
    finally:
        con.close()

    metadata_by_id: dict[int, dict[str, Any]] = defaultdict(dict)
    for row in rows:
        value = row["string_value"] if row["string_value"] is not None else row["int_value"]
        metadata_by_id[int(row["id"])][str(row["key"])] = value

    chunks: list[LegacyChunk] = []
    for legacy_id, metadata in sorted(metadata_by_id.items()):
        content = _clean_text(metadata.get("chroma:document"))
        youtube_video_id = _clean_text(metadata.get("video_id"))
        if not content or not youtube_video_id:
            continue

        title = _clean_text(metadata.get("title")) or f"YouTube video {youtube_video_id}"
        channel_name = _clean_text(metadata.get("channel_name")) or "Unknown Channel"
        start_seconds = _safe_int(metadata.get("start_seconds"))
        end_seconds = max(_safe_int(metadata.get("end_seconds")), start_seconds)
        thumbnail_url = (
            _clean_text(metadata.get("thumbnail_url"))
            or f"https://img.youtube.com/vi/{youtube_video_id}/mqdefault.jpg"
        )
        source_url = (
            _clean_text(metadata.get("source_url"))
            or f"https://www.youtube.com/watch?v={youtube_video_id}"
        )
        chunks.append(
            LegacyChunk(
                legacy_id=legacy_id,
                youtube_video_id=youtube_video_id,
                title=title,
                channel_name=channel_name,
                start_seconds=start_seconds,
                end_seconds=end_seconds,
                content=content,
                thumbnail_url=thumbnail_url,
                source_url=source_url,
            )
        )

    return chunks


def hydrate_chunks_with_chroma_embeddings(
    chunks: list[LegacyChunk],
    db_dir: Path | None = None,
) -> list[LegacyChunk]:
    """Attach persisted Chroma vectors to legacy chunks when available."""
    try:
        import chromadb
    except ImportError as exc:
        raise RuntimeError("chromadb is required to reuse legacy persisted embeddings") from exc

    db_dir = db_dir or DEFAULT_CHROMA_DB.parent
    client = chromadb.PersistentClient(path=str(db_dir))
    collection = client.get_collection("video_knowledge")
    result = collection.get(include=["embeddings", "documents", "metadatas"])
    ids = result.get("ids") or []
    documents = result.get("documents") or []
    metadatas = result.get("metadatas") or []
    embeddings = result.get("embeddings")
    if embeddings is None:
        raise RuntimeError("Legacy Chroma collection did not return embeddings")

    embedding_by_key: dict[tuple[str, int, int, str], list[float]] = {}
    for index, _embedding_id in enumerate(ids):
        metadata = metadatas[index] if index < len(metadatas) else {}
        document = documents[index] if index < len(documents) else ""
        vector = embeddings[index]
        if hasattr(vector, "tolist"):
            vector = vector.tolist()
        key = (
            _clean_text(metadata.get("video_id")),
            _safe_int(metadata.get("start_seconds")),
            _safe_int(metadata.get("end_seconds")),
            _clean_text(document),
        )
        if key[0] and key[3]:
            embedding_by_key[key] = [float(value) for value in vector]

    hydrated = []
    missing = 0
    for chunk in chunks:
        key = (
            chunk.youtube_video_id,
            chunk.start_seconds,
            chunk.end_seconds,
            chunk.content,
        )
        vector = embedding_by_key.get(key)
        if vector is None:
            missing += 1
            hydrated.append(chunk)
            continue
        hydrated.append(
            LegacyChunk(
                legacy_id=chunk.legacy_id,
                youtube_video_id=chunk.youtube_video_id,
                title=chunk.title,
                channel_name=chunk.channel_name,
                start_seconds=chunk.start_seconds,
                end_seconds=chunk.end_seconds,
                content=chunk.content,
                thumbnail_url=chunk.thumbnail_url,
                source_url=chunk.source_url,
                embedding=vector,
            )
        )
    if missing:
        raise RuntimeError(f"Missing legacy Chroma embeddings for {missing} chunks")
    return hydrated


def summarize_videos(chunks: list[LegacyChunk]) -> list[LegacyVideo]:
    """Group chunks by YouTube video and return import metadata."""
    grouped: dict[str, list[LegacyChunk]] = defaultdict(list)
    for chunk in chunks:
        grouped[chunk.youtube_video_id].append(chunk)

    videos = []
    for youtube_video_id, video_chunks in grouped.items():
        ordered = sorted(video_chunks, key=lambda chunk: (chunk.start_seconds, chunk.legacy_id))
        first = ordered[0]
        videos.append(
            LegacyVideo(
                youtube_video_id=youtube_video_id,
                title=first.title,
                channel_name=first.channel_name,
                thumbnail_url=first.thumbnail_url,
                source_url=first.source_url,
                transcript_seconds=max(chunk.end_seconds for chunk in ordered),
                chunk_count=len(ordered),
                content_chars=sum(len(chunk.content) for chunk in ordered),
            )
        )

    return sorted(videos, key=lambda video: (-video.chunk_count, video.title.lower()))


def build_manifest(
    db_path: Path,
    chunks: list[LegacyChunk],
    *,
    embed_batch_size: int = DEFAULT_EMBED_BATCH_SIZE,
    selected_video_ids: set[str] | None = None,
) -> dict:
    """Return a compact dry-run manifest with cost-relevant counts."""
    if selected_video_ids:
        chunks = [chunk for chunk in chunks if chunk.youtube_video_id in selected_video_ids]
    videos = summarize_videos(chunks)
    total_chars = sum(video.content_chars for video in videos)
    total_seconds = sum(video.transcript_seconds for video in videos)
    return {
        "source": str(db_path),
        "mode": "dry_run",
        "videoCount": len(videos),
        "chunkCount": sum(video.chunk_count for video in videos),
        "transcriptSeconds": total_seconds,
        "transcriptHours": round(total_seconds / 3600, 2),
        "contentChars": total_chars,
        "approxEmbeddingTokens": math.ceil(total_chars / 4),
        "embeddingBatchSize": embed_batch_size,
        "estimatedEmbeddingBatches": math.ceil(len(chunks) / embed_batch_size) if chunks else 0,
        "digestLlmCalls": 0,
        "notes": [
            "Dry run only; no Supabase rows or embeddings are written.",
            "Apply mode uses Gemini document embeddings unless the video already exists.",
            "Source knowledge extraction is intentionally skipped; run a separate digest workflow later.",
            "Access should be granted with user_videos so shared canonical rows stay user-scoped.",
        ],
        "videos": [asdict(video) for video in videos],
    }


def apply_import(
    chunks: list[LegacyChunk],
    *,
    user_id: str,
    api_key: str | None,
    selected_video_ids: set[str] | None = None,
    embed_batch_size: int = DEFAULT_EMBED_BATCH_SIZE,
    write_transcript_lines: bool = True,
    embed_batch_delay_seconds: float = 0.0,
) -> dict:
    """Write selected legacy chunks into Supabase with reused or fresh embeddings."""
    from backend.db import get_supabase
    from backend.ingest import get_indexed_video_pg, get_or_create_channel

    if selected_video_ids:
        chunks = [chunk for chunk in chunks if chunk.youtube_video_id in selected_video_ids]
    chunks_by_video: dict[str, list[LegacyChunk]] = defaultdict(list)
    for chunk in chunks:
        chunks_by_video[chunk.youtube_video_id].append(chunk)

    supabase = get_supabase()
    embedder = None

    imported = []
    reused = []
    total_videos = len(chunks_by_video)
    for video_index, (youtube_video_id, raw_chunks) in enumerate(
        sorted(chunks_by_video.items()), start=1
    ):
        ordered_chunks = sorted(
            raw_chunks, key=lambda chunk: (chunk.start_seconds, chunk.legacy_id)
        )
        first = ordered_chunks[0]
        print(
            f"[{video_index}/{total_videos}] {youtube_video_id} ({len(ordered_chunks)} chunks)",
            file=sys.stderr,
            flush=True,
        )
        existing_video = get_indexed_video_pg(supabase, youtube_video_id)
        existing_chunk_count = (
            _count_existing_chunks(supabase, existing_video["id"]) if existing_video else 0
        )
        if existing_video and 0 < existing_chunk_count < len(ordered_chunks):
            raise RuntimeError(
                f"Video {youtube_video_id} has {existing_chunk_count}/{len(ordered_chunks)} "
                "chunks in Supabase. Clean up or complete that partial import before retrying."
            )
        if existing_video and existing_chunk_count >= len(ordered_chunks):
            _grant_user_video_access(
                supabase,
                user_id,
                existing_video["id"],
                "shared_existing",
                first.source_url,
            )
            reused.append(
                {
                    "youtubeVideoId": youtube_video_id,
                    "videoDbId": existing_video["id"],
                    "chunkCount": len(ordered_chunks),
                }
            )
            continue

        if existing_video:
            video = existing_video
        else:
            channel = get_or_create_channel(
                supabase,
                _legacy_channel_handle(first.channel_name, youtube_video_id),
                first.channel_name,
                user_id,
            )
            video = _insert_video(supabase, channel["id"], first, ordered_chunks)
        if all(chunk.embedding is not None for chunk in ordered_chunks):
            vectors = [chunk.embedding or [] for chunk in ordered_chunks]
        else:
            if embedder is None:
                from langchain_google_genai import GoogleGenerativeAIEmbeddings

                from backend.config import get_embedding_dimensions, get_embedding_model

                key_to_use = api_key or os.getenv("GEMINI_API_KEY")
                if not key_to_use:
                    raise ValueError(
                        "GEMINI_API_KEY or --api-key is required when legacy embeddings are unavailable"
                    )
                embedder = GoogleGenerativeAIEmbeddings(
                    model=get_embedding_model(),
                    google_api_key=key_to_use,
                    task_type="RETRIEVAL_DOCUMENT",
                    output_dimensionality=get_embedding_dimensions(),
                )
            texts = [f"{first.title}\n\n{chunk.content}" for chunk in ordered_chunks]
            vectors = _embed_in_batches(
                embedder,
                texts,
                embed_batch_size,
                embed_batch_delay_seconds,
            )
        _insert_chunks(supabase, video["id"], ordered_chunks, vectors)
        if write_transcript_lines:
            _insert_transcript_lines(supabase, video["id"], ordered_chunks)
        _grant_user_video_access(supabase, user_id, video["id"], "agent", first.source_url)
        imported.append(
            {
                "youtubeVideoId": youtube_video_id,
                "videoDbId": video["id"],
                "chunkCount": len(ordered_chunks),
            }
        )

    return {
        "mode": "applied",
        "importedVideoCount": len(imported),
        "reusedVideoCount": len(reused),
        "importedChunkCount": sum(item["chunkCount"] for item in imported),
        "imported": imported,
        "reused": reused,
    }


def parse_video_ids(raw_values: list[str]) -> set[str]:
    """Parse repeated/comma-separated YouTube IDs."""
    ids: set[str] = set()
    for raw_value in raw_values:
        for item in raw_value.split(","):
            cleaned = item.strip()
            if cleaned:
                ids.add(cleaned)
    return ids


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_CHROMA_DB), help="Path to chroma.sqlite3.")
    parser.add_argument("--video-id", action="append", default=[], help="Limit to video ID(s).")
    parser.add_argument(
        "--limit-videos",
        type=int,
        default=0,
        help="Limit dry-run output to the largest N videos. Apply mode ignores this.",
    )
    parser.add_argument(
        "--export-manifest",
        help="Write the dry-run manifest JSON to this path.",
    )
    parser.add_argument("--apply", action="store_true", help="Write selected videos to Supabase.")
    parser.add_argument("--user-id", help="Supabase profile/user UUID to grant video access to.")
    parser.add_argument(
        "--create-eval-user",
        action="store_true",
        help=(
            "Create or reuse a dedicated Supabase Auth user for migration/eval access "
            "when --user-id is not supplied."
        ),
    )
    parser.add_argument(
        "--eval-user-email",
        default="embedmoments-migration-eval@local.embedmoments.dev",
        help="Email address for --create-eval-user. The generated password is not printed.",
    )
    parser.add_argument("--api-key", help="Gemini API key override for apply mode.")
    parser.add_argument(
        "--no-reuse-chroma-embeddings",
        action="store_true",
        help="Re-embed with Gemini instead of importing persisted 768-dim Chroma vectors.",
    )
    parser.add_argument(
        "--embed-batch-size",
        type=int,
        default=DEFAULT_EMBED_BATCH_SIZE,
        help="Number of transcript chunks to embed per Gemini batch.",
    )
    parser.add_argument(
        "--embed-batch-delay-seconds",
        type=float,
        default=0.0,
        help=(
            "Optional sleep between embedding batches. Free-tier Gemini embedding "
            "quotas may need roughly batch_size * 0.65 seconds."
        ),
    )
    parser.add_argument(
        "--skip-transcript-lines",
        action="store_true",
        help="Do not write transcript_lines in apply mode.",
    )
    args = parser.parse_args()

    db_path = Path(args.db)
    selected_ids = parse_video_ids(args.video_id)
    chunks = load_legacy_chunks(db_path)
    if args.apply and not args.no_reuse_chroma_embeddings:
        chunks = hydrate_chunks_with_chroma_embeddings(chunks, db_path.parent)
    manifest = build_manifest(
        db_path,
        chunks,
        embed_batch_size=args.embed_batch_size,
        selected_video_ids=selected_ids or None,
    )

    if args.limit_videos and not args.apply:
        manifest["videos"] = manifest["videos"][: args.limit_videos]
        manifest["videoOutputLimitedTo"] = args.limit_videos

    if args.export_manifest:
        Path(args.export_manifest).write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    if not args.apply:
        print(json.dumps(manifest, indent=2))
        return 0

    eval_user = None
    user_id = args.user_id
    if not user_id and args.create_eval_user:
        eval_user = ensure_eval_user(args.eval_user_email)
        user_id = eval_user["userId"]

    if not user_id:
        print("--user-id or --create-eval-user is required with --apply", file=sys.stderr)
        return 2

    result = apply_import(
        chunks,
        user_id=user_id,
        api_key=args.api_key,
        selected_video_ids=selected_ids or None,
        embed_batch_size=args.embed_batch_size,
        write_transcript_lines=not args.skip_transcript_lines,
        embed_batch_delay_seconds=max(0.0, args.embed_batch_delay_seconds),
    )
    result["grantUserId"] = user_id
    if eval_user:
        result["evalUser"] = eval_user
    print(json.dumps(result, indent=2))
    return 0


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split()).strip()


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _legacy_channel_handle(channel_name: str, youtube_video_id: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]", "", channel_name.replace(" ", ""))
    if not slug or slug.lower() == "unknownchannel":
        slug = f"legacy-{youtube_video_id}"
    return f"@{slug[:64]}"


def ensure_eval_user(email: str) -> dict:
    """Create or reuse a service-role managed Auth user for hosted migration evals."""
    from backend.db import get_supabase

    supabase = get_supabase()
    existing = _find_auth_user_by_email(supabase, email)
    created = False
    if existing:
        user_id = existing["id"]
    else:
        password = secrets.token_urlsafe(32)
        try:
            result = supabase.auth.admin.create_user(
                {
                    "email": email,
                    "password": password,
                    "email_confirm": True,
                    "user_metadata": {"full_name": "Memexai Migration Eval"},
                }
            )
        except Exception as exc:
            raise RuntimeError(
                "Could not create the migration eval user. If Supabase reports a database "
                "error, apply migration 017_auth_profile_trigger_search_path.sql and retry."
            ) from exc
        user = getattr(result, "user", result)
        user_id = getattr(user, "id", None) or user.get("id")
        created = True

    _ensure_profile_row(supabase, user_id)
    return {"userId": user_id, "email": email, "created": created}


def _find_auth_user_by_email(supabase: Any, email: str) -> dict | None:
    result = supabase.auth.admin.list_users()
    users = getattr(result, "users", result)
    for user in users or []:
        user_email = getattr(user, "email", None)
        if user_email == email:
            user_id = getattr(user, "id", None)
            return {"id": user_id, "email": user_email}
    return None


def _ensure_profile_row(supabase: Any, user_id: str) -> None:
    rows = supabase.table("profiles").select("id").eq("id", user_id).limit(1).execute().data or []
    if rows:
        return
    supabase.table("profiles").insert(
        {
            "id": user_id,
            "display_name": "Memexai Migration Eval",
            "avatar_url": "",
        }
    ).execute()


def _insert_video(supabase: Any, channel_id: str, first: LegacyChunk, chunks: list[LegacyChunk]):
    result = (
        supabase.table("videos")
        .insert(
            {
                "channel_id": channel_id,
                "youtube_video_id": first.youtube_video_id,
                "title": first.title,
                "thumbnail_url": first.thumbnail_url,
                "transcript_seconds": max(chunk.end_seconds for chunk in chunks),
            }
        )
        .execute()
    )
    return result.data[0]


def _count_existing_chunks(supabase: Any, video_db_id: str) -> int:
    result = supabase.table("chunks").select("id").eq("video_id", video_db_id).execute()
    return len(getattr(result, "data", None) or [])


def _embed_in_batches(
    embedder: Any,
    texts: list[str],
    batch_size: int,
    delay_seconds: float = 0.0,
) -> list[list[float]]:
    vectors: list[list[float]] = []
    for index in range(0, len(texts), batch_size):
        if index and delay_seconds:
            time.sleep(delay_seconds)
        print(
            f"  embedding batch {index // batch_size + 1}/{math.ceil(len(texts) / batch_size)}",
            file=sys.stderr,
            flush=True,
        )
        vectors.extend(
            _embed_batch_with_retry(
                embedder,
                texts[index : index + batch_size],
            )
        )
    return vectors


def _embed_batch_with_retry(
    embedder: Any,
    batch: list[str],
    *,
    max_attempts: int = 4,
) -> list[list[float]]:
    for attempt in range(1, max_attempts + 1):
        try:
            return embedder.embed_documents(batch)
        except Exception:
            if attempt >= max_attempts:
                raise
            time.sleep(35 * attempt)
    return []


def _insert_chunks(
    supabase: Any,
    video_db_id: str,
    chunks: list[LegacyChunk],
    vectors: list[list[float]],
) -> None:
    rows = [
        {
            "video_id": video_db_id,
            "content": chunk.content,
            "start_seconds": chunk.start_seconds,
            "end_seconds": chunk.end_seconds,
            "embedding": vector,
        }
        for chunk, vector in zip(chunks, vectors)
    ]
    for index in range(0, len(rows), INSERT_BATCH_SIZE):
        supabase.table("chunks").insert(rows[index : index + INSERT_BATCH_SIZE]).execute()


def _insert_transcript_lines(supabase: Any, video_db_id: str, chunks: list[LegacyChunk]) -> None:
    rows = [
        {
            "video_id": video_db_id,
            "content": chunk.content,
            "start_seconds": chunk.start_seconds,
            "end_seconds": chunk.end_seconds,
            "source": "youtube_caption",
            "metadata": {"granularity": "legacy_chroma_chunk", "legacy_id": chunk.legacy_id},
        }
        for chunk in chunks
    ]
    for index in range(0, len(rows), INSERT_BATCH_SIZE):
        supabase.table("transcript_lines").insert(rows[index : index + INSERT_BATCH_SIZE]).execute()


def _grant_user_video_access(
    supabase: Any,
    user_id: str,
    video_db_id: str,
    access_source: str,
    source_url: str,
) -> None:
    supabase.table("user_videos").upsert(
        {
            "user_id": user_id,
            "video_id": video_db_id,
            "access_source": access_source,
            "source_url": source_url,
        },
        on_conflict="user_id,video_id",
    ).execute()


if __name__ == "__main__":
    raise SystemExit(main())
