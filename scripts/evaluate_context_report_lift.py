"""Evaluate Memexai report/source-object retrieval against raw transcript scanning.

This offline eval measures agent navigability, not prose quality. It compares two
ways an agent could answer questions about the same video:

1. transcript_baseline: search raw timestamp chunks and read until enough evidence appears.
2. memexai_context: search structured source concepts and report sections with source refs.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE = ROOT / "eval" / "fixtures" / "video_context_report_lift.json"

STOPWORDS = {
    "about",
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
class EvalDoc:
    id: str
    corpus: str
    doc_type: str
    title: str
    text: str
    evidence: tuple[str, ...]
    source_refs: tuple[dict, ...]

    @property
    def char_count(self) -> int:
        return len(" ".join(self.text.split()))


def tokenize(value: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-zA-Z0-9+#.-]+", value.lower())
        if len(token) >= 3 and token not in STOPWORDS
    ]


def score_document(query: str, doc: EvalDoc) -> float:
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
    if all(term in haystack for term in terms):
        score += 8
    matched = sum(1 for term in terms if term in haystack)
    score += matched / len(terms)
    return round(score, 3)


def build_transcript_docs(fixture: dict) -> list[EvalDoc]:
    return [
        EvalDoc(
            id=row["id"],
            corpus="transcript_baseline",
            doc_type="transcript_chunk",
            title=fixture["video"]["title"],
            text=row["text"],
            evidence=tuple(row.get("evidence", [])),
            source_refs=(
                {
                    "start_seconds": row.get("start_seconds"),
                    "end_seconds": row.get("end_seconds"),
                },
            ),
        )
        for row in fixture["rawTranscriptChunks"]
    ]


def build_memexai_docs(fixture: dict) -> list[EvalDoc]:
    context = fixture["memexaiContext"]
    docs: list[EvalDoc] = []
    for row in context.get("sourceConcepts", []):
        docs.append(
            EvalDoc(
                id=row["id"],
                corpus="memexai_context",
                doc_type="source_concept",
                title=row["name"],
                text=f"{row.get('concept_type', '')} {row.get('summary', '')}",
                evidence=tuple(row.get("evidence", [])),
                source_refs=tuple(row.get("source_refs", [])),
            )
        )
    for row in context.get("reportSections", []):
        docs.append(
            EvalDoc(
                id=row["id"],
                corpus="memexai_context",
                doc_type="report_section",
                title=row["heading"],
                text=row["text"],
                evidence=tuple(row.get("evidence", [])),
                source_refs=tuple(row.get("source_refs", [])),
            )
        )
    return docs


def rank_docs(query: str, docs: list[EvalDoc], limit: int) -> list[dict]:
    ranked = []
    for doc in docs:
        score = score_document(query, doc)
        if score <= 0:
            continue
        ranked.append(
            {
                "id": doc.id,
                "corpus": doc.corpus,
                "docType": doc.doc_type,
                "title": doc.title,
                "score": score,
                "charCount": doc.char_count,
                "evidence": list(doc.evidence),
                "sourceRefs": list(doc.source_refs),
                "snippet": " ".join(doc.text.split())[:260],
            }
        )
    ranked.sort(key=lambda row: row["score"], reverse=True)
    return ranked[:limit]


def chars_to_cover(ranked_docs: list[dict], expected_evidence: list[str]) -> int | None:
    expected = set(expected_evidence)
    covered: set[str] = set()
    chars = 0
    for row in ranked_docs:
        chars += int(row["charCount"])
        covered.update(row.get("evidence", []))
        if expected.issubset(covered):
            return chars
    return None


def coverage_at_k(ranked_docs: list[dict], expected_evidence: list[str], k: int) -> bool:
    expected = set(expected_evidence)
    covered: set[str] = set()
    for row in ranked_docs[:k]:
        covered.update(row.get("evidence", []))
    return expected.issubset(covered)


def has_timestamped_evidence(ranked_docs: list[dict], k: int) -> bool:
    for row in ranked_docs[:k]:
        refs = row.get("sourceRefs") or []
        if any(ref.get("start_seconds") is not None for ref in refs if isinstance(ref, dict)):
            return True
    return False


def evaluate_fixture(fixture: dict, limit: int = 5) -> dict:
    transcript_docs = build_transcript_docs(fixture)
    memexai_docs = build_memexai_docs(fixture)
    rows = []

    transcript_coverage_hits = 0
    memexai_coverage_hits = 0
    transcript_timestamp_hits = 0
    memexai_timestamp_hits = 0
    transcript_chars: list[int] = []
    memexai_chars: list[int] = []

    for query in fixture["queries"]:
        expected = query["expectedEvidence"]
        transcript_ranked = rank_docs(query["query"], transcript_docs, limit)
        memexai_ranked = rank_docs(query["query"], memexai_docs, limit)
        transcript_hit = coverage_at_k(transcript_ranked, expected, 3)
        memexai_hit = coverage_at_k(memexai_ranked, expected, 3)
        transcript_ts = has_timestamped_evidence(transcript_ranked, 3)
        memexai_ts = has_timestamped_evidence(memexai_ranked, 3)
        transcript_char_count = chars_to_cover(transcript_ranked, expected)
        memexai_char_count = chars_to_cover(memexai_ranked, expected)

        transcript_coverage_hits += int(transcript_hit)
        memexai_coverage_hits += int(memexai_hit)
        transcript_timestamp_hits += int(transcript_ts)
        memexai_timestamp_hits += int(memexai_ts)
        if transcript_char_count is not None:
            transcript_chars.append(transcript_char_count)
        if memexai_char_count is not None:
            memexai_chars.append(memexai_char_count)

        rows.append(
            {
                "id": query["id"],
                "query": query["query"],
                "expectedEvidence": expected,
                "transcript": {
                    "coverageAt3": transcript_hit,
                    "charsToCover": transcript_char_count,
                    "topDocs": transcript_ranked[:3],
                },
                "memexaiContext": {
                    "coverageAt3": memexai_hit,
                    "charsToCover": memexai_char_count,
                    "topDocs": memexai_ranked[:3],
                },
            }
        )

    query_count = len(fixture["queries"])
    avg_transcript_chars = _average(transcript_chars)
    avg_memexai_chars = _average(memexai_chars)
    char_reduction = (
        round(1 - (avg_memexai_chars / avg_transcript_chars), 3)
        if avg_transcript_chars and avg_memexai_chars
        else None
    )
    metrics = {
        "transcriptCoverageAt3": round(transcript_coverage_hits / query_count, 3),
        "memexaiCoverageAt3": round(memexai_coverage_hits / query_count, 3),
        "transcriptTimestampRefRate": round(transcript_timestamp_hits / query_count, 3),
        "memexaiTimestampRefRate": round(memexai_timestamp_hits / query_count, 3),
        "avgTranscriptCharsToCover": avg_transcript_chars,
        "avgMemexaiCharsToCover": avg_memexai_chars,
        "charReduction": char_reduction,
    }
    passed = (
        metrics["memexaiCoverageAt3"] >= 1.0
        and metrics["memexaiTimestampRefRate"] >= 1.0
        and (metrics["charReduction"] or 0) >= 0.25
    )
    return {
        "fixture": fixture["name"],
        "passed": passed,
        "metrics": metrics,
        "results": rows,
    }


def _average(values: list[int]) -> int | None:
    if not values:
        return None
    return round(sum(values) / len(values))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", default=str(DEFAULT_FIXTURE))
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()

    fixture = json.loads(Path(args.fixture).read_text(encoding="utf-8"))
    report = evaluate_fixture(fixture, limit=args.limit)
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
