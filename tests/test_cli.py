"""Contract tests for the same-session command bridge."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from channel_brains_mcp import cli
from channel_brains_mcp.db import Repository, initialize_database
from channel_brains_mcp.server import TOOL_NAMES


def test_help_exposes_exactly_the_six_mcp_operation_names() -> None:
    parser = cli.build_parser()
    subparsers = next(
        action for action in parser._actions if action.dest == "tool"
    )

    assert set(subparsers.choices) == set(TOOL_NAMES)


@pytest.mark.asyncio
async def test_valid_create_returns_mcp_shape_and_starts_detached_worker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CHANNEL_BRAINS_HOME", str(tmp_path))
    started: list[str] = []

    output = await cli._execute(
        "create_brain",
        {
            "channel_url": "https://www.youtube.com/@example",
            "max_videos": 3,
            "language": "en",
        },
        start_worker=started.append,
    )

    assert output["status"] == "queued"
    assert output["queued"] is True
    assert output["monitoring_required"] is True
    assert "REQUIRED NEXT ACTION" in output["monitoring_instruction"]
    assert "Do not reply to the user yet" in output["monitoring_instruction"]
    assert "scheduled task" in output["monitoring_instruction"]
    assert started == [output["brain_id"]]


@pytest.mark.asyncio
async def test_invalid_create_never_starts_worker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CHANNEL_BRAINS_HOME", str(tmp_path))
    started: list[str] = []

    output = await cli._execute(
        "create_brain",
        {"channel_url": "https://youtu.be/not-a-channel"},
        start_worker=started.append,
    )

    assert output["status"] == "error"
    assert output["queued"] is False
    assert output["monitoring_required"] is False
    assert "monitoring_instruction" not in output
    assert started == []


def test_subprocess_status_emits_one_structured_json_object(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["CHANNEL_BRAINS_HOME"] = str(tmp_path)

    result = subprocess.run(
        [sys.executable, "-m", "channel_brains_mcp.cli", "get_brain_status"],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    assert json.loads(result.stdout) == {"brains": [], "count": 0}
    assert result.stderr == ""


def test_worker_starter_detaches_with_the_current_python_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CHANNEL_BRAINS_HOME", str(tmp_path))
    captured: dict[str, object] = {}

    def fake_popen(command: list[str], **options: object) -> object:
        captured["command"] = command
        captured["options"] = options
        return object()

    monkeypatch.setattr(cli.subprocess, "Popen", fake_popen)

    cli._start_worker("a0b1c2d3e4f5")

    assert captured["command"] == [
        sys.executable,
        "-m",
        "channel_brains_mcp.cli",
        "_worker",
        "a0b1c2d3e4f5",
    ]
    options = captured["options"]
    assert isinstance(options, dict)
    assert options["stdin"] is subprocess.DEVNULL
    assert options["stdout"] is subprocess.DEVNULL
    assert options["env"] == os.environ
    if os.name == "nt":
        assert int(options["creationflags"]) & subprocess.DETACHED_PROCESS
    else:
        assert options["start_new_session"] is True
    assert (tmp_path / "worker.log").exists()


def test_status_bridge_owns_waiting_until_a_terminal_state(tmp_path: Path) -> None:
    db_path = tmp_path / "channel_brains.sqlite3"
    initialize_database(db_path)
    repo = Repository(db_path)
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
    repo.set_brain(brain_id, status="ready")
    env = os.environ.copy()
    env["CHANNEL_BRAINS_HOME"] = str(tmp_path)

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "channel_brains_mcp.cli",
            "get_brain_status",
            "--brain-id",
            brain_id,
            "--wait-until-terminal",
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    output = json.loads(result.stdout)
    assert output["waited"] is True
    assert output["terminal"] is True
    assert output["brains"][0]["status"] == "ready"


def test_delete_bridge_keeps_confirmation_default_false(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["CHANNEL_BRAINS_HOME"] = str(tmp_path)

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "channel_brains_mcp.cli",
            "delete_brain",
            "--brain-id",
            "a0b1c2d3e4f5",
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    output = json.loads(result.stdout)
    assert output["deleted"] is False
    assert output["message"] == "Deletion requires confirm=true."
