"""Shared clip ranking: soft intro filter + near-duplicate suppression.

Both storage modes build raw candidate clips (similarity-ordered) and call
select_clips() to pick the final result set. Post-intro clips are preferred,
but intro clips backfill when there are not enough later matches — a short
video must never produce zero results.
"""

INTRO_SECONDS = 120
NEARBY_CHUNK_SECONDS = 90


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


def select_clips(
    candidates: list[dict], limit: int, intro_seconds: int = INTRO_SECONDS
) -> list[dict]:
    """Pick up to `limit` clips from similarity-ordered candidates.

    Two passes preserve similarity order within each tier: post-intro clips
    first, then intro clips as backfill. Near-duplicates (same video, within
    NEARBY_CHUNK_SECONDS or overlapping) are suppressed across both passes.
    Returns copies with sequential clip ids.
    """
    chosen: list[dict] = []

    def take(pool: list[dict]) -> None:
        for clip in pool:
            if len(chosen) >= limit:
                return
            if _is_near_existing(clip, chosen):
                continue
            chosen.append(clip)

    take([c for c in candidates if c["startSeconds"] >= intro_seconds])
    take([c for c in candidates if c["startSeconds"] < intro_seconds])

    return [{**clip, "id": f"clip_{i}"} for i, clip in enumerate(chosen)]
