"""End-to-end stdio protocol verification for the packaged MCP server."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import pytest
from mcp import Client
from mcp.client.stdio import StdioServerParameters, stdio_client

EXPECTED_TOOL_NAMES = {
    "create_brain",
    "get_brain_status",
    "list_brain_videos",
    "search_brain",
    "get_video_transcript",
    "delete_brain",
}


@pytest.mark.asyncio
async def test_stdio_client_discovers_exactly_six_tools_and_calls_local_status(
    tmp_path: Path,
) -> None:
    """A fresh subprocess speaks MCP over stdout without any network work."""
    env = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    env["CHANNEL_BRAINS_HOME"] = str(tmp_path / "data")
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "channel_brains_mcp"],
        env=env,
    )

    async def exercise_contract() -> None:
        async with Client(stdio_client(params)) as client:
            listing = await client.list_tools()
            assert {tool.name for tool in listing.tools} == EXPECTED_TOOL_NAMES

            status = await client.call_tool("get_brain_status", {})
            assert status.structured_content == {"brains": [], "count": 0}

            search = await client.call_tool("search_brain", {"query": "pricing strategy"})
            assert search.structured_content["query"] == "pricing strategy"
            assert search.structured_content["results"] == []

            unknown = await client.call_tool("not_a_channel_brains_tool", {})
            assert unknown.is_error is True

    try:
        await asyncio.wait_for(exercise_contract(), timeout=60)
    except TimeoutError:
        pytest.fail("stdio MCP handshake, calls, or subprocess teardown exceeded 60 seconds")
