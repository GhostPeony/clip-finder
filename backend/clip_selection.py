"""Shared clip ranking: soft intro filter + near-duplicate suppression.

Supabase pgvector search builds raw candidate clips in similarity order and calls
select_clips() to pick the final result set. Post-intro clips are preferred,
but intro clips backfill when there are not enough later matches — a short
video must never produce zero results.

Two optional guards keep result sets useful without hurting recall:
- A similarity floor (env RETRIEVAL_SIMILARITY_FLOOR, default 0.0 = off) drops
  only candidates whose numeric similarity falls below it. Score-less keyword
  rows are never dropped. Floor tuning is deferred to a hosted A/B.
- A soft per-video cap (env RETRIEVAL_PER_VIDEO_CLIP_CAP, default 3) skips
  over-represented videos in the main passes, then backfills ignoring the cap
  when the result set is still under the limit — a recall regression is
  structurally impossible. Callers disable the cap (0) for video-scoped
  searches where one video is the whole point.
"""

import os

INTRO_SECONDS = 120
NEARBY_CHUNK_SECONDS = 90
DEFAULT_SIMILARITY_FLOOR = 0.0
DEFAULT_PER_VIDEO_CLIP_CAP = 3


def _env_float(name: str, default: float) -> float:
    raw_value = os.getenv(name, "").strip()
    if not raw_value:
        return default
    try:
        return float(raw_value)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    raw_value = os.getenv(name, "").strip()
    if not raw_value:
        return default
    try:
        return int(raw_value)
    except ValueError:
        return default


def _resolve_similarity_floor(similarity_floor: float | None) -> float:
    if similarity_floor is not None:
        return float(similarity_floor)
    return _env_float("RETRIEVAL_SIMILARITY_FLOOR", DEFAULT_SIMILARITY_FLOOR)


def _resolve_per_video_cap(per_video_cap: int | None) -> int:
    if per_video_cap is not None:
        return int(per_video_cap)
    return _env_int("RETRIEVAL_PER_VIDEO_CLIP_CAP", DEFAULT_PER_VIDEO_CLIP_CAP)


def _below_similarity_floor(clip: dict, floor: float) -> bool:
    similarity = clip.get("similarity")
    if isinstance(similarity, bool) or not isinstance(similarity, (int, float)):
        return False
    return similarity < floor


def _is_near_existing(clip: dict, chosen: list[dict]) -> bool:
    for existing in chosen:
        if existing["videoId"] != clip["videoId"]:
            continue
        overlaps = (
            clip["startSeconds"] < existing["endSeconds"]
            and clip["endSeconds"] > existing["startSeconds"]
        )
        nearby = abs(clip["startSeconds"] - existing["startSeconds"]) < NEARBY_CHUNK_SECONDS
        if overlaps or nearby:
            return True
    return False


def _video_clip_count(clip: dict, chosen: list[dict]) -> int:
    return sum(1 for existing in chosen if existing["videoId"] == clip["videoId"])


def select_clips(
    candidates: list[dict],
    limit: int,
    intro_seconds: int = INTRO_SECONDS,
    *,
    similarity_floor: float | None = None,
    per_video_cap: int | None = None,
) -> list[dict]:
    """Pick up to `limit` clips from similarity-ordered candidates.

    Two passes preserve similarity order within each tier: post-intro clips
    first, then intro clips as backfill. Near-duplicates (same video, within
    NEARBY_CHUNK_SECONDS or overlapping) are suppressed across both passes.
    The per-video cap is soft: a final backfill ignores it when the result
    set is still under the limit. Returns copies with sequential clip ids.
    """
    floor = _resolve_similarity_floor(similarity_floor)
    cap = _resolve_per_video_cap(per_video_cap)

    pool = candidates
    if floor > 0:
        pool = [clip for clip in candidates if not _below_similarity_floor(clip, floor)]

    chosen: list[dict] = []

    def take(tier: list[dict], enforce_cap: bool) -> None:
        for clip in tier:
            if len(chosen) >= limit:
                return
            if _is_near_existing(clip, chosen):
                continue
            if enforce_cap and cap > 0 and _video_clip_count(clip, chosen) >= cap:
                continue
            chosen.append(clip)

    post_intro = [c for c in pool if c["startSeconds"] >= intro_seconds]
    intro = [c for c in pool if c["startSeconds"] < intro_seconds]

    take(post_intro, True)
    take(intro, True)
    if len(chosen) < limit and cap > 0:
        # Soft cap: backfill over-capped videos rather than returning fewer clips.
        take(post_intro, False)
        take(intro, False)

    return [{**clip, "id": f"clip_{i}"} for i, clip in enumerate(chosen)]
