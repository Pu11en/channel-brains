"""Manual live contract test: YouTube channel to timestamped local evidence."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from channel_brains_mcp.db import Repository, initialize_database, read_transaction
from channel_brains_mcp.jobs import ingest_brain
from channel_brains_mcp.server import _search
from channel_brains_mcp.youtube import YoutubeClient, normalize_channel_url


@pytest.mark.live
def test_live_channel_ingests_caption_and_returns_timestamped_search(tmp_path: Path) -> None:
    channel_url = normalize_channel_url(
        os.environ.get("CHANNEL_BRAINS_LIVE_CHANNEL", "https://www.youtube.com/@OpenAI")
    )
    db_path = tmp_path / "live.sqlite3"
    initialize_database(db_path)
    repo = Repository(db_path)
    brain_id = "11aa22bb33cc"
    repo.create_brain(brain_id, channel_url, channel_url, None, None, "en", 3)

    ingest_brain(repo, brain_id, YoutubeClient())

    status = repo.get_brain_status(brain_id)
    assert status["status"] == "ready", status["last_error"]
    assert status["indexed_count"] >= 1
    with read_transaction(db_path) as conn:
        chunk = conn.execute(
            "SELECT text FROM chunks WHERE brain_id = ? ORDER BY id LIMIT 1", (brain_id,)
        ).fetchone()
    assert chunk is not None
    query = next(word for word in str(chunk["text"]).split() if len(word) >= 4)

    result = _search(repo, query, brain_id, 1)

    assert result.results
    assert result.results[0].url.startswith("https://youtu.be/")
    assert "?t=" in result.results[0].url
    assert result.results[0].timestamp
