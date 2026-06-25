"""Lightweight ingestion cost estimates for user/agent preflight surfaces."""

from __future__ import annotations

from typing import Any

try:
    from .config import get_free_max_import_videos
    from .digest_depth import (
        DEFAULT_DIGEST_DEPTH,
        digest_llm_calls_per_video,
        get_digest_depth_profile,
        normalize_digest_depth,
    )
except ImportError:
    from config import get_free_max_import_videos
    from digest_depth import (
        DEFAULT_DIGEST_DEPTH,
        digest_llm_calls_per_video,
        get_digest_depth_profile,
        normalize_digest_depth,
    )

ESTIMATE_VERSION = "ingestion-cost-estimate-v1"
DEFAULT_SECONDS_PER_VIDEO = 900
DEFAULT_CHARS_PER_SECOND = 16
DEFAULT_CHUNK_SECONDS = 60
DEFAULT_DIGEST_PROMPT_OVERHEAD_TOKENS = 1200

GEMINI_EMBEDDING_STANDARD_INPUT_USD_PER_1M = 0.15
GEMINI_EMBEDDING_BATCH_INPUT_USD_PER_1M = 0.075
GEMINI_FLASH_LITE_STANDARD_INPUT_USD_PER_1M = 0.25
GEMINI_FLASH_LITE_STANDARD_OUTPUT_USD_PER_1M = 1.50
PRICING_SOURCE = "https://ai.google.dev/gemini-api/docs/pricing"


def build_ingestion_cost_estimate(
    supabase: Any | None,
    user_id: str,
    source_url: str,
    source_type: str,
    discovered_video_ids: list[str] | None = None,
    digest_depth: str = DEFAULT_DIGEST_DEPTH,
) -> dict:
    """Return a conservative estimate before expensive transcript/embedding work.

    Estimates intentionally avoid fetching transcripts or embedding text. When
    candidate video IDs are known, already-indexed canonical videos can be
    counted precisely; otherwise playlist/channel values are bounded by the
    hosted import cap and marked as estimates.
    """
    normalized_source_type = (
        source_type if source_type in {"video", "playlist", "channel"} else "unknown"
    )
    normalized_digest_depth = normalize_digest_depth(digest_depth)
    digest_profile = get_digest_depth_profile(normalized_digest_depth)
    candidates = _dedupe_video_ids(discovered_video_ids or [])
    if not candidates and normalized_source_type == "video":
        candidates = (
            [_extract_video_id_from_url(source_url)]
            if _extract_video_id_from_url(source_url)
            else []
        )

    import_cap = get_free_max_import_videos()
    discovered_count = len(candidates)
    estimated_discovered = False
    if not discovered_count:
        if normalized_source_type == "video":
            discovered_count = 1
        elif normalized_source_type in {"playlist", "channel"}:
            discovered_count = import_cap
            estimated_discovered = True

    candidate_ids = candidates[:import_cap] if candidates else []
    already_indexed_ids = _already_indexed_video_ids(supabase, candidate_ids)
    already_indexed_count = len(already_indexed_ids)
    videos_to_embed = max(0, min(discovered_count, import_cap) - already_indexed_count)
    estimated_seconds = videos_to_embed * DEFAULT_SECONDS_PER_VIDEO
    estimated_chars = estimated_seconds * DEFAULT_CHARS_PER_SECOND
    estimated_embedding_tokens = max(0, estimated_chars // 4)
    estimated_digest_calls = videos_to_embed * digest_llm_calls_per_video(normalized_digest_depth)
    estimated_digest_input_tokens = _estimated_digest_input_tokens(
        videos_to_embed,
        normalized_digest_depth,
        digest_profile,
    )
    estimated_digest_output_budget_tokens = estimated_digest_calls * int(
        digest_profile.get("max_output_tokens") or 0
    )
    model_cost = _estimate_model_cost(
        estimated_embedding_tokens,
        estimated_digest_input_tokens,
        estimated_digest_output_budget_tokens,
    )

    return {
        "version": ESTIMATE_VERSION,
        "sourceType": normalized_source_type,
        "sourceUrl": source_url,
        "userId": user_id,
        "discoveredVideos": discovered_count,
        "discoveredVideosEstimated": estimated_discovered,
        "alreadyIndexedVideos": already_indexed_count,
        "alreadyIndexedVideoIds": sorted(already_indexed_ids),
        "videosToEmbed": videos_to_embed,
        "maxVideosThisRun": import_cap,
        "digestDepth": normalized_digest_depth,
        "digestDepthDescription": digest_profile["description"],
        "estimatedTranscriptSeconds": estimated_seconds,
        "estimatedEmbeddingChars": estimated_chars,
        "estimatedEmbeddingTokens": estimated_embedding_tokens,
        "estimatedEmbeddingBatches": videos_to_embed,
        "estimatedDigestLlmCalls": estimated_digest_calls,
        "estimatedDigestInputTokens": estimated_digest_input_tokens,
        "estimatedDigestOutputTokenBudget": estimated_digest_output_budget_tokens,
        "estimatedModelCostUsd": model_cost,
        "generationPolicy": _generation_policy(normalized_digest_depth),
        "assumptions": {
            "secondsPerNewVideo": DEFAULT_SECONDS_PER_VIDEO,
            "charsPerTranscriptSecond": DEFAULT_CHARS_PER_SECOND,
            "chunkSeconds": DEFAULT_CHUNK_SECONDS,
            "digestPromptOverheadTokensPerCall": DEFAULT_DIGEST_PROMPT_OVERHEAD_TOKENS,
            "noTranscriptFetchInEstimate": True,
            "alreadyIndexedVideosNeedNoEmbeddingCompute": True,
            "digestDepthProfile": digest_profile,
            "pricing": {
                "source": PRICING_SOURCE,
                "embeddingModel": "gemini-embedding-001",
                "embeddingStandardInputUsdPer1MTokens": GEMINI_EMBEDDING_STANDARD_INPUT_USD_PER_1M,
                "embeddingBatchInputUsdPer1MTokens": GEMINI_EMBEDDING_BATCH_INPUT_USD_PER_1M,
                "digestModel": "gemini-3.1-flash-lite",
                "digestStandardInputUsdPer1MTokens": GEMINI_FLASH_LITE_STANDARD_INPUT_USD_PER_1M,
                "digestStandardOutputUsdPer1MTokens": GEMINI_FLASH_LITE_STANDARD_OUTPUT_USD_PER_1M,
                "digestOutputIsUpperBound": True,
            },
        },
        "riskLevel": _risk_level(videos_to_embed),
        "guidance": _estimate_guidance(
            normalized_source_type,
            videos_to_embed,
            estimated_discovered,
            normalized_digest_depth,
        ),
    }


def _estimated_digest_input_tokens(
    videos_to_embed: int,
    digest_depth: str,
    digest_profile: dict,
) -> int:
    calls = videos_to_embed * digest_llm_calls_per_video(digest_depth)
    if calls <= 0:
        return 0
    transcript_tokens = int(digest_profile.get("max_transcript_chars") or 0) // 4
    return calls * (transcript_tokens + DEFAULT_DIGEST_PROMPT_OVERHEAD_TOKENS)


def _estimate_model_cost(
    embedding_tokens: int,
    digest_input_tokens: int,
    digest_output_budget_tokens: int,
) -> dict:
    embedding_cost = _cost_usd(
        embedding_tokens,
        GEMINI_EMBEDDING_STANDARD_INPUT_USD_PER_1M,
    )
    digest_input_cost = _cost_usd(
        digest_input_tokens,
        GEMINI_FLASH_LITE_STANDARD_INPUT_USD_PER_1M,
    )
    digest_output_budget_cost = _cost_usd(
        digest_output_budget_tokens,
        GEMINI_FLASH_LITE_STANDARD_OUTPUT_USD_PER_1M,
    )
    return {
        "embeddingStandardUsd": embedding_cost,
        "embeddingBatchUsd": _cost_usd(
            embedding_tokens,
            GEMINI_EMBEDDING_BATCH_INPUT_USD_PER_1M,
        ),
        "digestInputUsd": digest_input_cost,
        "digestOutputBudgetUsd": digest_output_budget_cost,
        "totalStandardUpperBoundUsd": round(
            embedding_cost + digest_input_cost + digest_output_budget_cost,
            6,
        ),
        "notes": [
            "Digest output cost is an upper bound based on max_output_tokens; actual generated tokens may be lower.",
            "Storage, worker runtime, YouTube quota, and downstream agent model usage are not included.",
        ],
    }


def _cost_usd(tokens: int, usd_per_1m: float) -> float:
    return round((max(0, tokens) / 1_000_000) * usd_per_1m, 6)


def _generation_policy(digest_depth: str) -> dict:
    if digest_depth == "none":
        ingestion_generated = ["transcript_lines", "timestamped_chunks", "embeddings"]
    elif digest_depth == "basic":
        ingestion_generated = [
            "transcript_lines",
            "timestamped_chunks",
            "embeddings",
            "compact_labels",
            "core_topic_cards",
            "tldr",
        ]
    else:
        ingestion_generated = [
            "transcript_lines",
            "timestamped_chunks",
            "embeddings",
            "labels",
            "topic_cards",
            "claim_cards",
            "timeline_entries",
            "source_backed_report",
        ]
    return {
        "ingestionGenerated": ingestion_generated,
        "mcpAgentShouldGenerateOnDemand": [
            "task_specific_answer",
            "repo_or_project_application",
            "cross_video_synthesis",
            "custom_report_for_current_user_goal",
            "long-form final narrative",
        ],
        "recommendedDefault": (
            "standard_for_all_indexed_videos_length_adaptive_basic_or_none_only_for_explicit_cost_saving"
        ),
        "rationale": (
            "Every indexed video should receive the same analysis contract. Ingestion creates "
            "reusable navigation and evidence objects once, while report length scales with "
            "transcript duration and information density; MCP agents spend their own context "
            "budget on the user's current task."
        ),
    }


def _dedupe_video_ids(video_ids: list[str]) -> list[str]:
    deduped = []
    seen = set()
    for raw_id in video_ids:
        video_id = str(raw_id or "").strip()
        if not video_id or video_id in seen:
            continue
        seen.add(video_id)
        deduped.append(video_id)
    return deduped


def _extract_video_id_from_url(url: str) -> str:
    if "youtu.be/" in url:
        return url.rsplit("youtu.be/", 1)[-1].split("?", 1)[0].split("&", 1)[0].strip("/")
    if "v=" in url:
        return url.split("v=", 1)[-1].split("&", 1)[0].strip()
    return ""


def _already_indexed_video_ids(supabase: Any | None, youtube_video_ids: list[str]) -> set[str]:
    if supabase is None or not youtube_video_ids:
        return set()
    try:
        result = (
            supabase.table("videos")
            .select("youtube_video_id")
            .in_("youtube_video_id", youtube_video_ids)
            .execute()
        )
    except Exception:
        return set()
    rows = getattr(result, "data", None) or []
    return {
        row.get("youtube_video_id")
        for row in rows
        if isinstance(row, dict) and isinstance(row.get("youtube_video_id"), str)
    }


def _risk_level(videos_to_embed: int) -> str:
    if videos_to_embed <= 1:
        return "low"
    if videos_to_embed <= 5:
        return "medium"
    return "high"


def _estimate_guidance(
    source_type: str,
    videos_to_embed: int,
    estimated_discovered: bool,
    digest_depth: str,
) -> str:
    if videos_to_embed == 0:
        return "All known videos appear to be indexed already; this should grant access without new embedding compute."
    if digest_depth == "none":
        return (
            "Digest depth is none, so ingestion stores transcript/search rows without LLM "
            "source-knowledge extraction."
        )
    if source_type in {"playlist", "channel"} and estimated_discovered:
        return (
            "Bulk estimate is capped by the hosted import limit because items have not been "
            "discovered yet. Run a bounded playlist sync or approve bulk ingestion only when "
            "the user expects this spend."
        )
    return "Estimate uses transcript-duration defaults until captions are fetched during ingestion."
