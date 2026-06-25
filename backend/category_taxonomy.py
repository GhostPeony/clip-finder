"""Agent-facing taxonomy for categorizing saved video knowledge."""

from __future__ import annotations

from typing import Any

CATEGORY_TAXONOMY_VERSION = "video-category-taxonomy-v1"

CATEGORY_FACETS: dict[str, dict[str, Any]] = {
    "domain": {
        "description": "Broad area the video belongs to.",
        "examples": ["cooking", "history", "home repair", "music", "fitness", "AI/ML"],
    },
    "content_type": {
        "description": "Form of the source content.",
        "examples": ["podcast", "tutorial", "lecture", "demo", "documentary", "review"],
    },
    "topic": {
        "description": "Specific subject matter or theme.",
        "examples": [
            "sourdough starter",
            "Roman history",
            "guitar improvisation",
            "agent architecture",
        ],
    },
    "task_fit": {
        "description": "Work this source can help with.",
        "examples": [
            "study guide",
            "lesson plan",
            "troubleshooting",
            "buying decision",
            "implementation plan",
        ],
    },
    "method": {
        "description": "Method, process, or pattern explained by the source.",
        "examples": [
            "kneading technique",
            "practice routine",
            "diagnostic workflow",
            "harness-driven development",
        ],
    },
    "tool": {
        "description": "Software, physical tool, material, model, framework, or platform discussed.",
        "examples": ["Dutch oven", "torque wrench", "Ableton", "Supabase", "pgvector"],
    },
    "entity": {
        "description": "Person, place, organization, product, paper, project, or named system.",
        "examples": ["Sierra", "Julia Child", "NASA", "Bach", "Gemini"],
    },
    "difficulty": {
        "description": "Learning depth needed to apply the source.",
        "examples": ["introductory", "intermediate", "advanced"],
    },
    "maturity": {
        "description": "How production-ready or speculative the idea is.",
        "examples": ["introductory overview", "field-tested", "case study", "research"],
    },
    "evidence_quality": {
        "description": "How directly the transcript supports the extracted idea.",
        "examples": ["direct explanation", "anecdotal", "implementation detail", "opinion"],
    },
}

DEFAULT_FACET_ORDER = list(CATEGORY_FACETS.keys())


def get_category_taxonomy() -> dict:
    """Return the stable agent-facing video category taxonomy."""
    return {
        "version": CATEGORY_TAXONOMY_VERSION,
        "facets": CATEGORY_FACETS,
        "facetOrder": DEFAULT_FACET_ORDER,
        "filterSemantics": {
            "withinFacet": "OR",
            "acrossFacets": "AND",
            "matching": "case-insensitive exact label match after whitespace normalization",
        },
        "recommendedAgentFlow": [
            "Call list_context_categories to inspect available facets.",
            "Choose narrow topic, task_fit, method, tool, or difficulty filters when the query is broad.",
            "Pass category_filters into build_context_bundle or build_agent_brief.",
            "Use search_video_moments for timestamp evidence after narrowing the library.",
        ],
    }


def normalize_category_filters(filters: Any) -> dict[str, list[str]]:
    """Normalize category filter input from REST or MCP callers."""
    if not isinstance(filters, dict):
        return {}

    normalized: dict[str, list[str]] = {}
    for raw_key, raw_values in filters.items():
        key = _normalize_facet_name(raw_key)
        if key not in CATEGORY_FACETS:
            continue

        if isinstance(raw_values, str):
            values = [raw_values]
        elif isinstance(raw_values, list):
            values = raw_values
        else:
            continue

        cleaned_values = []
        seen_values = set()
        for value in values:
            if not isinstance(value, str):
                continue
            cleaned = _normalize_label(value)
            if not cleaned or cleaned.lower() in seen_values:
                continue
            seen_values.add(cleaned.lower())
            cleaned_values.append(cleaned)
        if cleaned_values:
            normalized[key] = cleaned_values[:12]

    return normalized


def labels_match_category_filters(labels: list[dict], filters: dict[str, list[str]]) -> bool:
    """Return whether a video's labels satisfy normalized category filters."""
    if not filters:
        return True

    labels_by_type: dict[str, set[str]] = {}
    for row in labels:
        label_type = _normalize_facet_name(row.get("label_type"))
        label = _normalize_label(row.get("label")).lower()
        if not label_type or not label:
            continue
        labels_by_type.setdefault(label_type, set()).add(label)

    for label_type, expected_labels in filters.items():
        available = labels_by_type.get(label_type, set())
        expected = {_normalize_label(label).lower() for label in expected_labels}
        if not available.intersection(expected):
            return False
    return True


def category_filter_examples() -> list[dict[str, list[str]]]:
    """Return examples agents can copy when narrowing saved-video context."""
    return [
        {"task_fit": ["study guide"], "difficulty": ["introductory"]},
        {"method": ["diagnostic workflow"], "task_fit": ["troubleshooting"]},
        {"tool": ["MCP"], "task_fit": ["implementation plan"]},
    ]


def _normalize_facet_name(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return "_".join(value.lower().strip().replace("-", "_").split())


def _normalize_label(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.split())[:120].strip()
