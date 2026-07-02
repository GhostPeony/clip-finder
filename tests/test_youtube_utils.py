from backend.youtube_utils import (
    chunk_transcript_entries,
    classify_transcript_error,
    detect_url_type,
    fetch_transcript_chunks,
    get_transcript_chunks,
)


def test_detect_url_type_handles_video_urls_with_timestamps():
    samples = [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=123s",
        "https://www.youtube.com/watch?t=1m2s&v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ?t=42",
        "https://m.youtube.com/watch?v=dQw4w9WgXcQ&start=90",
        "www.youtube.com/watch?v=dQw4w9WgXcQ&t=123",
    ]

    for sample in samples:
        assert detect_url_type(sample) == ("video", "dQw4w9WgXcQ")


def test_detect_url_type_prefers_video_for_watch_playlist_context_urls():
    url_type, extracted = detect_url_type(
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLabc123"
    )

    assert url_type == "video"
    assert extracted == "dQw4w9WgXcQ"


def test_detect_url_type_handles_explicit_playlist_urls():
    url_type, extracted = detect_url_type("https://www.youtube.com/playlist?list=PLabc123")

    assert url_type == "playlist"
    assert extracted == "PLabc123"


def test_detect_url_type_handles_path_video_urls_with_extra_context():
    samples = [
        "https://youtube.com/shorts/dQw4w9WgXcQ?si=abc123",
        "https://www.youtube.com/live/dQw4w9WgXcQ?feature=share&t=10",
        "https://www.youtube.com/embed/dQw4w9WgXcQ?start=30",
        "youtube.com/v/dQw4w9WgXcQ?version=3",
    ]

    for sample in samples:
        assert detect_url_type(sample) == ("video", "dQw4w9WgXcQ")


def test_detect_url_type_handles_channel_url_variants():
    samples = [
        (
            "https://www.youtube.com/@Some.Channel/videos",
            "https://www.youtube.com/@Some.Channel/videos",
        ),
        (
            "youtube.com/@SomeChannel/streams?view=0",
            "https://youtube.com/@SomeChannel/streams?view=0",
        ),
        ("@SomeChannel", "https://www.youtube.com/@SomeChannel"),
        (
            "https://www.youtube.com/channel/UC_x5XG1OV2P6uZZ5FSM9Ttw?sub_confirmation=1",
            "https://www.youtube.com/channel/UC_x5XG1OV2P6uZZ5FSM9Ttw?sub_confirmation=1",
        ),
        (
            "https://www.youtube.com/c/GoogleDevelopers",
            "https://www.youtube.com/c/GoogleDevelopers",
        ),
        (
            "https://www.youtube.com/user/GoogleDevelopers",
            "https://www.youtube.com/user/GoogleDevelopers",
        ),
    ]

    for sample, expected in samples:
        assert detect_url_type(sample) == ("channel", expected)


def test_channel_detection_returns_unknown_for_non_youtube_urls():
    assert detect_url_type("https://example.com/watch?v=dQw4w9WgXcQ") == ("unknown", None)


def test_get_transcript_chunks_adds_overlap_after_closed_chunk(monkeypatch):
    class Snippet:
        def __init__(self, text, start, duration):
            self.text = text
            self.start = start
            self.duration = duration

    class FakeTranscriptApi:
        def fetch(self, video_id):
            assert video_id == "video123"
            return [
                Snippet("the quick brown fox", 0, 20),
                Snippet("jumps over the lazy dog", 20, 20),
                Snippet("and stops right there.", 40, 20),
                Snippet("a short tail follows here now", 60, 10),
            ]

    monkeypatch.setattr("backend.youtube_utils.YouTubeTranscriptApi", FakeTranscriptApi)

    chunks = get_transcript_chunks("video123")

    assert chunks == [
        {
            "text": "the quick brown fox jumps over the lazy dog and stops right there.",
            "start_seconds": 0,
            "end_seconds": 60,
        },
        {
            "text": "and stops right there. a short tail follows here now",
            "start_seconds": 40,
            "end_seconds": 70,
        },
    ]


def test_fetch_transcript_chunks_reports_empty_transcript(monkeypatch):
    class FakeTranscriptApi:
        def fetch(self, video_id):
            return []

    monkeypatch.setattr("backend.youtube_utils.YouTubeTranscriptApi", FakeTranscriptApi)

    result = fetch_transcript_chunks("video123")

    assert result.chunks == []
    assert result.skip_reason == "empty_transcript"


def test_transcript_error_classification_uses_stable_reasons():
    class TranscriptsDisabled(Exception):
        pass

    class TooManyRequests(Exception):
        pass

    assert classify_transcript_error(TranscriptsDisabled("disabled")) == "captions_disabled"
    assert classify_transcript_error(TooManyRequests("too many requests")) == "rate_limited"


def test_chunk_transcript_entries_waits_for_sentence_boundary():
    chunks = chunk_transcript_entries(
        [
            {"text": "first idea", "start": 0, "duration": 20},
            {"text": "keeps going", "start": 20, "duration": 20},
            {"text": "still no stop", "start": 40, "duration": 20},
            {"text": "now it ends.", "start": 60, "duration": 5},
        ]
    )

    assert chunks[0] == {
        "text": "first idea keeps going still no stop now it ends.",
        "start_seconds": 0,
        "end_seconds": 65,
    }


def test_chunk_transcript_entries_caps_long_chunks_without_sentence_boundary():
    chunks = chunk_transcript_entries(
        [
            {"text": "one", "start": 0, "duration": 20},
            {"text": "two", "start": 20, "duration": 20},
            {"text": "three", "start": 40, "duration": 20},
            {"text": "four", "start": 60, "duration": 20},
            {"text": "five", "start": 80, "duration": 10},
        ]
    )

    assert chunks[0] == {
        "text": "one two three four",
        "start_seconds": 0,
        "end_seconds": 80,
    }
    # The tiny trailing chunk is not merged back: the merge would stretch the
    # previous chunk past CHUNK_MAX_SECONDS.
    assert chunks[1] == {
        "text": "four five",
        "start_seconds": 60,
        "end_seconds": 90,
    }


def test_chunk_transcript_entries_strips_bracketed_caption_noise():
    chunks = chunk_transcript_entries(
        [
            {"text": "[Music]", "start": 0, "duration": 5},
            {"text": "[Applause] welcome back to the show.", "start": 5, "duration": 5},
            {"text": "[música]", "start": 10, "duration": 5},
        ]
    )

    assert chunks == [
        {"text": "welcome back to the show.", "start_seconds": 5, "end_seconds": 10},
    ]


def test_chunk_transcript_entries_closes_long_chunk_at_speech_gap():
    chunks = chunk_transcript_entries(
        [
            {
                "text": "auto captions often have no punctuation at all",
                "start": 0,
                "duration": 30,
            },
            {
                "text": "so the boundary check alone never fires",
                "start": 30,
                "duration": 30,
            },
            {
                "text": "a new topic starts after the pause",
                "start": 64,
                "duration": 10,
            },
        ]
    )

    assert chunks[0] == {
        "text": (
            "auto captions often have no punctuation at all so the boundary check alone never fires"
        ),
        "start_seconds": 0,
        "end_seconds": 60,
    }
    assert chunks[1] == {
        "text": "so the boundary check alone never fires a new topic starts after the pause",
        "start_seconds": 30,
        "end_seconds": 74,
    }


def test_chunk_transcript_entries_merges_tiny_trailing_chunk():
    chunks = chunk_transcript_entries(
        [
            {"text": "one two three four five six seven eight.", "start": 0, "duration": 60},
            {"text": "tail words", "start": 60, "duration": 5},
        ]
    )

    assert chunks == [
        {
            "text": "one two three four five six seven eight. tail words",
            "start_seconds": 0,
            "end_seconds": 65,
        },
    ]


def test_chunk_transcript_entries_holds_short_chunks_past_sentence_boundary():
    chunks = chunk_transcript_entries(
        [
            {"text": "yes.", "start": 0, "duration": 61},
            {
                "text": "the answer deserves more context than a single word reply.",
                "start": 61,
                "duration": 10,
            },
        ]
    )

    assert len(chunks) == 1
    assert chunks[0] == {
        "text": "yes. the answer deserves more context than a single word reply.",
        "start_seconds": 0,
        "end_seconds": 71,
    }
