"""Unit tests for the public Channel Brains MCP tool contract."""

from __future__ import annotations

from pathlib import Path

import pytest

from channel_brains_mcp.db import Repository, initialize_database
from channel_brains_mcp.jobs import JobManager
from channel_brains_mcp.models import BrainStatus
from channel_brains_mcp.server import (
    TOOL_NAMES,
    _tokenize_query,
    _validate_brain_id,
    _validate_language,
    _wait_for_terminal_status,
    build_server,
)


class NoNetworkYoutube:
    """A test double that fails loudly if a read-only MCP tool reaches YouTube."""

    def __getattr__(self, name: str) -> object:
        raise AssertionError(f"Unexpected YouTube call: {name}")


@pytest.fixture
def dependencies(tmp_path: Path) -> tuple[Repository, JobManager]:
    db_path = tmp_path / "channel_brains.sqlite3"
    initialize_database(db_path)
    repo = Repository(db_path)
    jobs = JobManager(repo, NoNetworkYoutube(), str(tmp_path / "ingest.lock"))
    return repo, jobs


class TestInputHelpers:
    def test_accepts_twelve_lowercase_hex_brain_id(self) -> None:
        assert _validate_brain_id("a0b1c2d3e4f5") == "a0b1c2d3e4f5"

    @pytest.mark.parametrize("value", ["", "not-hex", "A0B1C2D3E4F5", "a" * 11, "a" * 13])
    def test_rejects_invalid_brain_id(self, value: str) -> None:
        with pytest.raises(ValueError):
            _validate_brain_id(value)

    def test_normalizes_valid_language_tag(self) -> None:
        assert _validate_language("EN-us") == "en-us"

    @pytest.mark.parametrize("value", ["", "123", "x", "a" * 36])
    def test_rejects_invalid_language_tag(self, value: str) -> None:
        with pytest.raises(ValueError):
            _validate_language(value)

    def test_tokenizer_removes_stopwords_deduplicates_and_bounds(self) -> None:
        tokens = _tokenize_query("the Python python strategy strategies " + " ".join(str(i) for i in range(20)))
        assert tokens[:3] == ["python", "strategy", "strategies"]
        assert len(tokens) == 12


@pytest.mark.asyncio
async def test_all_six_tools_publish_concrete_input_and_output_schemas(
    dependencies: tuple[Repository, JobManager],
) -> None:
    repo, jobs = dependencies
    server = build_server(repo, jobs)

    tools = await server.list_tools()
    assert tuple(tool.name for tool in tools) == TOOL_NAMES
    assert len(tools) == 6
    for tool in tools:
        assert tool.input_schema["type"] == "object"
        assert tool.output_schema is not None
        assert tool.output_schema["type"] == "object"
        assert tool.output_schema.get("additionalProperties") is False

    status_tool = next(tool for tool in tools if tool.name == "get_brain_status")
    properties = status_tool.input_schema["properties"]
    assert properties["wait_until_terminal"]["default"] is False
    assert properties["timeout_seconds"]["minimum"] == 1
    assert properties["poll_interval_seconds"]["minimum"] == 1


@pytest.mark.asyncio
async def test_status_and_search_do_not_call_youtube(
    dependencies: tuple[Repository, JobManager],
) -> None:
    repo, jobs = dependencies
    server = build_server(repo, jobs)

    status = await server.call_tool("get_brain_status", {})
    assert status.structured_content == {"brains": [], "count": 0}

    search = await server.call_tool("search_brain", {"query": "pricing AI products"})
    assert search.structured_content["results"] == []


@pytest.mark.asyncio
async def test_plugin_owned_monitor_waits_until_local_status_is_terminal(
    dependencies: tuple[Repository, JobManager],
) -> None:
    repo, _ = dependencies
    brain_id = "a0b1c2d3e4f5"
    repo.create_brain(
        brain_id,
        "https://www.youtube.com/@one",
        "https://www.youtube.com/@one",
        None,
        None,
        "en",
        1,
    )
    reported: list[str] = []

    async def report(brain: BrainStatus) -> None:
        reported.append(brain.status)

    async def finish_ingestion(_: float) -> None:
        repo.set_brain(brain_id, status="ready")

    result = await _wait_for_terminal_status(
        repo,
        brain_id,
        timeout_seconds=30,
        poll_interval_seconds=5,
        report_progress=report,
        sleep=finish_ingestion,
        clock=lambda: 0,
    )

    assert result.waited is True
    assert result.terminal is True
    assert result.timed_out is False
    assert result.brains[0].status == "ready"
    assert reported == ["queued", "ready"]


@pytest.mark.asyncio
async def test_plugin_owned_monitor_returns_current_status_at_timeout(
    dependencies: tuple[Repository, JobManager],
) -> None:
    repo, _ = dependencies
    brain_id = "a0b1c2d3e4f5"
    repo.create_brain(
        brain_id,
        "https://www.youtube.com/@one",
        "https://www.youtube.com/@one",
        None,
        None,
        "en",
        1,
    )
    times = iter((0.0, 0.0, 1.0))

    async def no_sleep(_: float) -> None:
        return None

    result = await _wait_for_terminal_status(
        repo,
        brain_id,
        timeout_seconds=1,
        poll_interval_seconds=1,
        sleep=no_sleep,
        clock=lambda: next(times),
    )

    assert result.waited is True
    assert result.terminal is False
    assert result.timed_out is True
    assert result.brains[0].status == "queued"


@pytest.mark.asyncio
async def test_invalid_create_makes_no_database_row_and_enqueues_no_work(
    dependencies: tuple[Repository, JobManager],
) -> None:
    repo, jobs = dependencies
    server = build_server(repo, jobs)

    result = await server.call_tool("create_brain", {"channel_url": "https://youtu.be/not-a-channel"})

    assert result.structured_content["status"] == "error"
    assert repo.get_brain_status() == []
    assert not jobs.pending


@pytest.mark.asyncio
async def test_delete_requires_explicit_confirmation(
    dependencies: tuple[Repository, JobManager],
) -> None:
    repo, jobs = dependencies
    repo.create_brain(
        "a0b1c2d3e4f5", "https://www.youtube.com/@one", "https://www.youtube.com/@one", None, None, "en", 1
    )
    server = build_server(repo, jobs)

    result = await server.call_tool("delete_brain", {"brain_id": "a0b1c2d3e4f5"})

    assert result.structured_content["deleted"] is False
    assert repo.get_brain("a0b1c2d3e4f5") is not None
