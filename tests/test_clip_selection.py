from backend.clip_selection import select_clips


def make_clip(video_id: str, start: int, end: int, similarity: float | None = None) -> dict:
    clip = {
        "videoId": video_id,
        "title": f"video {video_id}",
        "channelName": "chan",
        "startSeconds": start,
        "endSeconds": end,
        "content": "text",
        "thumbnailUrl": "",
    }
    if similarity is not None:
        clip["similarity"] = similarity
    return clip


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


def test_similarity_floor_drops_low_scores_but_keeps_scoreless_rows():
    candidates = [
        make_clip("a", 300, 360, similarity=0.9),
        make_clip("b", 500, 560, similarity=0.2),
        make_clip("c", 700, 760),  # keyword row without a similarity score
    ]
    result = select_clips(candidates, limit=5, similarity_floor=0.5)
    assert [c["videoId"] for c in result] == ["a", "c"]


def test_similarity_floor_defaults_off():
    candidates = [
        make_clip("a", 300, 360, similarity=0.05),
        make_clip("b", 500, 560, similarity=-0.4),
    ]
    result = select_clips(candidates, limit=5)
    assert [c["videoId"] for c in result] == ["a", "b"]


def test_similarity_floor_reads_env_default(monkeypatch):
    monkeypatch.setenv("RETRIEVAL_SIMILARITY_FLOOR", "0.5")
    candidates = [
        make_clip("a", 300, 360, similarity=0.9),
        make_clip("b", 500, 560, similarity=0.2),
    ]
    result = select_clips(candidates, limit=5)
    assert [c["videoId"] for c in result] == ["a"]


def test_per_video_cap_diversifies_across_videos():
    candidates = [
        make_clip("a", 300, 360),
        make_clip("a", 500, 560),
        make_clip("a", 700, 760),
        make_clip("a", 900, 960),
        make_clip("b", 300, 360),
    ]
    result = select_clips(candidates, limit=4, per_video_cap=3)
    assert [c["videoId"] for c in result] == ["a", "a", "a", "b"]


def test_per_video_cap_is_soft_and_backfills_when_under_limit():
    # Only one video available: the cap must never shrink the result set.
    candidates = [
        make_clip("a", 300, 360),
        make_clip("a", 500, 560),
        make_clip("a", 700, 760),
        make_clip("a", 900, 960),
        make_clip("a", 1100, 1160),
    ]
    result = select_clips(candidates, limit=5, per_video_cap=3)
    assert len(result) == 5
    assert [c["startSeconds"] for c in result] == [300, 500, 700, 900, 1100]


def test_per_video_cap_zero_disables_cap_for_video_scoped_search():
    candidates = [make_clip("a", 300 + i * 200, 360 + i * 200) for i in range(6)]
    result = select_clips(candidates, limit=6, per_video_cap=0)
    assert len(result) == 6


def test_per_video_cap_reads_env_default(monkeypatch):
    monkeypatch.setenv("RETRIEVAL_PER_VIDEO_CLIP_CAP", "1")
    candidates = [
        make_clip("a", 300, 360),
        make_clip("a", 500, 560),
        make_clip("b", 300, 360),
        make_clip("c", 300, 360),
    ]
    result = select_clips(candidates, limit=3)
    assert [c["videoId"] for c in result] == ["a", "b", "c"]
