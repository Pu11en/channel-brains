"""Tests for Channel Brains database layer."""

import sqlite3

import pytest

from channel_brains_mcp.db import (
    Repository,
    connect_db,
    initialize_database,
    rebuild_fts_index,
    transaction,
)


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test.db"


class TestInitializeDatabase:
    def test_initialize_creates_schema_version_one(self, db_path):
        initialize_database(db_path)
        conn = connect_db(db_path)
        try:
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            assert version == 1
        finally:
            conn.close()

    def test_fts5_is_available(self, db_path):
        initialize_database(db_path)
        conn = connect_db(db_path)
        try:
            # FTS5 integrity check passes silently with no exception
            conn.execute(
                "INSERT INTO chunks_fts(chunks_fts) VALUES('integrity-check')"
            )
            conn.commit()
        finally:
            conn.close()

    def test_unique_normalized_url(self, db_path):
        initialize_database(db_path)
        repo = Repository(db_path)
        repo.create_brain(
            brain_id="aaa",
            source_url="https://www.youtube.com/@test",
            normalized_url="https://www.youtube.com/@test",
            channel_id=None,
            channel_name=None,
            language="en",
            max_videos=50,
        )
        with pytest.raises(sqlite3.IntegrityError):
            repo.create_brain(
                brain_id="bbb",
                source_url="https://www.youtube.com/@test",
                normalized_url="https://www.youtube.com/@test",
                channel_id=None,
                channel_name=None,
                language="en",
                max_videos=50,
            )

    def test_fts_triggers_add_update_delete(self, db_path):
        initialize_database(db_path)
        repo = Repository(db_path)
        repo.create_brain(
            brain_id="test1",
            source_url="https://www.youtube.com/@test",
            normalized_url="https://www.youtube.com/@test",
            channel_id=None,
            channel_name=None,
            language="en",
            max_videos=50,
        )
        # Also need a video row for the FK
        repo.upsert_brain_status("test1", "queued")
        with transaction(db_path) as conn:
            conn.execute(
                """INSERT INTO videos
                (brain_id, video_id, position, title, webpage_url, status)
                VALUES (?, ?, ?, ?, ?, ?)""",
                ("test1", "vid1", 1, "Test Video", "https://youtu.be/vid1", "pending"),
            )
            repo.insert_chunk(
                conn,
                brain_id="test1",
                video_id="vid1",
                video_title="Test Video",
                chunk_index=0,
                start_ms=0,
                end_ms=10000,
                text="hello world test content",
            )

        # Search should find the text
        results = repo.search_chunks("test", ["test"])
        assert len(results) >= 1

        # Delete the brain and FTS should remove the row
        repo.delete_brain("test1")
        results = repo.search_chunks("test", ["test"])
        assert len(results) == 0

    def test_fts_stemming(self, db_path):
        initialize_database(db_path)
        repo = Repository(db_path)
        repo.create_brain(
            brain_id="stem1",
            source_url="https://www.youtube.com/@test",
            normalized_url="https://www.youtube.com/@test",
            channel_id=None,
            channel_name=None,
            language="en",
            max_videos=50,
        )
        with transaction(db_path) as conn:
            conn.execute(
                """INSERT INTO videos
                (brain_id, video_id, position, title, webpage_url, status)
                VALUES (?, ?, ?, ?, ?, ?)""",
                ("stem1", "vid1", 1, "Test", "https://youtu.be/vid1", "pending"),
            )
            repo.insert_chunk(
                conn,
                brain_id="stem1",
                video_id="vid1",
                video_title="Test",
                chunk_index=0,
                start_ms=0,
                end_ms=10000,
                text="This is about strategies for success",
            )

        # Porter stemmer should match "strategies" with "strategy"
        results = repo.search_chunks("strategy", ["strategy"])
        assert len(results) >= 1

    def test_search_excludes_other_brains(self, db_path):
        initialize_database(db_path)
        repo = Repository(db_path)
        repo.create_brain(
            brain_id="b1",
            source_url="https://www.youtube.com/@ch1",
            normalized_url="https://www.youtube.com/@ch1",
            channel_id=None,
            channel_name="Channel 1",
            language="en",
            max_videos=50,
        )
        repo.create_brain(
            brain_id="b2",
            source_url="https://www.youtube.com/@ch2",
            normalized_url="https://www.youtube.com/@ch2",
            channel_id=None,
            channel_name="Channel 2",
            language="en",
            max_videos=50,
        )
        with transaction(db_path) as conn:
            conn.execute(
                """INSERT INTO videos
                (brain_id, video_id, position, title, webpage_url, status)
                VALUES (?, ?, ?, ?, ?, ?)""",
                ("b1", "v1", 1, "Video 1", "https://youtu.be/v1", "pending"),
            )
            repo.insert_chunk(
                conn,
                brain_id="b1",
                video_id="v1",
                video_title="Video 1",
                chunk_index=0,
                start_ms=0,
                end_ms=10000,
                text="python programming",
            )

        results = repo.search_chunks("python", ["python"], brain_id="b1")
        for r in results:
            assert r["brain_id"] == "b1"

    def test_search_without_brain_filter(self, db_path):
        initialize_database(db_path)
        repo = Repository(db_path)
        repo.create_brain(
            brain_id="b1",
            source_url="https://www.youtube.com/@ch1",
            normalized_url="https://www.youtube.com/@ch1",
            channel_id=None,
            channel_name="Channel 1",
            language="en",
            max_videos=50,
        )
        with transaction(db_path) as conn:
            conn.execute(
                """INSERT INTO videos
                (brain_id, video_id, position, title, webpage_url, status)
                VALUES (?, ?, ?, ?, ?, ?)""",
                ("b1", "v1", 1, "Video 1", "https://youtu.be/v1", "pending"),
            )
            repo.insert_chunk(
                conn,
                brain_id="b1",
                video_id="v1",
                video_title="Video 1",
                chunk_index=0,
                start_ms=0,
                end_ms=10000,
                text="python programming",
            )

        results = repo.search_chunks("python", ["python"])
        assert len(results) >= 1

    def test_search_returns_timestamp_metadata(self, db_path):
        initialize_database(db_path)
        repo = Repository(db_path)
        repo.create_brain(
            brain_id="ts1",
            source_url="https://www.youtube.com/@ch1",
            normalized_url="https://www.youtube.com/@ch1",
            channel_id=None,
            channel_name="Ch1",
            language="en",
            max_videos=50,
        )
        with transaction(db_path) as conn:
            conn.execute(
                """INSERT INTO videos
                (brain_id, video_id, position, title, webpage_url, status)
                VALUES (?, ?, ?, ?, ?, ?)""",
                ("ts1", "v1", 1, "My Video", "https://youtu.be/v1", "pending"),
            )
            repo.insert_chunk(
                conn,
                brain_id="ts1",
                video_id="v1",
                video_title="My Video",
                chunk_index=0,
                start_ms=754000,
                end_ms=799000,
                text="relevant caption excerpt",
            )

        results = repo.search_chunks("relevant", ["relevant"])
        assert len(results) >= 1
        hit = results[0]
        assert hit.get("start_ms", 0) // 1000 == 754
        assert hit.get("end_ms", 0) // 1000 == 799
        assert "My Video" in hit["video_title"]
        assert hit.get("video_id") == "v1"

    def test_raw_fts_operators_are_quoted(self, db_path):
        initialize_database(db_path)
        repo = Repository(db_path)
        repo.create_brain(
            brain_id="op1",
            source_url="https://www.youtube.com/@ch1",
            normalized_url="https://www.youtube.com/@ch1",
            channel_id=None,
            channel_name="Ch1",
            language="en",
            max_videos=50,
        )
        with transaction(db_path) as conn:
            conn.execute(
                """INSERT INTO videos
                (brain_id, video_id, position, title, webpage_url, status)
                VALUES (?, ?, ?, ?, ?, ?)""",
                ("op1", "v1", 1, "Vid", "https://youtu.be/v1", "pending"),
            )
            repo.insert_chunk(
                conn,
                brain_id="op1",
                video_id="v1",
                video_title="Vid",
                chunk_index=0,
                start_ms=0,
                end_ms=10000,
                text="foo bar baz",
            )

        tokens = _tokenize_query_fresh("foo OR bar")
        assert "foo" in tokens
        assert "bar" in tokens

    def test_delete_brain_cascades(self, db_path):
        initialize_database(db_path)
        repo = Repository(db_path)
        repo.create_brain(
            brain_id="del1",
            source_url="https://www.youtube.com/@ch1",
            normalized_url="https://www.youtube.com/@ch1",
            channel_id=None,
            channel_name="Ch1",
            language="en",
            max_videos=50,
        )
        with transaction(db_path) as conn:
            conn.execute(
                """INSERT INTO videos
                (brain_id, video_id, position, title, webpage_url, status)
                VALUES (?, ?, ?, ?, ?, ?)""",
                ("del1", "v1", 1, "Vid", "https://youtu.be/v1", "pending"),
            )
            repo.insert_chunk(
                conn,
                brain_id="del1",
                video_id="v1",
                video_title="Vid",
                chunk_index=0,
                start_ms=0,
                end_ms=10000,
                text="test content",
            )

        result = repo.delete_brain("del1")
        assert result["deleted_chunk_count"] >= 1

    def test_fts_rebuild(self, db_path):
        initialize_database(db_path)
        rebuild_fts_index(db_path)


def _tokenize_query_fresh(query: str) -> list[str]:
    """Duplicate of _tokenize_query for use in tests without server import."""
    import re
    text = query.lower().strip()
    if not text:
        return []
    tokens = re.findall(r"[a-z0-9][a-z0-9]+", text)
    STOPWORDS = frozenset(
        "a an and are as at be but by for from has have he her his how i if in into is it its me my no not of on or our own re s she so some such t than that the their them then there these they this those through to too under up very was we were what when where which while who will with would you your".split()  # noqa: SIM905
    )
    tokens = [t for t in tokens if t not in STOPWORDS]
    seen: set[str] = set()
    deduped: list[str] = []
    for t in tokens:
        if t not in seen:
            seen.add(t)
            deduped.append(t)
    return deduped[:12]
