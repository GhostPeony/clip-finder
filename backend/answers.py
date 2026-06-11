"""Cited answer generation over selected clips.

generate_answer() is failure-safe: any LLM error returns "" so search always
returns clips even when the answer step is unavailable.
"""

import os
from typing import Optional

from langchain_google_genai import ChatGoogleGenerativeAI

try:
    from .config import get_llm_model
except ImportError:
    from config import get_llm_model

MAX_CLIP_CHARS = 700

PROMPT_TEMPLATE = """You answer questions about video transcripts. Use ONLY the clips below.

Rules:
- Write 2-4 sentences, direct and concrete.
- After every claim, cite its supporting clip inline as [[clip_N]].
- Only cite clips that actually support the claim.
- If the clips do not answer the question, reply exactly: I couldn't find this in your indexed videos.

Question: {query}

Clips:
{clips}

Answer:"""


def _format_timestamp(seconds: int) -> str:
    return f"{seconds // 60}:{seconds % 60:02d}"


def _get_llm(api_key: Optional[str]) -> ChatGoogleGenerativeAI:
    key_to_use = api_key or os.getenv("GEMINI_API_KEY")
    if not key_to_use:
        raise ValueError("No API key available for answer generation")
    return ChatGoogleGenerativeAI(
        model=get_llm_model(),
        google_api_key=key_to_use,
        temperature=0.2,
        max_output_tokens=512,
    )


def generate_answer(query: str, clips: list[dict], api_key: Optional[str] = None) -> str:
    """Generate a short cited answer from selected clips. Returns "" on any failure."""
    if not clips:
        return ""

    clip_lines = []
    for clip in clips:
        content = " ".join(clip["content"].split())[:MAX_CLIP_CHARS]
        clip_lines.append(
            f'[{clip["id"]}] "{clip["title"]}" at {_format_timestamp(clip["startSeconds"])}: {content}'
        )

    prompt = PROMPT_TEMPLATE.format(query=query, clips="\n".join(clip_lines))

    try:
        llm = _get_llm(api_key)
        response = llm.invoke(prompt)
        return (response.content or "").strip()
    except Exception as exc:  # noqa: BLE001 — answer must never break search
        print(f"[ANSWERS] Generation failed, returning clips only: {exc}")
        return ""
