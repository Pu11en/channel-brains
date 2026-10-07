"""OAuth dual-path behavior for the hosted server: public auth, secret path free."""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
import uvicorn
from starlette.types import ASGIApp

from channel_brains_mcp.db import Repository, initialize_database
from channel_brains_mcp.server import build_http_app, build_server

SECRET_PATH = "/t/test-token/mcp"


class _ServerHandle:
    def __init__(self, app: ASGIApp) -> None:
        config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning")
        self.uv = uvicorn.Server(config)
        self.thread = threading.Thread(target=self.uv.run, daemon=True)

    def start(self) -> str:
        self.thread.start()
        deadline = time.monotonic() + 10
        while not self.uv.started:
            if time.monotonic() > deadline:
                pytest.fail("test server failed to start")
            time.sleep(0.05)
        port = self.uv.servers[0].sockets[0].getsockname()[1]
        return f"http://127.0.0.1:{port}"

    def stop(self) -> None:
        self.uv.should_exit = True
        self.thread.join(timeout=5)


def _build_app(tmp_path: Path) -> ASGIApp:
    db_path = tmp_path / "channel_brains.sqlite3"
    initialize_database(db_path)
    repo = Repository(db_path)
    from channel_brains_mcp.jobs import JobManager
    from channel_brains_mcp.youtube import YoutubeClient

    jobs = JobManager(repo=repo, youtube=YoutubeClient(), lock_path=str(tmp_path / "ingest.lock"))
    return build_http_app(build_server(repo, jobs), host="0.0.0.0")


@pytest.fixture()
def auth_server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    monkeypatch.setenv("CHANNEL_BRAINS_HOME", str(tmp_path))
    monkeypatch.setenv("CHANNEL_BRAINS_HTTP_PATH", SECRET_PATH)
    monkeypatch.setenv("CHANNEL_BRAINS_AUTH_ISSUER", "https://example-issuer.test/")
    monkeypatch.setenv("CHANNEL_BRAINS_AUTH_AUDIENCE", "https://channel-brains.test")

    from channel_brains_mcp import server as server_module

    class _StubValidator:
        def __init__(self) -> None:
            self.tokens: dict[str, dict] = {"good-token": {"sub": "user-123"}}

        async def verify(self, token: str) -> dict | None:
            return self.tokens.get(token)

    original = server_module.TokenValidator
    server_module.TokenValidator = lambda config: _StubValidator()  # type: ignore[assignment]
    handle = _ServerHandle(_build_app(tmp_path))
    base = handle.start()
    try:
        yield base
    finally:
        server_module.TokenValidator = original  # type: ignore[assignment]
        handle.stop()


def test_metadata_endpoint_advertises_issuer(auth_server: str) -> None:
    with httpx.Client() as client:
        response = client.get(f"{auth_server}/.well-known/oauth-protected-resource")
        assert response.status_code == 200
        payload = response.json()
        assert payload["resource"] == "https://channel-brains.test"
        assert payload["authorization_servers"] == ["https://example-issuer.test"]


def test_public_mcp_requires_bearer_and_accepts_valid_token(auth_server: str) -> None:
    headers_json = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
    initialize = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "auth-test", "version": "0"},
        },
    }
    with httpx.Client() as client:
        denied = client.post(f"{auth_server}/mcp", headers=headers_json, json=initialize)
        assert denied.status_code == 401
        assert "WWW-Authenticate" in denied.headers

        bad = client.post(
            f"{auth_server}/mcp",
            headers={**headers_json, "Authorization": "Bearer wrong-token"},
            json=initialize,
        )
        assert bad.status_code == 401

        allowed = client.post(
            f"{auth_server}/mcp",
            headers={**headers_json, "Authorization": "Bearer good-token"},
            json=initialize,
        )
        assert allowed.status_code == 200
        assert "serverInfo" in allowed.text


def test_secret_path_still_works_without_any_token(auth_server: str) -> None:
    with httpx.Client() as client:
        response = client.post(
            f"{auth_server}{SECRET_PATH}",
            headers={"Accept": "application/json, text/event-stream", "Content-Type": "application/json"},
            json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
        )
        assert response.status_code == 200


def test_openai_challenge_serves_exact_token_without_auth(
    auth_server: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CHANNEL_BRAINS_OPENAI_CHALLENGE_TOKEN", "openai-apps-token-123")
    with httpx.Client() as client:
        response = client.get(f"{auth_server}/.well-known/openai-apps-challenge")
        assert response.status_code == 200
        assert response.text == "openai-apps-token-123"
        assert response.text == response.text.strip()
        assert response.headers["content-type"].startswith("text/plain")


def test_openai_challenge_is_404_without_configured_token(
    auth_server: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("CHANNEL_BRAINS_OPENAI_CHALLENGE_TOKEN", raising=False)
    with httpx.Client() as client:
        response = client.get(f"{auth_server}/.well-known/openai-apps-challenge")
        assert response.status_code == 404


def test_demo_video_served_without_auth(
    auth_server: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    video = tmp_path / "demo.mp4"
    video.write_bytes(b"\x00\x00\x00\x18ftypmp42")
    monkeypatch.setenv("CHANNEL_BRAINS_DEMO_VIDEO", str(video))
    with httpx.Client() as client:
        response = client.get(f"{auth_server}/demo.mp4")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("video/mp4")
        assert response.content.startswith(b"\x00\x00\x00\x18ftyp")


def test_demo_video_is_404_without_configured_file(
    auth_server: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("CHANNEL_BRAINS_DEMO_VIDEO", raising=False)
    with httpx.Client() as client:
        response = client.get(f"{auth_server}/demo.mp4")
        assert response.status_code == 404


class _FailingYoutube:
    """Offline YouTube stub: discovery fails fast so brains reach a terminal state."""

    def extract_listing(self, normalized_url: str) -> list[dict]:
        raise RuntimeError("offline test stub")

    def extract_metadata(self, webpage_url: str) -> dict | None:
        return None


def test_authenticated_users_are_isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Two token subjects get separate brain spaces; neither sees the other's data."""
    import anyio

    from channel_brains_mcp.auth import current_sub
    from channel_brains_mcp.db import Repository, initialize_database
    from channel_brains_mcp.jobs import JobManager
    from channel_brains_mcp.server import UserStore, build_server

    monkeypatch.setenv("CHANNEL_BRAINS_HOME", str(tmp_path))
    base_db = tmp_path / "channel_brains.sqlite3"
    initialize_database(base_db)
    base_repo = Repository(base_db)
    base_jobs = JobManager(
        repo=base_repo, youtube=_FailingYoutube(), lock_path=str(tmp_path / "ingest.lock"), auto_start=False
    )
    store = UserStore(base_repo, base_jobs)
    server = build_server(base_repo, base_jobs, store=store)

    async def scenario() -> None:
        tools = await server.list_tools()
        tool_names = {t.name for t in tools}
        assert tool_names == {
            "create_brain",
            "get_brain_status",
            "list_brain_videos",
            "search_brain",
            "get_video_transcript",
            "delete_brain",
        }

        token_a = current_sub.set("user-a")
        created = await server.call_tool("create_brain", {"channel_url": "https://www.youtube.com/@one"})
        assert created.structured_content["status"] == "queued"
        current_sub.reset(token_a)

        token_b = current_sub.set("user-b")
        stranger = await server.call_tool("get_brain_status", {})
        assert stranger.structured_content["count"] == 0
        current_sub.reset(token_b)

        token_a = current_sub.set("user-a")
        owner = await server.call_tool("get_brain_status", {})
        assert owner.structured_content["count"] == 1
        current_sub.reset(token_a)

        anonymous = await server.call_tool("get_brain_status", {})
        assert anonymous.structured_content["count"] == 0

    anyio.run(scenario)

    user_a_dir = tmp_path / "users"
    assert user_a_dir.exists(), "authenticated user must get an isolated data directory"


def test_quota_blocks_fourth_brain_and_profile_reports_sub(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import anyio

    from channel_brains_mcp.auth import current_sub
    from channel_brains_mcp.db import Repository, initialize_database
    from channel_brains_mcp.jobs import JobManager
    from channel_brains_mcp.server import UserStore, build_server

    monkeypatch.setenv("CHANNEL_BRAINS_HOME", str(tmp_path))
    base_db = tmp_path / "channel_brains.sqlite3"
    initialize_database(base_db)
    repo = Repository(base_db)
    jobs = JobManager(repo=repo, youtube=_FailingYoutube(), lock_path=str(tmp_path / "ingest.lock"), auto_start=False)
    server = build_server(repo, jobs, store=UserStore(repo, jobs), auth_enabled=True)

    async def scenario() -> None:
        token = current_sub.set("quota-user")
        profile = await server.call_tool("get_profile", {})
        assert profile.structured_content["id"] == "quota-user"

        for handle in ("@one", "@two", "@three"):
            result = await server.call_tool(
                "create_brain", {"channel_url": f"https://www.youtube.com/{handle}"}
            )
            assert result.structured_content["status"] in {"queued", "error"}

        blocked = await server.call_tool("create_brain", {"channel_url": "https://www.youtube.com/@four"})
        assert blocked.structured_content["status"] == "error"
        assert "limit reached" in blocked.structured_content["message"]

        repeat = await server.call_tool("create_brain", {"channel_url": "https://www.youtube.com/@one"})
        assert repeat.structured_content["status"] != "error" or "limit" not in repeat.structured_content["message"]
        current_sub.reset(token)

    anyio.run(scenario)


def test_retry_of_failed_brain_reports_queued_and_monitoring(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A re-queued failed brain must not claim status=failed with monitoring off."""
    import anyio

    from channel_brains_mcp.db import Repository, initialize_database
    from channel_brains_mcp.jobs import JobManager
    from channel_brains_mcp.server import UserStore, build_server

    monkeypatch.setenv("CHANNEL_BRAINS_HOME", str(tmp_path))
    base_db = tmp_path / "channel_brains.sqlite3"
    initialize_database(base_db)
    repo = Repository(base_db)
    repo.create_brain("aabbccddeeff", "https://www.youtube.com/@one", "https://www.youtube.com/@one", None, None, "en", 5)
    repo.set_brain("aabbccddeeff", status="failed", last_error="Channel discovery failed: old")
    jobs = JobManager(repo=repo, youtube=_FailingYoutube(), lock_path=str(tmp_path / "ingest.lock"), auto_start=False)
    server = build_server(repo, jobs, store=UserStore(repo, jobs))

    async def scenario() -> None:
        result = await server.call_tool("create_brain", {"channel_url": "https://www.youtube.com/@one"})
        payload = result.structured_content
        assert payload["queued"] is True
        assert payload["status"] == "queued"
        assert payload["monitoring_required"] is True

    anyio.run(scenario)
