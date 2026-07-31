"""SQLite FTS5 storage for persistent Channel Brains caption indexes."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS brains (
    brain_id TEXT PRIMARY KEY,
    source_url TEXT NOT NULL,
    normalized_url TEXT NOT NULL UNIQUE,
    channel_id TEXT,
    channel_name TEXT,
    language TEXT NOT NULL,
    max_videos INTEGER NOT NULL CHECK (max_videos BETWEEN 1 AND 50),
    selected_url TEXT,
    selection_method TEXT CHECK (
        selection_method IN ('view_count', 'view_count_partial', 'latest_fallback')
    ),
    status TEXT NOT NULL CHECK (
        status IN ('queued', 'discovering', 'ingesting', 'paused', 'ready', 'failed')
    ),
    candidate_count INTEGER NOT NULL DEFAULT 0,
    discovered_count INTEGER NOT NULL DEFAULT 0,
    current_video_title TEXT,
    last_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS videos (
    brain_id TEXT NOT NULL REFERENCES brains(brain_id) ON DELETE CASCADE,
    video_id TEXT NOT NULL,
    position INTEGER NOT NULL,
    title TEXT NOT NULL,
    webpage_url TEXT NOT NULL,
    duration_seconds INTEGER,
    view_count INTEGER,
    upload_date TEXT,
    status TEXT NOT NULL CHECK (
        status IN ('pending', 'processing', 'indexed', 'skipped', 'failed')
    ),
    caption_language TEXT,
    caption_kind TEXT CHECK (caption_kind IN ('manual', 'automatic')),
    error TEXT,
    PRIMARY KEY (brain_id, video_id)
);

CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    brain_id TEXT NOT NULL,
    video_id TEXT NOT NULL,
    video_title TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    start_ms INTEGER NOT NULL CHECK (start_ms >= 0),
    end_ms INTEGER NOT NULL CHECK (end_ms >= start_ms),
    text TEXT NOT NULL,
    FOREIGN KEY (brain_id, video_id)
        REFERENCES videos(brain_id, video_id) ON DELETE CASCADE,
    UNIQUE (brain_id, video_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_videos_brain_status
    ON videos(brain_id, status);
CREATE INDEX IF NOT EXISTS idx_chunks_brain_video
    ON chunks(brain_id, video_id, chunk_index);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    text,
    video_title,
    content='chunks',
    content_rowid='id',
    tokenize='porter unicode61 remove_diacritics 2'
);

CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
    INSERT INTO chunks_fts(rowid, text, video_title)
    VALUES (new.id, new.text, new.video_title);
END;

CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, text, video_title)
    VALUES ('delete', old.id, old.text, old.video_title);
END;

CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, text, video_title)
    VALUES ('delete', old.id, old.text, old.video_title);
    INSERT INTO chunks_fts(rowid, text, video_title)
    VALUES (new.id, new.text, new.video_title);
END;
"""


def now_iso() -> str:
    """Return an unambiguous UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def connect_db(db_path: Path) -> sqlite3.Connection:
    """Open a fresh configured SQLite connection for one operation."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def initialize_database(db_path: Path) -> None:
    """Create schema version 1 and fail clearly if FTS5 is unavailable or corrupt."""
    conn = connect_db(db_path)
    try:
        try:
            conn.executescript(SCHEMA)
            conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            conn.execute("INSERT INTO chunks_fts(chunks_fts) VALUES('integrity-check')")
            conn.commit()
        except sqlite3.OperationalError as exc:
            conn.rollback()
            message = str(exc).lower()
            if "fts5" in message or "no such module" in message:
                raise RuntimeError(
                    "SQLite FTS5 is required by Channel Brains but is unavailable in this Python build. "
                    "Install a standard CPython build with FTS5 support."
                ) from exc
            raise
    finally:
        conn.close()


def rebuild_fts_index(db_path: Path) -> None:
    """Explicitly rebuild FTS from caption chunks. Never called automatically."""
    with transaction(db_path) as conn:
        conn.execute("INSERT INTO chunks_fts(chunks_fts) VALUES('rebuild')")
        conn.execute("INSERT INTO chunks_fts(chunks_fts) VALUES('integrity-check')")


@contextmanager
def transaction(db_path: Path) -> Iterator[sqlite3.Connection]:
    """Yield a short write transaction and roll it back on any exception."""
    conn = connect_db(db_path)
    try:
        conn.execute("BEGIN")
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def read_transaction(db_path: Path) -> Iterator[sqlite3.Connection]:
    """Yield a read-only-use connection that is not shared between threads."""
    conn = connect_db(db_path)
    try:
        yield conn
    finally:
        conn.close()


class Repository:
    """Small repository layer. Every method opens its own SQLite connection."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def initialize_database(self) -> None:
        initialize_database(self.db_path)

    def create_brain(
        self,
        brain_id: str,
        source_url: str,
        normalized_url: str,
        channel_id: str | None,
        channel_name: str | None,
        language: str,
        max_videos: int,
    ) -> None:
        now = now_iso()
        with transaction(self.db_path) as conn:
            conn.execute(
                """INSERT INTO brains (
                    brain_id, source_url, normalized_url, channel_id, channel_name, language,
                    max_videos, status, candidate_count, discovered_count, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'queued', 0, 0, ?, ?)""",
                (
                    brain_id,
                    source_url,
                    normalized_url,
                    channel_id,
                    channel_name,
                    language,
                    max_videos,
                    now,
                    now,
                ),
            )

    def get_brain(self, brain_id: str) -> dict[str, Any] | None:
        with read_transaction(self.db_path) as conn:
            row = conn.execute("SELECT * FROM brains WHERE brain_id = ?", (brain_id,)).fetchone()
        return dict(row) if row else None

    def get_brain_by_url(self, normalized_url: str) -> dict[str, Any] | None:
        with read_transaction(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM brains WHERE normalized_url = ?", (normalized_url,)
            ).fetchone()
        return dict(row) if row else None

    def set_brain(
        self,
        brain_id: str,
        *,
        status: str | None = None,
        discovered_count: int | None = None,
        candidate_count: int | None = None,
        selection_method: str | None = None,
        selected_url: str | None = None,
        current_video_title: str | None = None,
        last_error: str | None = None,
        clear_current_video: bool = False,
    ) -> None:
        """Update whitelisted brain fields in one short transaction."""
        values: list[tuple[str, Any]] = []
        for column, value in (
            ("status", status),
            ("discovered_count", discovered_count),
            ("candidate_count", candidate_count),
            ("selection_method", selection_method),
            ("selected_url", selected_url),
            ("current_video_title", current_video_title),
            ("last_error", last_error),
        ):
            if value is not None:
                values.append((column, value))
        if clear_current_video:
            values.append(("current_video_title", None))
        values.append(("updated_at", now_iso()))
        assignments = ", ".join(f"{column} = ?" for column, _ in values)
        params = [value for _, value in values] + [brain_id]
        with transaction(self.db_path) as conn:
            conn.execute(f"UPDATE brains SET {assignments} WHERE brain_id = ?", params)

    def upsert_brain_status(self, brain_id: str, status: str) -> None:
        self.set_brain(brain_id, status=status)

    def mark_failed(self, brain_id: str, error: str) -> None:
        self.set_brain(
            brain_id,
            status="failed",
            last_error=sanitize_error(error),
            clear_current_video=True,
        )

    def set_brain_info(
        self,
        brain_id: str,
        *,
        discovered_count: int | None = None,
        candidate_count: int | None = None,
        selection_method: str | None = None,
        selected_url: str | None = None,
        current_video_title: str | None = None,
    ) -> None:
        self.set_brain(
            brain_id,
            discovered_count=discovered_count,
            candidate_count=candidate_count,
            selection_method=selection_method,
            selected_url=selected_url,
            current_video_title=current_video_title,
        )

    def update_brain_stage(
        self, brain_id: str, status: str, current_video_title: str | None = None
    ) -> None:
        self.set_brain(brain_id, status=status, current_video_title=current_video_title)

    def insert_candidate_manifest(
        self,
        brain_id: str,
        videos: Sequence[dict[str, Any]],
        selection_method: str,
        selected_url: str,
        discovered_count: int,
    ) -> None:
        """Persist selected listing candidates. Existing rows are retained on resume."""
        with transaction(self.db_path) as conn:
            conn.execute(
                """UPDATE brains SET candidate_count = ?, discovered_count = ?,
                   selection_method = ?, selected_url = ?, updated_at = ?
                   WHERE brain_id = ?""",
                (
                    len(videos),
                    discovered_count,
                    selection_method,
                    selected_url[:500],
                    now_iso(),
                    brain_id,
                ),
            )
            for position, video in enumerate(videos, start=1):
                conn.execute(
                    """INSERT OR IGNORE INTO videos (
                        brain_id, video_id, position, title, webpage_url, duration_seconds,
                        view_count, upload_date, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending')""",
                    (
                        brain_id,
                        str(video["video_id"]),
                        int(video.get("position", position)),
                        str(video.get("title") or "Untitled")[:200],
                        str(video.get("webpage_url") or f"https://youtu.be/{video['video_id']}")[:500],
                        _as_int(video.get("duration_seconds")),
                        _as_int(video.get("view_count")),
                        _as_str(video.get("upload_date")),
                    ),
                )

    def get_pending_videos(self, brain_id: str) -> list[dict[str, Any]]:
        with read_transaction(self.db_path) as conn:
            rows = conn.execute(
                """SELECT * FROM videos
                   WHERE brain_id = ? AND status IN ('pending', 'failed')
                   ORDER BY position""",
                (brain_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_video(self, brain_id: str, video_id: str) -> dict[str, Any] | None:
        with read_transaction(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM videos WHERE brain_id = ? AND video_id = ?",
                (brain_id, video_id),
            ).fetchone()
        return dict(row) if row else None

    def get_videos_for_brain(self, brain_id: str) -> list[dict[str, Any]]:
        with read_transaction(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM videos WHERE brain_id = ? ORDER BY position", (brain_id,)
            ).fetchall()
        return [dict(row) for row in rows]

    def upsert_video_status(
        self,
        brain_id: str,
        video_id: str,
        status: str,
        *,
        conn: sqlite3.Connection | None = None,
        error: str | None = None,
        caption_language: str | None = None,
        caption_kind: str | None = None,
    ) -> None:
        """Update one video, optionally inside the caller's atomic transaction."""
        owns_connection = conn is None
        if conn is None:
            conn = connect_db(self.db_path)
        try:
            assignments: list[str] = ["status = ?"]
            params: list[Any] = [status]
            if error is not None:
                assignments.append("error = ?")
                params.append(sanitize_error(error))
            if caption_language is not None:
                assignments.append("caption_language = ?")
                params.append(caption_language)
            if caption_kind is not None:
                assignments.append("caption_kind = ?")
                params.append(caption_kind)
            params.extend([brain_id, video_id])
            conn.execute(
                f"UPDATE videos SET {', '.join(assignments)} WHERE brain_id = ? AND video_id = ?",
                params,
            )
            if owns_connection:
                conn.commit()
        except BaseException:
            if owns_connection:
                conn.rollback()
            raise
        finally:
            if owns_connection:
                conn.close()

    def delete_video_chunks(self, conn: sqlite3.Connection, brain_id: str, video_id: str) -> None:
        conn.execute(
            "DELETE FROM chunks WHERE brain_id = ? AND video_id = ?", (brain_id, video_id)
        )

    def insert_chunk(
        self,
        conn: sqlite3.Connection,
        *,
        brain_id: str,
        video_id: str,
        video_title: str,
        chunk_index: int,
        start_ms: int,
        end_ms: int,
        text: str,
    ) -> None:
        conn.execute(
            """INSERT INTO chunks (
                brain_id, video_id, video_title, chunk_index, start_ms, end_ms, text
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(brain_id, video_id, chunk_index) DO UPDATE SET
                video_title = excluded.video_title,
                start_ms = excluded.start_ms,
                end_ms = excluded.end_ms,
                text = excluded.text""",
            (brain_id, video_id, video_title[:200], chunk_index, start_ms, end_ms, text),
        )

    def get_brain_status(self, brain_id: str | None = None) -> list[dict[str, Any]] | dict[str, Any]:
        with read_transaction(self.db_path) as conn:
            if brain_id is not None:
                row = conn.execute("SELECT * FROM brains WHERE brain_id = ?", (brain_id,)).fetchone()
                return self._enrich_brain(conn, dict(row)) if row else {}
            rows = conn.execute("SELECT * FROM brains ORDER BY updated_at DESC").fetchall()
            return [self._enrich_brain(conn, dict(row)) for row in rows]

    @staticmethod
    def _enrich_brain(conn: sqlite3.Connection, brain: dict[str, Any]) -> dict[str, Any]:
        brain_id = brain["brain_id"]
        rows = conn.execute(
            "SELECT status, COUNT(*) AS count FROM videos WHERE brain_id = ? GROUP BY status",
            (brain_id,),
        ).fetchall()
        counts = {row["status"]: row["count"] for row in rows}
        brain.update(
            pending_count=counts.get("pending", 0),
            processing_count=counts.get("processing", 0),
            indexed_count=counts.get("indexed", 0),
            skipped_count=counts.get("skipped", 0),
            failed_count=counts.get("failed", 0),
            chunk_count=conn.execute(
                "SELECT COUNT(*) FROM chunks WHERE brain_id = ?", (brain_id,)
            ).fetchone()[0],
        )
        return brain

    def list_videos_paginated(self, brain_id: str, offset: int = 0, limit: int = 20) -> dict[str, Any]:
        offset = max(0, offset)
        limit = max(1, min(limit, 50))
        with read_transaction(self.db_path) as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM videos WHERE brain_id = ?", (brain_id,)
            ).fetchone()[0]
            rows = conn.execute(
                """SELECT * FROM videos WHERE brain_id = ? ORDER BY position
                   LIMIT ? OFFSET ?""",
                (brain_id, limit, offset),
            ).fetchall()
        return {
            "brain_id": brain_id,
            "offset": offset,
            "limit": limit,
            "total": total,
            "next_offset": offset + limit if offset + limit < total else None,
            "videos": [dict(row) for row in rows],
        }

    def search_chunks(
        self,
        query: str,
        tokens: Sequence[str],
        brain_id: str | None = None,
        limit: int = 8,
    ) -> list[dict[str, Any]]:
        """Run a parameterized FTS query made only from individually quoted tokens."""
        del query  # The caller passes it for logging/schema symmetry; never interpolate it into FTS.
        clean_tokens = [token.replace('"', '""') for token in tokens if token.strip()]
        if not clean_tokens:
            return []
        fts_query = " OR ".join(f'"{token}"' for token in clean_tokens)
        limit = max(1, min(limit, 20))
        with read_transaction(self.db_path) as conn:
            rows = conn.execute(
                """SELECT c.brain_id, b.channel_name, c.video_id, c.video_title,
                          v.upload_date, c.start_ms, c.end_ms, c.text,
                          bm25(chunks_fts, 5.0, 2.0) AS bm25_score
                   FROM chunks_fts
                   JOIN chunks AS c ON c.id = chunks_fts.rowid
                   JOIN brains AS b ON b.brain_id = c.brain_id
                   JOIN videos AS v ON v.brain_id = c.brain_id AND v.video_id = c.video_id
                   WHERE chunks_fts MATCH ? AND (? IS NULL OR c.brain_id = ?)
                   ORDER BY bm25_score ASC LIMIT ?""",
                (fts_query, brain_id, brain_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def delete_brain(self, brain_id: str) -> dict[str, int]:
        with transaction(self.db_path) as conn:
            video_count = conn.execute(
                "SELECT COUNT(*) FROM videos WHERE brain_id = ?", (brain_id,)
            ).fetchone()[0]
            chunk_count = conn.execute(
                "SELECT COUNT(*) FROM chunks WHERE brain_id = ?", (brain_id,)
            ).fetchone()[0]
            conn.execute("DELETE FROM brains WHERE brain_id = ?", (brain_id,))
        return {"deleted_video_count": video_count, "deleted_chunk_count": chunk_count}

    def recover_brain(self, brain_id: str) -> None:
        """Recover one stale brain only while the caller holds the shared ingest lock."""
        with transaction(self.db_path) as conn:
            conn.execute(
                "UPDATE videos SET status = 'pending' WHERE brain_id = ? AND status = 'processing'",
                (brain_id,),
            )
            conn.execute(
                """UPDATE brains SET status = 'paused', current_video_title = NULL,
                   last_error = ?, updated_at = ?
                   WHERE brain_id = ? AND status IN ('queued', 'discovering', 'ingesting')""",
                (
                    "A previous ingestion was interrupted and is now resuming.",
                    now_iso(),
                    brain_id,
                ),
            )


def sanitize_error(value: object) -> str:
    """Keep errors useful while excluding URL queries, tracebacks, and large payloads."""
    text = str(value).replace("\r", " ").replace("\n", " ")
    text = text.split("?", 1)[0]
    return text[:500]


def _as_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _as_str(value: object) -> str | None:
    return str(value) if value is not None else None
