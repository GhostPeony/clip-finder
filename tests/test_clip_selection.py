from backend.clip_selection import select_clips


def make_clip(video_id: str, start: int, end: int) -> dict:
    return {
        "videoId": video_id,
        "title": f"video {video_id}",
        "channelName": "chan",
        "startSeconds": start,
        "endSeconds": end,
        "content": "text",
        "thumbnailUrl": "",
    }


def test_prefers_post_intro_clips():
    candidates = [make_clip("a", 30, 90), make_clip("a", 300, 360), make_clip("b", 500, 560)]
    result = select_clips(candidates, limit=2)
    assert [c["startSeconds"] for c in result] == [300, 500]


def test_backfills_intro_clips_when_short():
    candidates = [make_clip("a", 30, 90), make_clip("a", 300, 360)]
    result = select_clips(candidates, limit=3)
    # post-intro first, then intro backfill — never return fewer than available
    assert [c["startSeconds"] for c in result] == [300, 30]


def test_all_intro_still_returns_results():
    # both clips inside the intro window, far enough apart to not be duplicates
    candidates = [make_clip("a", 0, 60), make_clip("a", 100, 160)]
    result = select_clips(candidates, limit=5)
    assert len(result) == 2


def test_suppresses_near_duplicates():
    # within 90s on the same video -> duplicate
    candidates = [make_clip("a", 300, 360), make_clip("a", 350, 410), make_clip("a", 600, 660)]
    result = select_clips(candidates, limit=5)
    assert [c["startSeconds"] for c in result] == [300, 600]


def test_reassigns_sequential_ids():
    candidates = [make_clip("a", 30, 90), make_clip("a", 300, 360)]
    result = select_clips(candidates, limit=2)
    assert [c["id"] for c in result] == ["clip_0", "clip_1"]
