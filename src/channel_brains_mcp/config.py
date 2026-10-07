from __future__ import annotations

import hashlib
import os
from pathlib import Path

import platformdirs

APP_NAME = "channel-brains-mcp"
VERSION = "0.1.4"
MAX_VIDEOS = 50
DEFAULT_LANGUAGE = "en"
TARGET_CHUNK_SECONDS = 45
MAX_CHUNK_CHARS = 900
MAX_SEARCH_RESULTS = 20
DEFAULT_HTTP_HOST = "127.0.0.1"
DEFAULT_HTTP_PORT = 8000
DEFAULT_HTTP_PATH = "/mcp"


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


def get_user_data_dir(sub: str) -> Path:
    """Return a hashed per-user data directory under <data_dir>/users/.

    Authenticated users get isolated SQLite databases and ingest locks; the
    hash keeps directory names filesystem-safe and free of raw identifiers.
    """
    digest = hashlib.sha256(sub.encode("utf-8")).hexdigest()[:16]
    return get_data_dir() / "users" / digest


def get_http_path() -> str:
    """Return the streamable-HTTP mount path from CHANNEL_BRAINS_HTTP_PATH.

    Hosting behind an unguessable path (for example /t/<random-token>/mcp) is the
    access-control layer for deployments without OAuth.
    """
    value = os.environ.get("CHANNEL_BRAINS_HTTP_PATH", DEFAULT_HTTP_PATH).strip()
    if not value.startswith("/"):
        value = f"/{value}"
    return value.rstrip("/") or DEFAULT_HTTP_PATH


def get_auth_issuer() -> str:
    """Return the OAuth issuer URL (CHANNEL_BRAINS_AUTH_ISSUER); empty disables auth.

    Auth0 issuers are compared exactly, including exactly one trailing slash.
    """
    issuer = os.environ.get("CHANNEL_BRAINS_AUTH_ISSUER", "").strip().rstrip("/")
    return f"{issuer}/" if issuer else ""


def get_auth_audience() -> str:
    """Return the token audience / resource identifier (CHANNEL_BRAINS_AUTH_AUDIENCE)."""
    return os.environ.get("CHANNEL_BRAINS_AUTH_AUDIENCE", "").strip()


def get_openai_challenge_token() -> str:
    """Return the OpenAI apps domain-verification token; empty serves 404."""
    return os.environ.get("CHANNEL_BRAINS_OPENAI_CHALLENGE_TOKEN", "").strip()


def get_demo_video_path() -> str:
    """Return the packaged demo walkthrough video path; empty disables the route."""
    return os.environ.get("CHANNEL_BRAINS_DEMO_VIDEO", "").strip()


def get_http_host() -> str:
    return os.environ.get("CHANNEL_BRAINS_HTTP_HOST", DEFAULT_HTTP_HOST)


def get_http_port() -> int:
    for key in ("CHANNEL_BRAINS_HTTP_PORT", "PORT"):
        value = os.environ.get(key)
        if value and value.strip().isdigit():
            return int(value)
    return DEFAULT_HTTP_PORT


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
