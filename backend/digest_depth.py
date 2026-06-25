"""Digest-depth controls for transcript-derived source knowledge."""

from __future__ import annotations

from typing import Any

DIGEST_DEPTH_NONE = "none"
DIGEST_DEPTH_BASIC = "basic"
DIGEST_DEPTH_STANDARD = "standard"
DIGEST_DEPTH_DEEP = "deep"

DEFAULT_DIGEST_DEPTH = DIGEST_DEPTH_STANDARD
DIGEST_DEPTH_VALUES = (
    DIGEST_DEPTH_NONE,
    DIGEST_DEPTH_BASIC,
    DIGEST_DEPTH_STANDARD,
    DIGEST_DEPTH_DEEP,
)

DIGEST_DEPTH_PROFILES = {
    DIGEST_DEPTH_NONE: {
        "description": "Store transcript lines only; skip LLM source-knowledge digestion.",
        "llm_calls_per_video": 0,
        "max_transcript_chars": 0,
        "max_concepts": 0,
        "max_edges": 0,
        "max_labels": 0,
        "artifact_types": [],
        "max_output_tokens": 0,
    },
    DIGEST_DEPTH_BASIC: {
        "description": "Create compact labels, core concepts, and a TLDR.",
        "llm_calls_per_video": 1,
        "max_transcript_chars": 9_000,
        "max_concepts": 6,
        "max_edges": 0,
        "max_labels": 8,
        "artifact_types": ["tldr"],
        "max_output_tokens": 1024,
    },
    DIGEST_DEPTH_STANDARD: {
        "description": "Create labels, concepts, relationships, TLDR, and source report.",
        "llm_calls_per_video": 1,
        "max_transcript_chars": 18_000,
        "max_concepts": 14,
        "max_edges": 18,
        "max_labels": 20,
        "artifact_types": ["tldr", "study_guide"],
        "max_output_tokens": 6144,
    },
    DIGEST_DEPTH_DEEP: {
        "description": "Use a larger transcript window and richer concept/relationship budget.",
        "llm_calls_per_video": 1,
        "max_transcript_chars": 30_000,
        "max_concepts": 24,
        "max_edges": 30,
        "max_labels": 32,
        "artifact_types": ["tldr", "study_guide"],
        "max_output_tokens": 12288,
    },
}


def normalize_digest_depth(value: Any) -> str:
    """Return a supported digest depth, defaulting to standard."""
    if isinstance(value, str):
        normalized = value.strip().lower().replace("-", "_")
        if normalized in DIGEST_DEPTH_VALUES:
            return normalized
    return DEFAULT_DIGEST_DEPTH


def get_digest_depth_profile(value: Any) -> dict:
    """Return the immutable profile for a digest depth."""
    return DIGEST_DEPTH_PROFILES[normalize_digest_depth(value)]


def digest_llm_calls_per_video(value: Any) -> int:
    """Return estimated LLM extraction calls per newly embedded video."""
    return int(get_digest_depth_profile(value)["llm_calls_per_video"])
