from __future__ import annotations

import os
from pathlib import Path

import platformdirs

APP_NAME = "channel-brains-mcp"
VERSION = "0.1.2"
MAX_VIDEOS = 50
DEFAULT_LANGUAGE = "en"
TARGET_CHUNK_SECONDS = 45
MAX_CHUNK_CHARS = 900
MAX_SEARCH_RESULTS = 20


def get_data_dir() -> Path:
    """Return CHANNEL_BRAINS_HOME when set, otherwise platformdirs.user_data_path."""
    env = os.environ.get("CHANNEL_BRAINS_HOME")
    if env:
        return Path(env)
    return Path(platformdirs.user_data_path(APP_NAME))


def get_db_path() -> Path:
    """Create the data directory and return <data_dir>/channel_brains.sqlite3."""
    data_dir = get_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "channel_brains.sqlite3"


def get_ingest_lock_path() -> Path:
    """Return <data_dir>/ingest.lock for cross-process ingestion serialization."""
    return get_data_dir() / "ingest.lock"


class paths:
    """Simple namespace of well-known paths."""

    database_path: Path
    ingest_lock_path: Path

    def __init__(self) -> None:
        self.database_path = get_db_path()
        self.ingest_lock_path = get_ingest_lock_path()


def get_paths() -> paths:
    """Return a simple namespace of all well-known paths."""
    return paths()
