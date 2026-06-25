"""Evaluate source-knowledge discoverability without transcript scanning.

This offline eval models the MCP path:
search_video_concepts -> get_video_knowledge_map -> search_video_moments.
It does not call Supabase, Gemini, or an LLM. The goal is to keep a small,
deterministic gate for whether generated source objects are navigable by query.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE = ROOT / "eval" / "fixtures" / "source_knowledge_discoverability.json"

STOPWORDS = {
    "about",
    "actually",
    "agent",
    "agents",
    "and",
    "are",
    "does",
    "for",
    "from",
    "how",
    "into",
    "rather",
    "should",
    "task",
    "than",
    "the",
    "this",
    "use",
    "what",
    "when",
    "where",
    "which",
    "why",
    "with",
}


def tokenize(value: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-zA-Z0-9+#.-]+", value.lower())
        if len(token) >= 3 and token not in STOPWORDS
    ]


def score_row(query: str, row: dict) -> float:
    terms = tokenize(query)
    if not terms:
        return 0.0
    title = str(row.get("title") or "").lower()
    aliases = " ".join(row.get("aliases") or []).lower()
    body = str(row.get("body") or "").lower()
    haystack = f"{title}\n{aliases}\n{body}"
    score = 0.0
    for term in terms:
        score += body.count(term)
        score += aliases.count(term) * 3
        score += title.count(term) * 4
    matched = sum(1 for term in terms if term in haystack)
    score += matched / max(len(terms), 1)
    if all(term in haystack for term in terms):
        score += 6
    if row.get("sourceRefs"):
        score += 0.25
    if row.get("resultType") in {"source_concept", "report_section"}:
        score += 0.1
    return round(score, 4)


def rank_source_knowledge(query: str, rows: list[dict], limit: int = 5) -> list[dict]:
    ranked = []
    for row in rows:
        score = score_row(query, row)
        if score <= 0:
            continue
        ranked.append(
            {
                "id": row["id"],
                "videoId": row["videoId"],
                "resultType": row["resultType"],
                "title": row["title"],
                "score": score,
                "sourceRefs": row.get("sourceRefs") or [],
                "snippet": " ".join(str(row.get("body") or "").split())[:220],
            }
        )
    ranked.sort(key=lambda item: (-float(item["score"]), item["videoId"], item["title"]))
    return ranked[:limit]


def _has_expected_object(results: list[dict], expected_ids: list[str]) -> bool:
    returned = {row["id"] for row in results}
    return bool(returned.intersection(expected_ids))


def _has_expected_video(results: list[dict], expected_ids: list[str]) -> bool:
    returned = {row["videoId"] for row in results}
    return bool(returned.intersection(expected_ids))


def _has_expected_timestamp(results: list[dict], expected_ranges: list[dict]) -> bool:
    for row in results:
        for ref in row.get("sourceRefs") or []:
            if not isinstance(ref, dict):
                continue
            ref_video = ref.get("youtube_video_id") or row.get("videoId")
            ref_start = ref.get("start_seconds")
            if not isinstance(ref_start, (int, float)) or isinstance(ref_start, bool):
                continue
            for expected in expected_ranges:
                if ref_video != expected.get("videoId"):
                    continue
                if int(expected["start"]) <= int(ref_start) <= int(expected["end"]):
                    return True
    return False


def _top_result_wrong_video(results: list[dict], expected_ids: list[str]) -> bool:
    return bool(results) and results[0].get("videoId") not in set(expected_ids)


def _response_bytes(results: list[dict]) -> int:
    compact = [
        {
            "id": row["id"],
            "videoId": row["videoId"],
            "resultType": row["resultType"],
            "title": row["title"],
            "score": row["score"],
            "sourceRefs": row.get("sourceRefs") or [],
            "snippet": row.get("snippet") or "",
        }
        for row in results
    ]
    return len(json.dumps({"results": compact}, ensure_ascii=False, separators=(",", ":")))


def evaluate_fixture(fixture: dict, limit: int = 5) -> dict:
    rows = fixture["sourceKnowledge"]
    query_reports = []
    object_hits = 0
    video_hits = 0
    timestamp_hits = 0
    wrong_video_hits = 0
    transcript_avoidance_hits = 0
    response_sizes: list[int] = []

    for query in fixture["queries"]:
        results = rank_source_knowledge(query["query"], rows, limit)
        object_hit = _has_expected_object(results, query["expectedObjectIds"])
        video_hit = _has_expected_video(results, query["expectedVideoIds"])
        timestamp_hit = _has_expected_timestamp(results, query["expectedTimestampRanges"])
        wrong_video = _top_result_wrong_video(results, query["expectedVideoIds"])
        transcript_avoided = all(row.get("resultType") != "transcript_chunk" for row in results)
        response_bytes = _response_bytes(results)

        object_hits += int(object_hit)
        video_hits += int(video_hit)
        timestamp_hits += int(timestamp_hit)
        wrong_video_hits += int(wrong_video)
        transcript_avoidance_hits += int(transcript_avoided)
        response_sizes.append(response_bytes)
        query_reports.append(
            {
                "id": query["id"],
                "query": query["query"],
                "objectHit": object_hit,
                "videoHit": video_hit,
                "timestampHit": timestamp_hit,
                "wrongVideo": wrong_video,
                "transcriptAvoided": transcript_avoided,
                "responseBytes": response_bytes,
                "topResults": results,
            }
        )

    total = max(len(fixture["queries"]), 1)
    metrics = {
        "objectRecallAt5": round(object_hits / total, 3),
        "videoRecallAt5": round(video_hits / total, 3),
        "timestampHitRate": round(timestamp_hits / total, 3),
        "wrongVideoRate": round(wrong_video_hits / total, 3),
        "averageResponseBytes": round(sum(response_sizes) / max(len(response_sizes), 1), 1),
        "transcriptAvoidanceRate": round(transcript_avoidance_hits / total, 3),
    }
    bar = fixture.get("passingBar") or {}
    passed = (
        metrics["objectRecallAt5"] >= float(bar.get("objectRecallAt5", 0.85))
        and metrics["videoRecallAt5"] >= float(bar.get("videoRecallAt5", 0.9))
        and metrics["timestampHitRate"] >= float(bar.get("timestampHitRate", 0.75))
        and metrics["wrongVideoRate"] <= float(bar.get("maxWrongVideoRate", 0.2))
        and metrics["transcriptAvoidanceRate"] >= float(bar.get("minTranscriptAvoidanceRate", 0.9))
    )
    return {
        "fixture": fixture["name"],
        "version": fixture.get("version"),
        "passed": passed,
        "metrics": metrics,
        "passingBar": bar,
        "queries": query_reports,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", default=str(DEFAULT_FIXTURE))
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()

    fixture = json.loads(Path(args.fixture).read_text(encoding="utf-8"))
    report = evaluate_fixture(fixture, limit=args.limit)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
