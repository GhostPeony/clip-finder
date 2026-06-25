"""Transcript-derived source knowledge extraction and persistence."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings

try:
    from .brain_sync import queue_brain_sync_event
    from .category_taxonomy import CATEGORY_FACETS
    from .config import get_embedding_dimensions, get_embedding_model, get_llm_model
    from .digest_depth import (
        DEFAULT_DIGEST_DEPTH,
        get_digest_depth_profile,
        normalize_digest_depth,
    )
except ImportError:
    from brain_sync import queue_brain_sync_event
    from category_taxonomy import CATEGORY_FACETS
    from config import get_embedding_dimensions, get_embedding_model, get_llm_model
    from digest_depth import DEFAULT_DIGEST_DEPTH, get_digest_depth_profile, normalize_digest_depth

MAX_TRANSCRIPT_CHARS = 18_000
MAX_CONCEPTS = 14
MAX_EDGES = 18
MAX_LABELS = 20
MAX_SOURCE_REFS = 5
MAX_ARTIFACT_CHARS = 24_000
MAX_SOURCE_INDEX_BODY_CHARS = 5_000
MAX_REPORT_SECTION_INDEX_ROWS = 24
MIN_REFRESH_REPORT_CHARS = 700
KNOWLEDGE_EXTRACTION_VERSION = "source-knowledge-v3"
SOURCE_REF_FALLBACK_VERSION = "source-ref-fallback-v1"
SOURCE_KNOWLEDGE_INDEX_VERSION = "source-knowledge-index-v1"

ALLOWED_CONCEPT_TYPES = {
    "concept",
    "claim",
    "method",
    "algorithm",
    "tool",
    "entity",
    "implementation_note",
    "pitfall",
}

ALLOWED_RELATIONS = {
    "explains",
    "depends_on",
    "contrasts_with",
    "implements",
    "mentions",
    "supports",
    "warns_about",
    "related_to",
}

ALLOWED_LABEL_TYPES = set(CATEGORY_FACETS.keys())


def build_transcript_line_rows(video_db_id: str, chunks: list[dict]) -> list[dict]:
    """Create transcript line rows from stored transcript chunks."""
    rows = []
    for chunk in chunks:
        content = str(chunk.get("text", "")).strip()
        if not content:
            continue
        rows.append(
            {
                "video_id": video_db_id,
                "content": content,
                "start_seconds": int(chunk.get("start_seconds", 0) or 0),
                "end_seconds": int(chunk.get("end_seconds", 0) or 0),
                "source": "youtube_caption",
                "metadata": {
                    "granularity": "chunk",
                    "extraction_version": KNOWLEDGE_EXTRACTION_VERSION,
                },
            }
        )
    return rows


def store_video_knowledge(
    supabase: Any,
    video_db_id: str,
    youtube_video_id: str,
    title: str,
    channel_name: str,
    chunks: list[dict],
    api_key: str | None = None,
    digest_depth: str = DEFAULT_DIGEST_DEPTH,
    published_for_user_id: str | None = None,
    *,
    precomputed_extraction: dict | None = None,
    insert_transcript_lines: bool = True,
) -> dict:
    """Persist transcript lines and generated source knowledge for a video."""
    normalized_digest_depth = normalize_digest_depth(digest_depth)
    transcript_rows = build_transcript_line_rows(video_db_id, chunks)
    if insert_transcript_lines:
        _insert_rows(supabase, "transcript_lines", transcript_rows)

    if normalized_digest_depth == "none":
        counts = {
            "transcript_lines": len(transcript_rows) if insert_transcript_lines else 0,
            "source_concepts": 0,
            "source_labels": 0,
            "source_edges": 0,
            "knowledge_artifacts": 0,
        }
        _queue_knowledge_published_event(
            supabase,
            published_for_user_id,
            video_db_id,
            youtube_video_id,
            title,
            channel_name,
            normalized_digest_depth,
            counts,
        )
        return counts

    extraction = precomputed_extraction
    if extraction is None:
        extraction = extract_source_knowledge(
            youtube_video_id=youtube_video_id,
            title=title,
            channel_name=channel_name,
            chunks=chunks,
            api_key=api_key,
            digest_depth=normalized_digest_depth,
        )

    row_groups = _build_source_knowledge_rows(video_db_id, extraction)
    for table_name, rows in row_groups.items():
        _insert_rows(supabase, table_name, rows)
    replace_source_knowledge_index(
        supabase,
        video_db_id,
        row_groups,
        youtube_video_id=youtube_video_id,
        title=title,
        api_key=api_key,
    )

    counts = {
        "transcript_lines": len(transcript_rows) if insert_transcript_lines else 0,
        **_source_knowledge_counts(row_groups),
    }
    _queue_knowledge_published_event(
        supabase,
        published_for_user_id,
        video_db_id,
        youtube_video_id,
        title,
        channel_name,
        normalized_digest_depth,
        counts,
    )
    return counts


def _build_source_knowledge_rows(video_db_id: str, extraction: dict) -> dict[str, list[dict]]:
    concept_rows = [
        {
            "video_id": video_db_id,
            "concept_type": concept["concept_type"],
            "name": concept["name"],
            "summary": concept["summary"],
            "source_refs": concept["source_refs"],
            "metadata": concept["metadata"],
        }
        for concept in extraction.get("concepts", [])
    ]
    label_rows = [
        {
            "video_id": video_db_id,
            "label_type": label["label_type"],
            "label": label["label"],
            "confidence": label["confidence"],
            "source_refs": label["source_refs"],
            "metadata": label["metadata"],
        }
        for label in extraction.get("labels", [])
    ]
    edge_rows = [
        {
            "video_id": video_db_id,
            "relation": edge["relation"],
            "from_ref": edge["from_ref"],
            "to_ref": edge["to_ref"],
            "evidence_refs": edge["evidence_refs"],
            "metadata": edge["metadata"],
        }
        for edge in extraction.get("edges", [])
    ]
    artifact_rows = [
        {
            "user_id": None,
            "video_id": video_db_id,
            "artifact_type": artifact["artifact_type"],
            "title": artifact["title"],
            "summary": artifact["summary"],
            "content": artifact["content"],
            "source_refs": artifact["source_refs"],
            "metadata": artifact["metadata"],
            "created_by": "system",
        }
        for artifact in extraction.get("artifacts", [])
    ]
    return {
        "source_concepts": concept_rows,
        "source_labels": label_rows,
        "source_edges": edge_rows,
        "knowledge_artifacts": artifact_rows,
    }


def _source_knowledge_counts(row_groups: dict[str, list[dict]]) -> dict[str, int]:
    return {
        "source_concepts": len(row_groups.get("source_concepts", [])),
        "source_labels": len(row_groups.get("source_labels", [])),
        "source_edges": len(row_groups.get("source_edges", [])),
        "knowledge_artifacts": len(row_groups.get("knowledge_artifacts", [])),
    }


def build_source_knowledge_index_rows(
    video_db_id: str,
    row_groups: dict[str, list[dict]],
    youtube_video_id: str | None = None,
    title: str | None = None,
) -> list[dict]:
    """Build searchable source-knowledge rows from generated source objects."""
    rows: list[dict] = []
    video_title = _clean_text(title, max_length=180)

    for index, concept in enumerate(row_groups.get("source_concepts", [])):
        name = _clean_text(concept.get("name"), max_length=180)
        summary = _clean_text(concept.get("summary"), max_length=MAX_SOURCE_INDEX_BODY_CHARS)
        if not name and not summary:
            continue
        concept_type = _clean_text(concept.get("concept_type"), max_length=80) or "concept"
        source_refs = _normalize_index_source_refs(concept.get("source_refs"), youtube_video_id)
        rows.append(
            _source_index_row(
                video_db_id,
                "source_concept",
                f"concept:{index}:{_slugify(name or concept_type)}",
                "",
                name or concept_type,
                summary,
                _index_aliases([concept_type, name, video_title], concept.get("metadata")),
                source_refs,
                {
                    **_index_metadata(concept.get("metadata")),
                    "conceptType": concept_type,
                },
            )
        )

    for index, artifact in enumerate(row_groups.get("knowledge_artifacts", [])):
        artifact_type = _clean_text(artifact.get("artifact_type"), max_length=80)
        display_type = _clean_text(
            (artifact.get("metadata") or {}).get("display_artifact_type"),
            max_length=80,
        )
        artifact_title = _clean_text(artifact.get("title"), max_length=220)
        summary = _clean_text(artifact.get("summary"), max_length=1_400)
        content = _normalize_index_body(artifact.get("content"), MAX_SOURCE_INDEX_BODY_CHARS)
        object_id = f"artifact:{index}:{_slugify(artifact_title or artifact_type)}"
        source_refs = _normalize_index_source_refs(artifact.get("source_refs"), youtube_video_id)
        metadata = {
            **_index_metadata(artifact.get("metadata")),
            "artifactType": artifact_type,
            "displayArtifactType": display_type or None,
            "summary": summary,
        }
        rows.append(
            _source_index_row(
                video_db_id,
                "knowledge_artifact",
                object_id,
                "",
                artifact_title or artifact_type or "Knowledge artifact",
                "\n\n".join(part for part in (summary, content) if part),
                _index_aliases(
                    [
                        artifact_type,
                        display_type,
                        artifact_title,
                        "source report" if display_type == "source_report" else "",
                        "tldr" if artifact_type == "tldr" else "",
                        video_title,
                    ],
                    artifact.get("metadata"),
                ),
                source_refs,
                metadata,
            )
        )

        for section in _report_sections_from_markdown(artifact.get("content")):
            if len([row for row in rows if row.get("source_object_type") == "report_section"]) >= (
                MAX_REPORT_SECTION_INDEX_ROWS
            ):
                break
            section_title = _clean_text(section["title"], max_length=220)
            section_body = _normalize_index_body(section["body"], MAX_SOURCE_INDEX_BODY_CHARS)
            if not section_title or not section_body:
                continue
            section_refs = _normalize_index_source_refs(
                _source_refs_for_section(section_body, artifact.get("source_refs")),
                youtube_video_id,
            )
            rows.append(
                _source_index_row(
                    video_db_id,
                    "report_section",
                    object_id,
                    _slugify(section_title),
                    section_title,
                    section_body,
                    _index_aliases(
                        [
                            section_title,
                            artifact_title,
                            artifact_type,
                            display_type,
                            *_section_aliases(section_title),
                            video_title,
                        ],
                        artifact.get("metadata"),
                    ),
                    section_refs or source_refs,
                    {
                        **metadata,
                        "sectionHeading": section_title,
                        "sectionOrder": section["order"],
                    },
                )
            )

    return rows


def replace_source_knowledge_index(
    supabase: Any,
    video_db_id: str,
    row_groups: dict[str, list[dict]],
    youtube_video_id: str | None = None,
    title: str | None = None,
    api_key: str | None = None,
) -> int:
    """Replace searchable index rows for a video without blocking ingestion on failure."""
    rows = build_source_knowledge_index_rows(
        video_db_id,
        row_groups,
        youtube_video_id=youtube_video_id,
        title=title,
    )
    try:
        supabase.table("source_knowledge_index").delete().eq("video_id", video_db_id).execute()
    except Exception as exc:  # noqa: BLE001 - older schemas may not have the index yet.
        print(f"[KNOWLEDGE_INDEX] Skipping source knowledge index replace: {exc}")
        return 0

    if not rows:
        return 0

    rows = embed_source_knowledge_index_rows(rows, api_key)
    try:
        _insert_rows(supabase, "source_knowledge_index", rows)
    except Exception as exc:  # noqa: BLE001 - source objects remain available through fallback tables.
        print(f"[KNOWLEDGE_INDEX] Failed to insert source knowledge index rows: {exc}")
        return 0
    return len(rows)


def embed_source_knowledge_index_rows(
    rows: list[dict],
    api_key: str | None = None,
) -> list[dict]:
    """Attach document embeddings to source-knowledge rows, leaving nulls on failure."""
    if not rows:
        return rows
    for row in rows:
        row["embedding"] = None
    try:
        embeddings = _get_source_index_embeddings(api_key)
        vectors = embeddings.embed_documents([_source_index_embedding_text(row) for row in rows])
    except Exception as exc:  # noqa: BLE001 - keyword search must still work.
        print(f"[KNOWLEDGE_INDEX] Embedding source knowledge failed; keyword rows kept: {exc}")
        for row in rows:
            metadata = _index_metadata(row.get("metadata"))
            metadata["embeddingStatus"] = "failed"
            row["metadata"] = metadata
        return rows

    for row, vector in zip(rows, vectors, strict=False):
        row["embedding"] = vector
        metadata = _index_metadata(row.get("metadata"))
        metadata["embeddingStatus"] = "embedded"
        row["metadata"] = metadata
    return rows


_source_index_embeddings_cache: dict[str, GoogleGenerativeAIEmbeddings] = {}


def _get_source_index_embeddings(api_key: str | None = None) -> GoogleGenerativeAIEmbeddings:
    key_to_use = api_key or os.getenv("GEMINI_API_KEY")
    if not key_to_use or key_to_use == "PLACEHOLDER_API_KEY":
        raise ValueError(
            "No API key provided. Set GEMINI_API_KEY in .env.local or provide via header."
        )
    if key_to_use in _source_index_embeddings_cache:
        return _source_index_embeddings_cache[key_to_use]

    instance = GoogleGenerativeAIEmbeddings(
        model=get_embedding_model(),
        google_api_key=key_to_use,
        task_type="RETRIEVAL_DOCUMENT",
        output_dimensionality=get_embedding_dimensions(),
    )
    _source_index_embeddings_cache[key_to_use] = instance
    return instance


def _source_index_row(
    video_db_id: str,
    source_object_type: str,
    source_object_id: str,
    section_key: str,
    title: str,
    body: str,
    aliases: list[str],
    source_refs: list[dict],
    metadata: dict,
) -> dict:
    return {
        "video_id": video_db_id,
        "source_object_type": source_object_type,
        "source_object_id": source_object_id,
        "section_key": section_key,
        "title": title,
        "body": body,
        "aliases": aliases,
        "source_refs": source_refs,
        "metadata": {
            **_index_metadata(metadata),
            "indexVersion": SOURCE_KNOWLEDGE_INDEX_VERSION,
            "sourceObjectType": source_object_type,
        },
        "embedding": None,
        "index_version": SOURCE_KNOWLEDGE_INDEX_VERSION,
    }


def _source_index_embedding_text(row: dict) -> str:
    aliases = row.get("aliases") if isinstance(row.get("aliases"), list) else []
    return "\n".join(
        part
        for part in (
            str(row.get("title") or "").strip(),
            "Aliases: " + ", ".join(str(alias) for alias in aliases if str(alias).strip()),
            str(row.get("body") or "").strip(),
        )
        if part.strip()
    )


def _index_metadata(value: Any) -> dict:
    return dict(value) if isinstance(value, dict) else {}


def _index_aliases(values: list[Any], metadata: Any = None) -> list[str]:
    aliases: list[str] = []
    if isinstance(metadata, dict):
        raw_aliases = metadata.get("aliases") or metadata.get("keywords")
        if isinstance(raw_aliases, list):
            aliases.extend(raw_aliases)
    aliases.extend(values)

    deduped = []
    seen = set()
    for value in aliases:
        text = _clean_text(value, max_length=120)
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(text)
    return deduped[:12]


def _normalize_index_body(value: Any, max_chars: int) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    lines = [" ".join(line.split()) for line in text.splitlines()]
    normalized = "\n".join(line for line in lines if line).strip()
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    if len(normalized) <= max_chars:
        return normalized
    return normalized[: max_chars - 1].rstrip() + "…"


def _normalize_index_source_refs(refs: Any, youtube_video_id: str | None = None) -> list[dict]:
    if not isinstance(refs, list):
        refs = [refs] if isinstance(refs, dict) else []
    normalized = []
    for ref in refs:
        if not isinstance(ref, dict):
            continue
        copied = dict(ref)
        if youtube_video_id and not copied.get("youtube_video_id"):
            copied["youtube_video_id"] = youtube_video_id
        normalized.append(copied)
    return normalized[:MAX_SOURCE_REFS]


def _source_refs_for_section(section_body: str, artifact_refs: Any) -> list[dict]:
    refs = artifact_refs if isinstance(artifact_refs, list) else []
    starts = {
        int(match.group(1)) * 60 + int(match.group(2))
        for match in re.finditer(r"\(source:\s*(\d{1,2}):(\d{2})\)", section_body, re.I)
    }
    if not starts:
        return refs[:MAX_SOURCE_REFS]
    matching = [
        ref
        for ref in refs
        if isinstance(ref, dict)
        and isinstance(ref.get("start_seconds"), (int, float))
        and int(ref["start_seconds"]) in starts
    ]
    return matching[:MAX_SOURCE_REFS] if matching else refs[:MAX_SOURCE_REFS]


def _report_sections_from_markdown(value: Any) -> list[dict]:
    text = str(value or "").strip()
    if not text:
        return []

    matches = list(re.finditer(r"(?m)^(#{1,3})\s+(.+?)\s*$", text))
    if not matches:
        return [{"title": "Source Report", "body": text, "order": 0}]

    sections = []
    for order, match in enumerate(matches):
        heading = _clean_text(match.group(2), max_length=220)
        if not heading:
            continue
        start = match.end()
        end = matches[order + 1].start() if order + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        if match.group(1) == "#" and len(matches) > 1:
            continue
        if body:
            sections.append({"title": heading, "body": body, "order": len(sections)})
    return sections


def _section_aliases(section_title: str) -> list[str]:
    normalized = section_title.lower()
    aliases = []
    if "compiled truth" in normalized:
        aliases.extend(["main takeaways", "core argument", "executive summary"])
    if "agent quick" in normalized or "quick index" in normalized:
        aliases.extend(["agent index", "retrieval hints", "where to start"])
    if "theme" in normalized:
        aliases.extend(["themes", "topics", "patterns"])
    if "people" in normalized:
        aliases.extend(["persons", "speakers", "individuals"])
    if "organization" in normalized:
        aliases.extend(["companies", "clients", "institutions"])
    if "tool" in normalized or "system" in normalized:
        aliases.extend(["software", "platforms", "tools"])
    if "claim" in normalized:
        aliases.extend(["assertions", "arguments", "positions"])
    if "decision" in normalized:
        aliases.extend(["choices", "tradeoffs", "recommendations"])
    if "timeline" in normalized:
        aliases.extend(["timestamps", "sequence", "chronology"])
    if "evidence" in normalized:
        aliases.extend(["citations", "source refs", "timestamp evidence"])
    return aliases


def _slugify(value: Any) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-")
    return slug[:100] or "item"


def extract_source_knowledge(
    youtube_video_id: str,
    title: str,
    channel_name: str,
    chunks: list[dict],
    api_key: str | None = None,
    digest_depth: str = DEFAULT_DIGEST_DEPTH,
) -> dict:
    """Generate normalized concepts, edges, and artifacts from transcript chunks."""
    if not chunks:
        return _empty_extraction()

    normalized_digest_depth = normalize_digest_depth(digest_depth)
    if normalized_digest_depth == "none":
        return _empty_extraction()
    profile = get_digest_depth_profile(normalized_digest_depth)

    try:
        prompt = _build_extraction_prompt(title, channel_name, chunks, normalized_digest_depth)
        response = _get_llm(api_key, int(profile["max_output_tokens"])).invoke(prompt)
        raw_text = _content_to_text(response.content)
        payload = _parse_json_object(raw_text)
    except Exception as exc:  # noqa: BLE001 - knowledge extraction must not break ingestion.
        print(f"[KNOWLEDGE] Source extraction failed for {youtube_video_id}: {exc}")
        return _empty_extraction()

    return {
        "concepts": _normalize_concepts(
            payload, youtube_video_id, chunks, int(profile["max_concepts"])
        ),
        "labels": _normalize_labels(payload, youtube_video_id, chunks, int(profile["max_labels"])),
        "edges": _normalize_edges(payload, youtube_video_id, chunks, int(profile["max_edges"])),
        "artifacts": _normalize_artifacts(
            payload,
            youtube_video_id,
            title,
            chunks,
            set(profile["artifact_types"]),
        ),
    }


def _insert_rows(supabase: Any, table_name: str, rows: list[dict], batch_size: int = 50) -> None:
    if not rows:
        return
    for index in range(0, len(rows), batch_size):
        supabase.table(table_name).insert(rows[index : index + batch_size]).execute()


def _result_rows(result: Any) -> list[dict]:
    data = getattr(result, "data", None)
    if data is None:
        return []
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    if isinstance(data, dict):
        return [data]
    return []


def _load_stored_chunks(supabase: Any, video_db_id: str) -> list[dict]:
    rows = _result_rows(
        supabase.table("chunks")
        .select("content, start_seconds, end_seconds")
        .eq("video_id", video_db_id)
        .order("start_seconds", desc=False)
        .execute()
    )
    return [
        {
            "text": row.get("content", ""),
            "start_seconds": int(row.get("start_seconds", 0) or 0),
            "end_seconds": int(row.get("end_seconds", row.get("start_seconds", 0)) or 0),
        }
        for row in rows
        if str(row.get("content") or "").strip()
    ]


def _delete_existing_source_knowledge(supabase: Any, video_db_id: str) -> None:
    for table_name in ("source_concepts", "source_labels", "source_edges"):
        supabase.table(table_name).delete().eq("video_id", video_db_id).execute()
    (
        supabase.table("knowledge_artifacts")
        .delete()
        .eq("video_id", video_db_id)
        .eq("created_by", "system")
        .execute()
    )


def source_knowledge_needs_refresh(
    supabase: Any,
    video_db_id: str,
    digest_depth: str = DEFAULT_DIGEST_DEPTH,
) -> bool:
    """Return true when canonical source knowledge is missing, shallow, or unlinked."""
    normalized_digest_depth = normalize_digest_depth(digest_depth)
    if normalized_digest_depth == "none":
        return False

    concepts = _result_rows(
        supabase.table("source_concepts")
        .select("id, source_refs")
        .eq("video_id", video_db_id)
        .limit(30)
        .execute()
    )
    if not concepts:
        return True
    if not any(_has_timestamp_ref(row.get("source_refs")) for row in concepts):
        return True

    if normalized_digest_depth == "basic":
        return False

    artifacts = _result_rows(
        supabase.table("knowledge_artifacts")
        .select("id, artifact_type, content, source_refs, metadata")
        .eq("video_id", video_db_id)
        .eq("created_by", "system")
        .limit(10)
        .execute()
    )
    source_reports = [
        artifact
        for artifact in artifacts
        if artifact.get("artifact_type") == "study_guide"
        or (artifact.get("metadata") or {}).get("display_artifact_type") == "source_report"
    ]
    if not source_reports:
        return True

    best_report = max(source_reports, key=lambda artifact: len(str(artifact.get("content") or "")))
    content = str(best_report.get("content") or "")
    if len(content) < 1_500:
        return True
    if not (_has_timestamp_ref(best_report.get("source_refs")) or "(source:" in content.lower()):
        return True
    return False


def refresh_existing_video_source_knowledge(
    supabase: Any,
    video: dict,
    api_key: str | None = None,
    digest_depth: str = DEFAULT_DIGEST_DEPTH,
    published_for_user_id: str | None = None,
) -> dict:
    """Regenerate source knowledge for an already-embedded canonical video."""
    normalized_digest_depth = normalize_digest_depth(digest_depth)
    video_db_id = str(video.get("id") or "")
    youtube_video_id = str(video.get("youtube_video_id") or video.get("videoId") or "")
    if not video_db_id or not youtube_video_id:
        return {"refreshed": False, "reason": "missing_video_identity"}

    chunks = _load_stored_chunks(supabase, video_db_id)
    if not chunks:
        return {"refreshed": False, "reason": "missing_chunks"}

    if normalized_digest_depth == "none":
        return {"refreshed": False, "reason": "digest_depth_none"}

    title = str(video.get("title") or youtube_video_id)
    channel_name = str(video.get("channel_name") or video.get("channelName") or "Unknown Channel")
    extraction = extract_source_knowledge(
        youtube_video_id=youtube_video_id,
        title=title,
        channel_name=channel_name,
        chunks=chunks,
        api_key=api_key,
        digest_depth=normalized_digest_depth,
    )
    row_groups = _build_source_knowledge_rows(video_db_id, extraction)
    if not _has_publishable_source_knowledge(row_groups, normalized_digest_depth):
        return {
            "refreshed": False,
            "reason": "extraction_not_publishable",
            "counts": _source_knowledge_counts(row_groups),
        }

    _delete_existing_source_knowledge(supabase, video_db_id)
    counts = store_video_knowledge(
        supabase,
        video_db_id,
        youtube_video_id,
        title,
        channel_name,
        chunks,
        api_key=api_key,
        digest_depth=normalized_digest_depth,
        published_for_user_id=published_for_user_id,
        precomputed_extraction=extraction,
        insert_transcript_lines=False,
    )
    return {"refreshed": True, "reason": "regenerated", "counts": counts}


def _has_publishable_source_knowledge(
    row_groups: dict[str, list[dict]],
    digest_depth: str,
) -> bool:
    counts = _source_knowledge_counts(row_groups)
    if sum(counts.values()) <= 0:
        return False

    if normalize_digest_depth(digest_depth) == "basic":
        return True

    source_reports = [
        row
        for row in row_groups.get("knowledge_artifacts", [])
        if row.get("artifact_type") == "study_guide"
        or (row.get("metadata") or {}).get("display_artifact_type") == "source_report"
    ]
    if not source_reports:
        return False

    best_report = max(source_reports, key=lambda row: len(str(row.get("content") or "")))
    content = str(best_report.get("content") or "")
    if len(content.strip()) < MIN_REFRESH_REPORT_CHARS:
        return False
    return _has_timestamp_ref(best_report.get("source_refs")) or "(source:" in content.lower()


def _queue_knowledge_published_event(
    supabase: Any,
    user_id: str | None,
    video_db_id: str,
    youtube_video_id: str,
    title: str,
    channel_name: str,
    digest_depth: str,
    counts: dict,
) -> None:
    if not user_id:
        return
    published_count = sum(
        int(counts.get(key) or 0)
        for key in ("source_concepts", "source_labels", "source_edges", "knowledge_artifacts")
    )
    if published_count <= 0:
        return

    try:
        queue_brain_sync_event(
            supabase,
            user_id,
            "knowledge.published",
            payload={
                "videoDbId": video_db_id,
                "videoId": youtube_video_id,
                "title": title,
                "channelName": channel_name,
                "digestDepth": digest_depth,
                "counts": counts,
            },
            source_ref={
                "type": "youtube_video",
                "video_db_id": video_db_id,
                "video_id": youtube_video_id,
            },
            metadata={
                "trigger": "source_knowledge.published",
                "extractionVersion": KNOWLEDGE_EXTRACTION_VERSION,
            },
            idempotency_key=f"knowledge.published:{video_db_id}:{digest_depth}",
        )
    except Exception as exc:  # noqa: BLE001 - knowledge sync must not block ingestion.
        print(f"[BRAIN_SYNC] Failed to queue knowledge published event: {exc}")


def _get_llm(api_key: str | None, max_output_tokens: int = 2048) -> ChatGoogleGenerativeAI:
    key_to_use = api_key or os.getenv("GEMINI_API_KEY")
    if not key_to_use:
        raise ValueError("No API key available for source knowledge extraction")
    return ChatGoogleGenerativeAI(
        model=get_llm_model(),
        google_api_key=key_to_use,
        temperature=0.1,
        max_output_tokens=max_output_tokens,
    )


def _content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
        return "".join(parts)
    return ""


def _build_extraction_prompt(
    title: str,
    channel_name: str,
    chunks: list[dict],
    digest_depth: str,
) -> str:
    profile = get_digest_depth_profile(digest_depth)
    transcript = _format_transcript(chunks, int(profile["max_transcript_chars"]))
    transcript_duration_seconds = _transcript_duration_seconds(chunks)
    concept_types = ", ".join(sorted(ALLOWED_CONCEPT_TYPES))
    relations = ", ".join(sorted(ALLOWED_RELATIONS))
    label_taxonomy = _format_label_taxonomy()
    if digest_depth == "basic":
        required_shape = [
            "- tldr: a dense 2-3 sentence summary.",
            "- study_guide: an empty object. This legacy key is reserved for the full source report.",
            "- labels: compact library-search labels for this video.",
            "- concepts: only the most important concepts, methods, entities, claims, pitfalls, and practical notes.",
            "- edges: an empty array.",
        ]
        depth_rules = [
            "- Do not create a source report for basic depth.",
            "- Do not create concept relationship edges for basic depth.",
            f"- Keep concepts under {profile['max_concepts']} and labels under {profile['max_labels']}.",
        ]
    else:
        required_shape = [
            "- tldr: a dense 3-5 sentence summary.",
            (
                "- study_guide: a source-report object with title, summary, themes, compiled_truth, "
                "agent_index, people, organizations, tools, claims, decisions, timeline, "
                "sections, action_items, open_questions or questions."
            ),
            "- labels: array of library-search labels for this video.",
            "- concepts: array of important concepts, methods, techniques, tools, entities, claims, pitfalls, and practical notes.",
            "- edges: array of relationships between concepts.",
        ]
        depth_rules = [
            f"- Keep concepts under {profile['max_concepts']} and edges under {profile['max_edges']}.",
            f"- Keep labels under {profile['max_labels']} and make them useful for agent filtering and browsing.",
            _study_guide_length_rule(transcript_duration_seconds, digest_depth),
        ]
    return "\n".join(
        [
            "Extract structured knowledge from this YouTube transcript for a user and their agents.",
            "Return only valid JSON. Do not wrap it in markdown.",
            f"Digest depth: {digest_depth}. {profile['description']}",
            "",
            "The JSON object must include these keys:",
            *required_shape,
            "",
            f"Allowed concept_type values: {concept_types}",
            f"Allowed label_type values: {', '.join(sorted(ALLOWED_LABEL_TYPES))}",
            f"Allowed relation values: {relations}",
            "",
            "Label taxonomy:",
            label_taxonomy,
            "",
            "Rules:",
            *depth_rules,
            "- Good labels include domain, content type, topic, task fit, entities, methods, tools, difficulty, maturity, and evidence quality.",
            "- This system is universal across YouTube topics: cooking, repairs, history, music, sports, health, business, science, AI, and more.",
            "- Prefer ideas that help a user learn, decide, teach, troubleshoot, create, practice, buy, plan, build, or apply the topic.",
            "- For non-software topics, use concept_type='method' for procedures/techniques and concept_type='implementation_note' for practical application notes.",
            "- Concepts must be useful topic cards: each needs a specific name, a 2-4 sentence summary, and at least one timestamp source_ref with clip_index or start_seconds.",
            "- Apply the same analysis contract to every indexed video. Scale report length and item counts to transcript duration and information density, not to whether the video came from a single URL, playlist, channel, or agent submission.",
            "- Model the source report after a gbrain-style entity page: Compiled Truth, Agent Quick Index, Key Themes, People, Organizations, Tools and Systems, Claims, Decisions, Timeline, Evidence Map, and Open Questions.",
            "- Do not make agents scan the transcript. Produce scannable named objects with dense 2-5 sentence summaries, source_refs, query-friendly labels, and retrieval hints that point to exact supporting timestamps.",
            "- The source report must be substantial enough to help a human or agent understand the video's material without rewatching it or reading the raw transcript first.",
            "- For standard depth, write the full source report appropriate for the video length; for deep depth, use the larger transcript window and output budget to capture more nuance from long or dense videos.",
            "- Compiled Truth should contain 8-16 specific source-backed facts or takeaways when the transcript supports them; each item should explain the claim, the context, and why it matters.",
            "- Agent Quick Index should contain 8-12 retrieval entries with name, summary, retrieval_hint or query, and source_refs so agents can jump directly to the right part of the video.",
            "- Source-report section bullets should be paragraph-level notes of roughly 50-140 words, not slogans. Cover the video's argument, major themes, practical implications, examples, caveats, and follow-up questions.",
            "- Timeline entries should name the moment, explain what changes at that point in the material, and include source_refs.",
            "- Do not stop at generic summaries. Extract the specific mechanisms, tradeoffs, examples, warnings, and decisions that make this video worth saving.",
            "- People, organizations, tools, claims, decisions, and timeline entries should be objects with name/title, summary, why_it_matters or retrieval_hint, and source_refs where possible.",
            "- Do not write placeholder bullets, generic filler, teaser fragments, or ellipses. If a section has little evidence, omit it rather than padding it.",
            "- Every label, concept, report item, timeline entry, claim, decision, and edge must cite transcript evidence with source_refs unless no transcript clip supports it.",
            "- A source_ref may use clip_index from the transcript below, or start_seconds and end_seconds.",
            "- Do not invent facts that are not supported by the transcript.",
            "",
            f"Video title: {title}",
            f"Channel: {channel_name}",
            f"Transcript duration estimate: {_format_duration(transcript_duration_seconds)}",
            "",
            "Transcript clips:",
            transcript,
            "",
            "JSON:",
        ]
    )


def _transcript_duration_seconds(chunks: list[dict]) -> int:
    if not chunks:
        return 0
    return max(int(chunk.get("end_seconds", 0) or 0) for chunk in chunks)


def _study_guide_length_rule(duration_seconds: int, digest_depth: str) -> str:
    if duration_seconds <= 0:
        return (
            "- Source report length should match the available transcript substance; omit empty "
            "sections instead of padding."
        )
    if duration_seconds < 5 * 60:
        target = "400-900 words"
        sections = "3-5 concise sections"
    elif duration_seconds < 20 * 60:
        target = "900-1,800 words"
        sections = "4-7 sections"
    elif duration_seconds < 60 * 60:
        target = "1,500-3,000 words"
        sections = "6-10 sections"
    else:
        target = "2,500-4,500 words"
        sections = "8-14 sections"
    depth_note = (
        "Use the upper half of that range when the transcript is dense."
        if digest_depth == "deep"
        else "Use the lower or middle part of that range when the transcript is straightforward."
    )
    return (
        f"- Source report target for this {_format_duration(duration_seconds)} video: "
        f"{target} across {sections}, if the transcript supports it. {depth_note}"
    )


def _format_duration(seconds: int) -> str:
    minutes, secs = divmod(max(0, int(seconds)), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m {secs}s"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def _format_transcript(chunks: list[dict], max_chars: int = MAX_TRANSCRIPT_CHARS) -> str:
    lines = []
    total_chars = 0
    for index, chunk in enumerate(chunks):
        text = " ".join(str(chunk.get("text", "")).split())
        if not text:
            continue
        start = int(chunk.get("start_seconds", 0) or 0)
        end = int(chunk.get("end_seconds", 0) or 0)
        line = f"[{index}] {start}s-{end}s: {text}"
        if total_chars + len(line) > max_chars:
            remaining = max_chars - total_chars
            if remaining > 80:
                lines.append(line[:remaining].rstrip())
            break
        lines.append(line)
        total_chars += len(line) + 1
    return "\n".join(lines)


def _format_label_taxonomy() -> str:
    lines = []
    for label_type in sorted(ALLOWED_LABEL_TYPES):
        facet = CATEGORY_FACETS[label_type]
        examples = ", ".join(facet.get("examples", [])[:4])
        lines.append(f"- {label_type}: {facet.get('description', '')} Examples: {examples}.")
    return "\n".join(lines)


def _parse_json_object(raw_text: str) -> dict:
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if not match:
        raise ValueError("LLM response did not contain a JSON object")
    parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise ValueError("LLM response JSON must be an object")
    return parsed


def _normalize_concepts(
    payload: dict,
    youtube_video_id: str,
    chunks: list[dict],
    max_concepts: int = MAX_CONCEPTS,
) -> list[dict]:
    concepts = []
    raw_concepts = payload.get("concepts", [])
    if not isinstance(raw_concepts, list):
        return concepts

    seen_names = set()
    for raw in raw_concepts[:max_concepts]:
        if not isinstance(raw, dict):
            continue
        name = _clean_text(raw.get("name"), max_length=140)
        if not name or name.lower() in seen_names:
            continue
        seen_names.add(name.lower())

        concept_type = raw.get("concept_type", "concept")
        if concept_type not in ALLOWED_CONCEPT_TYPES:
            concept_type = "concept"
        summary = _clean_text(raw.get("summary"), max_length=900)
        source_refs = _normalize_source_refs(
            raw.get("source_refs", []),
            youtube_video_id,
            chunks,
        )
        inferred_source_refs = False
        if not source_refs:
            source_refs = _infer_source_refs_for_text(
                f"{name}. {summary}",
                youtube_video_id,
                chunks,
                limit=2,
            )
            inferred_source_refs = bool(source_refs)

        concepts.append(
            {
                "concept_type": concept_type,
                "name": name,
                "summary": summary,
                "source_refs": source_refs,
                "metadata": {
                    "extraction_version": KNOWLEDGE_EXTRACTION_VERSION,
                    "model": get_llm_model(),
                    **(
                        {"source_ref_fallback": SOURCE_REF_FALLBACK_VERSION}
                        if inferred_source_refs
                        else {}
                    ),
                },
            }
        )

    return concepts


def _normalize_labels(
    payload: dict,
    youtube_video_id: str,
    chunks: list[dict],
    max_labels: int = MAX_LABELS,
) -> list[dict]:
    labels = []
    raw_labels = payload.get("labels", [])
    if not isinstance(raw_labels, list):
        return labels

    seen = set()
    for raw in raw_labels[:max_labels]:
        if not isinstance(raw, dict):
            continue

        label_type = _normalize_label_type(raw.get("label_type") or raw.get("type"))
        label = _clean_text(raw.get("label") or raw.get("name") or raw.get("value"), 120)
        if not label:
            continue

        key = (label_type, label.lower())
        if key in seen:
            continue
        seen.add(key)
        source_refs = _normalize_source_refs(
            raw.get("source_refs", []),
            youtube_video_id,
            chunks,
        )
        inferred_source_refs = False
        if not source_refs:
            source_refs = _infer_source_refs_for_text(label, youtube_video_id, chunks, limit=1)
            inferred_source_refs = bool(source_refs)

        labels.append(
            {
                "label_type": label_type,
                "label": label,
                "confidence": _normalize_confidence(raw.get("confidence")),
                "source_refs": source_refs,
                "metadata": {
                    "extraction_version": KNOWLEDGE_EXTRACTION_VERSION,
                    "model": get_llm_model(),
                    **(
                        {"source_ref_fallback": SOURCE_REF_FALLBACK_VERSION}
                        if inferred_source_refs
                        else {}
                    ),
                },
            }
        )

    return labels


def _normalize_label_type(value: Any) -> str:
    if isinstance(value, str):
        normalized = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
        if normalized in ALLOWED_LABEL_TYPES:
            return normalized
    return "topic"


def _normalize_confidence(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(1.0, round(numeric, 3)))


def _normalize_edges(
    payload: dict,
    youtube_video_id: str,
    chunks: list[dict],
    max_edges: int = MAX_EDGES,
) -> list[dict]:
    edges = []
    raw_edges = payload.get("edges", [])
    if not isinstance(raw_edges, list):
        return edges

    for raw in raw_edges[:max_edges]:
        if not isinstance(raw, dict):
            continue
        from_ref = _normalize_named_ref(raw.get("from") or raw.get("from_ref"))
        to_ref = _normalize_named_ref(raw.get("to") or raw.get("to_ref"))
        if not from_ref or not to_ref:
            continue

        relation = raw.get("relation", "related_to")
        if relation not in ALLOWED_RELATIONS:
            relation = "related_to"
        evidence_refs = _normalize_source_refs(
            raw.get("evidence_refs") or raw.get("source_refs", []),
            youtube_video_id,
            chunks,
        )
        inferred_source_refs = False
        if not evidence_refs:
            evidence_refs = _infer_source_refs_for_text(
                " ".join(
                    value
                    for value in (
                        _named_ref_name(from_ref),
                        _named_ref_name(to_ref),
                        relation,
                    )
                    if value
                ),
                youtube_video_id,
                chunks,
                limit=1,
            )
            inferred_source_refs = bool(evidence_refs)

        edges.append(
            {
                "relation": relation,
                "from_ref": from_ref,
                "to_ref": to_ref,
                "evidence_refs": evidence_refs,
                "metadata": {
                    "extraction_version": KNOWLEDGE_EXTRACTION_VERSION,
                    "model": get_llm_model(),
                    **(
                        {"source_ref_fallback": SOURCE_REF_FALLBACK_VERSION}
                        if inferred_source_refs
                        else {}
                    ),
                },
            }
        )

    return edges


def _normalize_artifacts(
    payload: dict,
    youtube_video_id: str,
    title: str,
    chunks: list[dict],
    artifact_types: set[str] | None = None,
) -> list[dict]:
    artifacts = []
    artifact_types = artifact_types or {"tldr", "study_guide"}
    video_ref = _video_ref(youtube_video_id, chunks)
    tldr = _clean_text(payload.get("tldr"), max_length=2000)
    if tldr and "tldr" in artifact_types:
        artifacts.append(
            {
                "artifact_type": "tldr",
                "title": f"TLDR: {title}"[:180],
                "summary": tldr[:900],
                "content": tldr,
                "source_refs": [video_ref],
                "metadata": {
                    "extraction_version": KNOWLEDGE_EXTRACTION_VERSION,
                    "model": get_llm_model(),
                },
            }
        )

    study_guide = payload.get("study_guide")
    study_content = _format_study_guide(study_guide, youtube_video_id, chunks)
    if study_content and "study_guide" in artifact_types:
        study_title = title
        study_summary = ""
        if isinstance(study_guide, dict):
            study_title = _clean_text(study_guide.get("title"), max_length=160) or title
            study_summary = _clean_text(study_guide.get("summary"), max_length=900)
        artifacts.append(
            {
                "artifact_type": "study_guide",
                "title": f"Source Report: {study_title}"[:180],
                "summary": study_summary,
                "content": study_content[:MAX_ARTIFACT_CHARS],
                "source_refs": _artifact_source_refs(
                    video_ref,
                    study_guide,
                    youtube_video_id,
                    chunks,
                    fallback_text=study_content,
                ),
                "metadata": {
                    "display_artifact_type": "source_report",
                    "extraction_version": KNOWLEDGE_EXTRACTION_VERSION,
                    "model": get_llm_model(),
                },
            }
        )

    return artifacts


def _normalize_source_refs(
    refs: Any,
    youtube_video_id: str,
    chunks: list[dict],
) -> list[dict]:
    if not isinstance(refs, list):
        refs = [refs] if isinstance(refs, dict) else []

    normalized = []
    for raw in refs[:MAX_SOURCE_REFS]:
        if not isinstance(raw, dict):
            continue

        clip_index = raw.get("clip_index")
        if isinstance(clip_index, int) and not isinstance(clip_index, bool):
            if 0 <= clip_index < len(chunks):
                chunk = chunks[clip_index]
                start = int(chunk.get("start_seconds", 0) or 0)
                end = int(chunk.get("end_seconds", start) or start)
            else:
                continue
        else:
            start = _coerce_seconds(raw.get("start_seconds"))
            end = _coerce_seconds(raw.get("end_seconds"))
            if start is None:
                continue
            if end is None or end < start:
                end = start

        ref = {
            "source_type": "transcript",
            "youtube_video_id": youtube_video_id,
            "start_seconds": start,
            "end_seconds": end,
        }
        quote = _clean_text(raw.get("quote"), max_length=240)
        if quote:
            ref["quote"] = quote
        normalized.append(ref)

    return normalized


def _has_timestamp_ref(refs: Any) -> bool:
    if not isinstance(refs, list):
        return False
    return any(
        isinstance(ref, dict)
        and _coerce_seconds(ref.get("start_seconds")) is not None
        and (
            ref.get("source_type") in {None, "transcript"}
            or str(ref.get("source_type") or "").lower() == "transcript"
        )
        for ref in refs
    )


def _infer_source_refs_for_text(
    text: str,
    youtube_video_id: str,
    chunks: list[dict],
    limit: int = 1,
) -> list[dict]:
    """Infer timestamp refs from stored transcript chunks when the model omits refs."""
    if not youtube_video_id or not chunks:
        return []

    query_tokens = _meaningful_tokens(text)
    scored: list[tuple[int, int, dict]] = []
    fallback_chunks: list[tuple[int, dict]] = []
    for index, chunk in enumerate(chunks):
        chunk_text = str(chunk.get("text") or chunk.get("content") or "")
        if not chunk_text.strip():
            continue
        fallback_chunks.append((index, chunk))
        chunk_tokens = _meaningful_tokens(chunk_text)
        score = len(query_tokens & chunk_tokens)
        if score > 0:
            scored.append((score, -index, chunk))

    ranked_chunks = [chunk for _score, _index, chunk in sorted(scored, reverse=True)]
    if not ranked_chunks and fallback_chunks:
        ranked_chunks = [fallback_chunks[0][1]]

    refs = []
    seen_starts = set()
    for chunk in ranked_chunks:
        start = _coerce_seconds(chunk.get("start_seconds"))
        if start is None or start in seen_starts:
            continue
        end = _coerce_seconds(chunk.get("end_seconds"))
        if end is None or end < start:
            end = start
        ref = {
            "source_type": "transcript",
            "youtube_video_id": youtube_video_id,
            "start_seconds": start,
            "end_seconds": end,
            "quote": _clean_text(str(chunk.get("text") or chunk.get("content") or ""), 240),
        }
        refs.append(ref)
        seen_starts.add(start)
        if len(refs) >= max(1, limit):
            break
    return refs


def _meaningful_tokens(text: str) -> set[str]:
    stopwords = {
        "about",
        "after",
        "again",
        "also",
        "and",
        "are",
        "because",
        "before",
        "but",
        "can",
        "from",
        "has",
        "have",
        "how",
        "into",
        "its",
        "not",
        "that",
        "the",
        "their",
        "then",
        "this",
        "through",
        "use",
        "uses",
        "using",
        "what",
        "when",
        "where",
        "why",
        "with",
        "you",
    }
    return {
        token
        for token in re.findall(r"[a-zA-Z0-9][a-zA-Z0-9_-]{2,}", text.lower())
        if token not in stopwords
    }


def _named_ref_name(value: Any) -> str:
    if isinstance(value, dict):
        return _clean_text(value.get("name") or value.get("title") or value.get("label"), 140)
    return _clean_text(value, 140)


def _normalize_named_ref(value: Any) -> dict | None:
    if isinstance(value, dict):
        name = _clean_text(value.get("name"), max_length=140)
        ref_type = _clean_text(value.get("source_type"), max_length=60) or "source_concept"
    else:
        name = _clean_text(value, max_length=140)
        ref_type = "source_concept"
    if not name:
        return None
    return {"source_type": ref_type, "name": name}


def _format_study_guide(
    study_guide: Any,
    youtube_video_id: str | None = None,
    chunks: list[dict] | None = None,
) -> str:
    if isinstance(study_guide, str):
        return _clean_text(study_guide, max_length=MAX_ARTIFACT_CHARS)
    if not isinstance(study_guide, dict):
        return ""

    chunks = chunks or []
    lines = []
    title = _clean_text(study_guide.get("title"), max_length=180)
    summary = _clean_text(study_guide.get("summary"), max_length=2400)
    if title:
        lines.extend([f"# {title}", ""])
    if summary:
        lines.extend(["## Compiled Truth", "", summary, ""])

    _append_guide_list(
        lines,
        None if summary else "Compiled Truth",
        study_guide.get("compiled_truth") or study_guide.get("compiledTruth"),
        youtube_video_id,
        chunks,
        max_items=16,
        max_length=1600,
    )
    _append_guide_list(
        lines,
        "Agent Quick Index",
        study_guide.get("agent_index") or study_guide.get("agentIndex"),
        youtube_video_id,
        chunks,
        max_items=16,
        max_length=1400,
    )
    _append_guide_list(
        lines,
        "Key Themes",
        study_guide.get("themes"),
        youtube_video_id,
        chunks,
        max_items=16,
        max_length=1000,
    )
    _append_guide_list(
        lines,
        "People",
        study_guide.get("people") or study_guide.get("persons"),
        youtube_video_id,
        chunks,
        max_items=16,
        max_length=1200,
    )
    _append_guide_list(
        lines,
        "Organizations",
        study_guide.get("organizations") or study_guide.get("companies"),
        youtube_video_id,
        chunks,
        max_items=16,
        max_length=1200,
    )
    _append_guide_list(
        lines,
        "Tools and Systems",
        study_guide.get("tools")
        or study_guide.get("systems")
        or study_guide.get("tools_and_systems"),
        youtube_video_id,
        chunks,
        max_items=16,
        max_length=1200,
    )
    _append_guide_list(
        lines,
        "Claims",
        study_guide.get("claims"),
        youtube_video_id,
        chunks,
        max_items=14,
        max_length=1400,
    )
    _append_guide_list(
        lines,
        "Decisions",
        study_guide.get("decisions"),
        youtube_video_id,
        chunks,
        max_items=14,
        max_length=1400,
    )
    _append_guide_list(
        lines,
        "Timeline",
        study_guide.get("timeline"),
        youtube_video_id,
        chunks,
        max_items=20,
        max_length=1400,
    )
    _append_guide_list(
        lines,
        "Evidence Map",
        study_guide.get("evidence_map")
        or study_guide.get("evidenceMap")
        or study_guide.get("source_map")
        or study_guide.get("sourceMap"),
        youtube_video_id,
        chunks,
        max_items=20,
        max_length=1400,
    )

    sections = study_guide.get("sections", [])
    if isinstance(sections, list):
        for section in sections:
            if not isinstance(section, dict):
                continue
            heading = _clean_text(section.get("heading"), max_length=140)
            if heading:
                lines.extend([f"## {heading}", ""])
            bullets = section.get("bullets", [])
            if isinstance(bullets, list):
                for bullet in bullets[:8]:
                    text = _format_guide_item(
                        bullet,
                        youtube_video_id,
                        chunks,
                        max_length=1600,
                    )
                    if text:
                        lines.append(f"- {text}")
                if bullets:
                    lines.append("")

    _append_guide_list(
        lines,
        "Action Items",
        study_guide.get("action_items") or study_guide.get("actionItems"),
        youtube_video_id,
        chunks,
        max_items=16,
        max_length=1200,
    )
    _append_guide_list(
        lines,
        "Open Questions",
        study_guide.get("open_questions")
        or study_guide.get("openQuestions")
        or study_guide.get("questions"),
        youtube_video_id,
        chunks,
        max_items=16,
        max_length=1200,
    )

    return "\n".join(lines).strip()


def _append_guide_list(
    lines: list[str],
    heading: str | None,
    values: Any,
    youtube_video_id: str | None,
    chunks: list[dict],
    max_items: int = 12,
    max_length: int = 1200,
) -> None:
    entries = _guide_entries(values)
    if not entries:
        return
    cleaned = [
        _format_guide_item(value, youtube_video_id, chunks, max_length=max_length)
        for value in entries[:max_items]
    ]
    cleaned = [value for value in cleaned if value]
    if not cleaned:
        return
    if heading:
        lines.extend([f"## {heading}", ""])
    lines.extend(f"- {value}" for value in cleaned)
    lines.append("")


def _guide_entries(values: Any) -> list[Any]:
    if isinstance(values, list):
        return values
    if isinstance(values, dict):
        entries = []
        for key, value in values.items():
            if isinstance(value, list):
                entries.extend({"name": _humanize_key(key), "summary": item} for item in value[:8])
            else:
                entries.append({"name": _humanize_key(key), "summary": value})
        return entries
    if isinstance(values, str):
        return [values]
    return []


def _format_guide_item(
    value: Any,
    youtube_video_id: str | None,
    chunks: list[dict],
    max_length: int = 1200,
) -> str:
    if isinstance(value, str):
        text = _clean_text(value, max_length=max_length)
        if not text:
            return ""
        source_suffix = _format_source_suffix({}, youtube_video_id, chunks, fallback_text=text)
        return _clean_text(f"{text}{source_suffix}", max_length=max_length)
    if not isinstance(value, dict):
        return ""

    label = _first_clean_text(
        value,
        (
            "name",
            "title",
            "label",
            "topic",
            "person",
            "organization",
            "company",
            "tool",
            "system",
            "claim",
            "decision",
            "time",
            "timestamp",
        ),
        max_length=180,
    )
    parts = []
    for key in (
        "type",
        "role",
        "summary",
        "description",
        "detail",
        "takeaway",
        "context",
        "mechanism",
        "specifics",
        "example",
        "examples",
        "why_it_matters",
        "whyItMatters",
        "implication",
        "tradeoff",
        "risk",
        "caveat",
        "retrieval_hint",
        "retrievalHint",
        "result_hint",
        "resultHint",
        "what_to_retrieve",
        "whatToRetrieve",
        "query",
        "evidence",
        "supporting_evidence",
        "supportingEvidence",
        "source_note",
        "sourceNote",
        "action",
        "status",
    ):
        text = _value_to_text(value.get(key), max_length=700)
        if text and text.lower() != label.lower():
            parts.append(text)

    body = "; ".join(dict.fromkeys(parts))
    if label and body:
        separator = " " if label.endswith((".", "?", "!", ":")) else ": "
        text = f"{label}{separator}{body}"
    else:
        text = label or body

    source_suffix = _format_source_suffix(value, youtube_video_id, chunks, fallback_text=text)
    return _clean_text(f"{text}{source_suffix}", max_length=max_length)


def _value_to_text(value: Any, max_length: int = 320) -> str:
    if isinstance(value, str):
        return _clean_text(value, max_length=max_length)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, list):
        parts = [_value_to_text(item, max_length=220) for item in value[:6]]
        return _clean_text(", ".join(part for part in parts if part), max_length=max_length)
    if isinstance(value, dict):
        name = _first_clean_text(value, ("name", "title", "label", "summary"), max_length=180)
        if name:
            return name
        parts = []
        for key, item in list(value.items())[:4]:
            item_text = _value_to_text(item, max_length=90)
            if item_text:
                parts.append(f"{_humanize_key(str(key))}: {item_text}")
        return _clean_text("; ".join(parts), max_length=max_length)
    return ""


def _first_clean_text(value: dict, keys: tuple[str, ...], max_length: int = 180) -> str:
    for key in keys:
        text = _clean_text(value.get(key), max_length=max_length)
        if text:
            return text
    return ""


def _humanize_key(value: str) -> str:
    return value.replace("_", " ").replace("-", " ").strip().title()


def _format_source_suffix(
    value: dict,
    youtube_video_id: str | None,
    chunks: list[dict],
    fallback_text: str = "",
) -> str:
    refs = (
        value.get("source_refs")
        or value.get("sourceRefs")
        or value.get("source_ref")
        or value.get("evidence_refs")
        or value.get("citations")
    )
    if refs is None and "start_seconds" in value:
        refs = [
            {"start_seconds": value.get("start_seconds"), "end_seconds": value.get("end_seconds")}
        ]
    if refs is None and "clip_index" in value:
        refs = [{"clip_index": value.get("clip_index")}]

    if youtube_video_id:
        normalized = _normalize_source_refs(refs, youtube_video_id, chunks)
        if not normalized and fallback_text:
            normalized = _infer_source_refs_for_text(
                fallback_text, youtube_video_id, chunks, limit=1
            )
    else:
        normalized = _raw_timestamp_refs(refs)
    labels = []
    for ref in normalized[:3]:
        start = _coerce_seconds(ref.get("start_seconds"))
        if start is None:
            continue
        labels.append(_format_timestamp(start))
    if not labels:
        return ""
    return f" (source: {', '.join(labels)})"


def _raw_timestamp_refs(refs: Any) -> list[dict]:
    if isinstance(refs, dict):
        refs = [refs]
    if not isinstance(refs, list):
        return []
    return [ref for ref in refs if isinstance(ref, dict)]


def _format_timestamp(seconds: int) -> str:
    hours, remainder = divmod(max(0, int(seconds)), 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def _artifact_source_refs(
    video_ref: dict,
    study_guide: Any,
    youtube_video_id: str,
    chunks: list[dict],
    fallback_text: str = "",
) -> list[dict]:
    refs = [video_ref]
    seen = {
        (
            video_ref.get("source_type"),
            video_ref.get("start_seconds"),
            video_ref.get("end_seconds"),
        )
    }
    for raw in _collect_source_ref_values(study_guide):
        for ref in _normalize_source_refs(raw, youtube_video_id, chunks):
            key = (ref.get("source_type"), ref.get("start_seconds"), ref.get("end_seconds"))
            if key in seen:
                continue
            refs.append(ref)
            seen.add(key)
            if len(refs) >= MAX_SOURCE_REFS:
                return refs
    if len(refs) <= 1 and fallback_text:
        for ref in _infer_source_refs_for_text(
            fallback_text,
            youtube_video_id,
            chunks,
            limit=MAX_SOURCE_REFS - 1,
        ):
            key = (ref.get("source_type"), ref.get("start_seconds"), ref.get("end_seconds"))
            if key in seen:
                continue
            refs.append(ref)
            seen.add(key)
            if len(refs) >= MAX_SOURCE_REFS:
                return refs
    return refs


def _collect_source_ref_values(value: Any) -> list[Any]:
    if isinstance(value, dict):
        refs = []
        for key, item in value.items():
            if key in {"source_refs", "sourceRefs", "source_ref", "evidence_refs", "citations"}:
                refs.append(item)
            else:
                refs.extend(_collect_source_ref_values(item))
        return refs
    if isinstance(value, list):
        refs = []
        for item in value:
            refs.extend(_collect_source_ref_values(item))
        return refs
    return []


def _video_ref(youtube_video_id: str, chunks: list[dict]) -> dict:
    end_seconds = 0
    if chunks:
        end_seconds = max(int(chunk.get("end_seconds", 0) or 0) for chunk in chunks)
    return {
        "source_type": "video",
        "youtube_video_id": youtube_video_id,
        "start_seconds": 0,
        "end_seconds": end_seconds,
    }


def _coerce_seconds(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _clean_text(value: Any, max_length: int) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.split())[:max_length].strip()


def _empty_extraction() -> dict:
    return {"concepts": [], "labels": [], "edges": [], "artifacts": []}
