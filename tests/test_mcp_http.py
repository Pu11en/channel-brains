"""End-to-end streamable-HTTP protocol verification for the MCP server."""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
import uvicorn
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

from channel_brains_mcp.db import Repository, initialize_database
from channel_brains_mcp.server import build_http_app, build_server

EXPECTED_TOOL_NAMES = {
    "create_brain",
    "get_brain_status",
    "list_brain_videos",
    "search_brain",
    "get_video_transcript",
    "delete_brain",
}

SECRET_PATH = "/t/test-token/mcp"


@pytest.fixture()
def http_server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """Serve the MCP app on an ephemeral localhost port; yield the base URL."""
    monkeypatch.setenv("CHANNEL_BRAINS_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("CHANNEL_BRAINS_HTTP_PATH", SECRET_PATH)
    db_path = tmp_path / "data" / "channel_brains.sqlite3"
    initialize_database(db_path)
    repo = Repository(db_path)
    repo.create_brain(
        "a0b1c2d3e4f5",
        "https://www.youtube.com/@one",
        "https://www.youtube.com/@one",
        None,
        None,
        "en",
        1,
    )
    repo.set_brain("a0b1c2d3e4f5", status="ready")

    from channel_brains_mcp.config import get_paths
    from channel_brains_mcp.jobs import JobManager
    from channel_brains_mcp.youtube import YoutubeClient

    paths = get_paths()
    jobs = JobManager(repo=repo, youtube=YoutubeClient(), lock_path=str(paths.ingest_lock_path))
    server = build_server(repo, jobs)
    config = uvicorn.Config(
        build_http_app(server), host="127.0.0.1", port=0, log_level="warning"
    )
    uv_server = uvicorn.Server(config)
    thread = threading.Thread(target=uv_server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not uv_server.started:
        if time.monotonic() > deadline:
            pytest.fail("HTTP test server failed to start within 10 seconds")
        time.sleep(0.05)
    port = uv_server.servers[0].sockets[0].getsockname()[1]
    yield f"http://127.0.0.1:{port}"
    uv_server.should_exit = True
    thread.join(timeout=5)


async def test_http_client_discovers_six_tools_and_serves_local_status(http_server: str) -> None:
    """A real MCP streamable-HTTP client completes the handshake and calls tools."""
    async with Client(streamable_http_client(f"{http_server}{SECRET_PATH}")) as client:
        listing = await client.list_tools()
        assert {tool.name for tool in listing.tools} == EXPECTED_TOOL_NAMES

        status = await client.call_tool("get_brain_status", {})
        assert status.structured_content["count"] == 1
        assert status.structured_content["brains"][0]["status"] == "ready"

        search = await client.call_tool("search_brain", {"query": "pricing strategy"})
        assert search.structured_content["results"] == []


def test_healthz_responds_and_unknown_paths_are_rejected(http_server: str) -> None:
    """/healthz is public while unknown MCP paths do not exist."""
    with httpx.Client() as client:
        health = client.get(f"{http_server}/healthz")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"
        assert health.json()["tools"] == 6

        missing = client.post(
            f"{http_server}/nope/mcp",
            headers={"Accept": "application/json, text/event-stream"},
            json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
        )
        assert missing.status_code == 404


def test_public_bind_host_accepts_public_host_header(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A deployment bound to 0.0.0.0 must accept its public domain in the Host header.

    Regression: streamable_http_app defaults to host=127.0.0.1, which turns on
    loopback-only DNS-rebinding protection and rejects production Host headers
    with 421 "Invalid Host header".
    """
    monkeypatch.setenv("CHANNEL_BRAINS_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("CHANNEL_BRAINS_HTTP_PATH", SECRET_PATH)
    db_path = tmp_path / "data" / "channel_brains.sqlite3"
    initialize_database(db_path)
    repo = Repository(db_path)

    from channel_brains_mcp.jobs import JobManager
    from channel_brains_mcp.youtube import YoutubeClient

    jobs = JobManager(repo=repo, youtube=YoutubeClient(), lock_path=str(db_path.parent / "ingest.lock"))
    server = build_server(repo, jobs)
    config = uvicorn.Config(
        build_http_app(server, host="0.0.0.0"), host="127.0.0.1", port=0, log_level="warning"
    )
    uv_server = uvicorn.Server(config)
    thread = threading.Thread(target=uv_server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not uv_server.started:
        if time.monotonic() > deadline:
            pytest.fail("HTTP test server failed to start within 10 seconds")
        time.sleep(0.05)
    port = uv_server.servers[0].sockets[0].getsockname()[1]
    try:
        with httpx.Client() as client:
            response = client.post(
                f"http://127.0.0.1:{port}{SECRET_PATH}",
                headers={
                    "Host": "channel-brains-production.up.railway.app",
                    "Accept": "application/json, text/event-stream",
                },
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-06-18",
                        "capabilities": {},
                        "clientInfo": {"name": "smoke", "version": "0"},
                    },
                },
            )
            assert response.status_code == 200
            assert "serverInfo" in response.text
    finally:
        uv_server.should_exit = True
        thread.join(timeout=5)
