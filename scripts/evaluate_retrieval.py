"""Evaluate embedding candidates on a tiny SearchTube-style retrieval set."""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from langchain_google_genai import GoogleGenerativeAIEmbeddings

from backend.config import get_embedding_dimensions, get_embedding_model


@dataclass(frozen=True)
class Candidate:
    model: str
    dimensions: int


def parse_candidates(raw_value: str | None) -> list[Candidate]:
    if not raw_value:
        return [Candidate(get_embedding_model(), get_embedding_dimensions())]

    candidates = []
    for item in raw_value.split(","):
        model, _, dims = item.partition(":")
        candidates.append(Candidate(model.strip(), int(dims or get_embedding_dimensions())))
    return candidates


def cosine(a: list[float], b: list[float]) -> float:
    numerator = sum(x * y for x, y in zip(a, b))
    denom_a = math.sqrt(sum(x * x for x in a))
    denom_b = math.sqrt(sum(y * y for y in b))
    if denom_a == 0 or denom_b == 0:
        return 0.0
    return numerator / (denom_a * denom_b)


def reciprocal_rank(ranked_ids: list[str], expected: list[str]) -> float:
    expected_set = set(expected)
    for index, doc_id in enumerate(ranked_ids, start=1):
        if doc_id in expected_set:
            return 1 / index
    return 0.0


def evaluate(candidate: Candidate, fixture: dict, api_key: str) -> dict:
    document_embedder = GoogleGenerativeAIEmbeddings(
        model=candidate.model,
        google_api_key=api_key,
        task_type="RETRIEVAL_DOCUMENT",
        output_dimensionality=candidate.dimensions,
    )
    query_embedder = GoogleGenerativeAIEmbeddings(
        model=candidate.model,
        google_api_key=api_key,
        task_type="RETRIEVAL_QUERY",
        output_dimensionality=candidate.dimensions,
    )

    documents = fixture["documents"]
    doc_texts = [f"{doc['title']}\n\n{doc['text']}" for doc in documents]
    doc_vectors = document_embedder.embed_documents(doc_texts)

    recall_hits = 0
    mrr_total = 0.0
    query_count = len(fixture["queries"])

    for item in fixture["queries"]:
        query_vector = query_embedder.embed_query(item["query"])
        scored = sorted(
            (
                (documents[index]["id"], cosine(query_vector, vector))
                for index, vector in enumerate(doc_vectors)
            ),
            key=lambda row: row[1],
            reverse=True,
        )
        ranked_ids = [doc_id for doc_id, _score in scored]
        if set(ranked_ids[:3]).intersection(item["expected"]):
            recall_hits += 1
        mrr_total += reciprocal_rank(ranked_ids, item["expected"])

    return {
        "model": candidate.model,
        "dimensions": candidate.dimensions,
        "recallAt3": recall_hits / query_count if query_count else 0,
        "mrr": mrr_total / query_count if query_count else 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixture",
        default=str(ROOT / "eval" / "fixtures" / "searchtube_retrieval.json"),
        help="Path to retrieval fixture JSON.",
    )
    parser.add_argument(
        "--candidates",
        default=os.getenv("EVAL_EMBEDDING_CANDIDATES"),
        help="Comma-separated model:dimensions values.",
    )
    args = parser.parse_args()

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY is required to run retrieval evals.")
        return 2

    fixture = json.loads(Path(args.fixture).read_text(encoding="utf-8"))
    results = [
        evaluate(candidate, fixture, api_key)
        for candidate in parse_candidates(args.candidates)
    ]
    print(json.dumps({"results": results}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
