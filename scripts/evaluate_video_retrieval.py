"""Evaluate saved-video retrieval fixtures against local offline corpora.

This runner is intentionally cheap: it uses lexical scoring over the legacy
Chroma transcript chunks and the Sierra sample's generated concepts/artifacts.
Hosted semantic/hybrid retrieval can later use the same fixture to compare
against Supabase MCP results after migration.
"""

# ruff: noqa: E402,I001

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.legacy_chroma_supabase_import import DEFAULT_CHROMA_DB, load_legacy_chunks
from scripts.run_sierra_sample_eval import build_sample_tables, load_fixture as load_sierra_fixture

DEFAULT_FIXTURE = ROOT / "eval" / "fixtures" / "video_retrieval_queries.json"

STOPWORDS = {
    "about",
    "after",
    "agent",
    "agents",
    "and",
    "are",
    "does",
    "for",
    "from",
    "how",
    "into",
    "the",
    "their",
    "this",
    "that",
    "what",
    "when",
    "where",
    "which",
    "why",
    "with",
}


@dataclass(frozen=True)
class RetrievalDoc:
    id: str
    video_id: str
    title: str
    text: str
    start_seconds: float | None = None
    end_seconds: float | None = None
    source: str = "transcript"


def tokenize(value: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-zA-Z0-9+#.-]+", value.lower())
        if len(token) >= 3 and token not in STOPWORDS
    ]


def score_document(query: str, doc: RetrievalDoc) -> float:
    terms = tokenize(query)
    if not terms:
        return 0.0
    title = doc.title.lower()
    text = doc.text.lower()
    haystack = f"{title}\n{text}"
    score = 0.0
    for term in terms:
        score += text.count(term)
        score += title.count(term) * 3
    phrase = " ".join(terms)
    if phrase and phrase in haystack:
        score += 8
    if all(term in haystack for term in terms):
        score += 6
    return score


def rank_docs(query: str, docs: list[RetrievalDoc], limit: int) -> list[dict]:
    scored = [
        {
            "docId": doc.id,
            "videoId": doc.video_id,
            "title": doc.title,
            "score": round(score, 3),
            "startSeconds": doc.start_seconds,
            "endSeconds": doc.end_seconds,
            "source": doc.source,
            "snippet": " ".join(doc.text.split())[:220],
        }
        for doc in docs
        if (score := score_document(query, doc)) > 0
    ]
    scored.sort(key=lambda row: row["score"], reverse=True)
    return scored[:limit]


def collapse_video_rankings(ranked_docs: list[dict]) -> list[dict]:
    by_video: dict[str, dict] = {}
    for row in ranked_docs:
        current = by_video.get(row["videoId"])
        if current is None or row["score"] > current["score"]:
            by_video[row["videoId"]] = row
    return sorted(by_video.values(), key=lambda row: row["score"], reverse=True)


def reciprocal_rank(ranked_video_ids: list[str], expected_video_ids: list[str]) -> float:
    expected = set(expected_video_ids)
    for index, video_id in enumerate(ranked_video_ids, start=1):
        if video_id in expected:
            return 1 / index
    return 0.0


def timestamp_hit(
    ranked_docs: list[dict], expected_video_ids: list[str], ranges: list[dict]
) -> bool:
    if not ranges:
        return False
    expected = set(expected_video_ids)
    for row in ranked_docs:
        if row["videoId"] not in expected:
            continue
        start = row.get("startSeconds")
        end = row.get("endSeconds")
        if start is None or end is None:
            continue
        for expected_range in ranges:
            if end >= expected_range["start"] and start <= expected_range["end"]:
                return True
    return False


def load_legacy_docs(db_path: Path = DEFAULT_CHROMA_DB) -> list[RetrievalDoc]:
    return [
        RetrievalDoc(
            id=f"{chunk.youtube_video_id}:{chunk.start_seconds}",
            video_id=chunk.youtube_video_id,
            title=chunk.title,
            text=chunk.content,
            start_seconds=chunk.start_seconds,
            end_seconds=chunk.end_seconds,
            source="legacy_chroma_chunk",
        )
        for chunk in load_legacy_chunks(db_path)
    ]


def load_sierra_docs() -> list[RetrievalDoc]:
    fixture = load_sierra_fixture()
    tables = build_sample_tables(fixture)
    video = fixture["video"]
    docs: list[RetrievalDoc] = []
    for row in tables["source_concepts"]:
        docs.append(
            RetrievalDoc(
                id=row["id"],
                video_id=video["youtubeVideoId"],
                title=row["name"],
                text=f"{row['concept_type']} {row['summary']}",
                source="sierra_source_concept",
            )
        )
    for row in tables["knowledge_artifacts"]:
        docs.append(
            RetrievalDoc(
                id=row["id"],
                video_id=video["youtubeVideoId"],
                title=row["title"],
                text=f"{row['artifact_type']} {row['summary']} {row['content']}",
                source="sierra_knowledge_artifact",
            )
        )
    return docs


def evaluate_fixture(
    fixture: dict, *, legacy_db_path: Path = DEFAULT_CHROMA_DB, limit: int = 10
) -> dict:
    docs_by_corpus = {
        "legacy_chroma": load_legacy_docs(legacy_db_path),
        "sierra_sample": load_sierra_docs(),
    }
    rows = []
    recall_hits = 0
    wrong_top = 0
    mrr_total = 0.0
    timestamp_queries = 0
    timestamp_hits = 0

    for item in fixture["queries"]:
        docs = docs_by_corpus[item["corpus"]]
        ranked_docs = rank_docs(item["query"], docs, limit)
        ranked_videos = collapse_video_rankings(ranked_docs)
        ranked_video_ids = [row["videoId"] for row in ranked_videos]
        expected_video_ids = item["expectedVideoIds"]
        hit = bool(set(ranked_video_ids[:5]).intersection(expected_video_ids))
        recall_hits += int(hit)
        mrr = reciprocal_rank(ranked_video_ids, expected_video_ids)
        mrr_total += mrr
        if ranked_video_ids and ranked_video_ids[0] not in set(expected_video_ids):
            wrong_top += 1
        ranges = item.get("expectedTimestampRanges") or []
        ts_hit = timestamp_hit(ranked_docs[:5], expected_video_ids, ranges)
        if ranges:
            timestamp_queries += 1
            timestamp_hits += int(ts_hit)
        rows.append(
            {
                "id": item["id"],
                "corpus": item["corpus"],
                "query": item["query"],
                "expectedVideoIds": expected_video_ids,
                "topVideoIds": ranked_video_ids[:5],
                "topDocs": ranked_docs[:3],
                "recallAt5Hit": hit,
                "mrr": round(mrr, 3),
                "timestampHit": ts_hit if ranges else None,
            }
        )

    query_count = len(fixture["queries"])
    return {
        "fixture": fixture["name"],
        "queryCount": query_count,
        "metrics": {
            "recallAt5": round(recall_hits / query_count, 3) if query_count else 0,
            "mrr": round(mrr_total / query_count, 3) if query_count else 0,
            "timestampHitRate": (
                round(timestamp_hits / timestamp_queries, 3) if timestamp_queries else None
            ),
            "wrongTopVideoRate": round(wrong_top / query_count, 3) if query_count else 0,
        },
        "results": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", default=str(DEFAULT_FIXTURE))
    parser.add_argument("--legacy-db", default=str(DEFAULT_CHROMA_DB))
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--min-recall-at-5", type=float, default=0.8)
    args = parser.parse_args()

    fixture = json.loads(Path(args.fixture).read_text(encoding="utf-8"))
    report = evaluate_fixture(fixture, legacy_db_path=Path(args.legacy_db), limit=args.limit)
    print(json.dumps(report, indent=2))
    return 0 if report["metrics"]["recallAt5"] >= args.min_recall_at_5 else 1


if __name__ == "__main__":
    raise SystemExit(main())
