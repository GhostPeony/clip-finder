from backend.youtube_utils import (
    chunk_transcript_entries,
    classify_transcript_error,
    detect_url_type,
    fetch_transcript_chunks,
    get_transcript_chunks,
)


def test_detect_url_type_prefers_playlist_for_watch_playlist_urls():
    url_type, extracted = detect_url_type(
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLabc123"
    )

    assert url_type == "playlist"
    assert extracted == "PLabc123"


def test_detect_url_type_handles_shorts():
    url_type, extracted = detect_url_type("https://youtube.com/shorts/dQw4w9WgXcQ")

    assert url_type == "video"
    assert extracted == "dQw4w9WgXcQ"


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
                Snippet("first", 0, 20),
                Snippet("second", 20, 20),
                Snippet("third.", 40, 20),
                Snippet("fourth", 60, 10),
            ]

    monkeypatch.setattr("backend.youtube_utils.YouTubeTranscriptApi", FakeTranscriptApi)

    chunks = get_transcript_chunks("video123")

    assert chunks == [
        {"text": "first second third.", "start_seconds": 0, "end_seconds": 60},
        {"text": "third. fourth", "start_seconds": 40, "end_seconds": 70},
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
    assert chunks[1] == {
        "text": "four five",
        "start_seconds": 60,
        "end_seconds": 90,
    }
