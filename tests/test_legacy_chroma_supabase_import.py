import sqlite3
from pathlib import Path

from scripts.legacy_chroma_supabase_import import (
    build_manifest,
    load_legacy_chunks,
    parse_video_ids,
)


def _write_metadata(db_path: Path, rows: list[tuple]):
    con = sqlite3.connect(db_path)
    try:
        con.execute(
            """
            CREATE TABLE embedding_metadata (
                id INTEGER,
                key TEXT,
                string_value TEXT,
                int_value INTEGER
            )
            """
        )
        con.executemany(
            "INSERT INTO embedding_metadata (id, key, string_value, int_value) VALUES (?, ?, ?, ?)",
            rows,
        )
        con.commit()
    finally:
        con.close()


def test_legacy_chroma_manifest_groups_chunks_and_estimates_cost(tmp_path):
    db_path = tmp_path / "chroma.sqlite3"
    _write_metadata(
        db_path,
        [
            (1, "video_id", "video-a", None),
            (1, "title", "Sourdough Lesson", None),
            (1, "channel_name", "Kitchen Lessons", None),
            (1, "chroma:document", "Feed the starter before mixing.", None),
            (1, "start_seconds", None, 0),
            (1, "end_seconds", None, 30),
            (2, "video_id", "video-a", None),
            (2, "title", "Sourdough Lesson", None),
            (2, "channel_name", "Kitchen Lessons", None),
            (2, "chroma:document", "Keep the dough warm until it rises.", None),
            (2, "start_seconds", None, 30),
            (2, "end_seconds", None, 60),
            (3, "video_id", "video-b", None),
            (3, "title", "Faucet Repair", None),
            (3, "channel_name", "Home Fix", None),
            (3, "chroma:document", "Replace the cartridge after turning water off.", None),
            (3, "start_seconds", None, 10),
            (3, "end_seconds", None, 40),
            (4, "video_id", "skip-empty-doc", None),
            (4, "title", "Skipped", None),
        ],
    )

    chunks = load_legacy_chunks(db_path)
    manifest = build_manifest(db_path, chunks, embed_batch_size=2)

    assert len(chunks) == 3
    assert manifest["mode"] == "dry_run"
    assert manifest["videoCount"] == 2
    assert manifest["chunkCount"] == 3
    assert manifest["transcriptSeconds"] == 100
    assert manifest["estimatedEmbeddingBatches"] == 2
    assert manifest["digestLlmCalls"] == 0
    assert manifest["videos"][0]["youtube_video_id"] == "video-a"
    assert manifest["videos"][0]["chunk_count"] == 2


def test_legacy_chroma_manifest_can_select_video_ids(tmp_path):
    db_path = tmp_path / "chroma.sqlite3"
    _write_metadata(
        db_path,
        [
            (1, "video_id", "video-a", None),
            (1, "title", "A", None),
            (1, "chroma:document", "alpha", None),
            (1, "end_seconds", None, 10),
            (2, "video_id", "video-b", None),
            (2, "title", "B", None),
            (2, "chroma:document", "beta", None),
            (2, "end_seconds", None, 20),
        ],
    )

    chunks = load_legacy_chunks(db_path)
    selected = parse_video_ids(["video-b, video-c"])
    manifest = build_manifest(db_path, chunks, selected_video_ids=selected)

    assert selected == {"video-b", "video-c"}
    assert manifest["videoCount"] == 1
    assert manifest["videos"][0]["youtube_video_id"] == "video-b"
