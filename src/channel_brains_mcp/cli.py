"""One-shot command bridge for clients whose current MCP tool list is frozen."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections.abc import Callable, Sequence
from typing import Any

import anyio

from channel_brains_mcp.config import VERSION, get_data_dir, get_paths
from channel_brains_mcp.db import Repository
from channel_brains_mcp.jobs import JobManager
from channel_brains_mcp.server import (
    DEFAULT_MONITOR_POLL_SECONDS,
    DEFAULT_MONITOR_TIMEOUT_SECONDS,
    build_server,
    configure_logging_to_stderr,
)
from channel_brains_mcp.youtube import YoutubeClient

WorkerStarter = Callable[[str], None]


def _runtime(*, auto_start: bool) -> tuple[Repository, JobManager]:
    paths = get_paths()
    repo = Repository(paths.database_path)
    repo.initialize_database()
    jobs = JobManager(
        repo=repo,
        youtube=YoutubeClient(),
        lock_path=str(paths.ingest_lock_path),
        auto_start=auto_start,
    )
    return repo, jobs


def _worker_command(brain_id: str) -> list[str]:
    return [sys.executable, "-m", "channel_brains_mcp.cli", "_worker", brain_id]


def _start_worker(brain_id: str) -> None:
    data_dir = get_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    log_path = data_dir / "worker.log"
    options: dict[str, Any] = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "close_fds": True,
        "env": os.environ.copy(),
    }
    if os.name == "nt":  # pragma: no cover - exercised by Windows CI smoke coverage
        options["creationflags"] = (
            subprocess.CREATE_NEW_PROCESS_GROUP
            | subprocess.DETACHED_PROCESS
            | subprocess.CREATE_NO_WINDOW
        )
    else:
        options["start_new_session"] = True
    with log_path.open("ab") as worker_log:
        options["stderr"] = worker_log
        subprocess.Popen(_worker_command(brain_id), **options)


def _arguments(namespace: argparse.Namespace) -> dict[str, object]:
    if namespace.tool == "create_brain":
        return {
            "channel_url": namespace.channel_url,
            "max_videos": namespace.max_videos,
            "language": namespace.language,
        }
    if namespace.tool == "get_brain_status":
        arguments: dict[str, object] = {
            "wait_until_terminal": namespace.wait_until_terminal,
            "timeout_seconds": namespace.timeout_seconds,
            "poll_interval_seconds": namespace.poll_interval_seconds,
        }
        if namespace.brain_id:
            arguments["brain_id"] = namespace.brain_id
        return arguments
    if namespace.tool == "list_brain_videos":
        return {
            "brain_id": namespace.brain_id,
            "offset": namespace.offset,
            "limit": namespace.limit,
        }
    if namespace.tool == "search_brain":
        return {
            "query": namespace.query,
            "brain_id": namespace.brain_id,
            "limit": namespace.limit,
        }
    if namespace.tool == "get_video_transcript":
        return {
            "brain_id": namespace.brain_id,
            "video_id": namespace.video_id,
            "offset": namespace.offset,
            "limit": namespace.limit,
        }
    if namespace.tool == "delete_brain":
        return {"brain_id": namespace.brain_id, "confirm": namespace.confirm}
    raise ValueError(f"Unsupported command: {namespace.tool}")


async def _execute(
    tool_name: str,
    arguments: dict[str, object],
    *,
    start_worker: WorkerStarter = _start_worker,
) -> dict[str, object]:
    repo, jobs = _runtime(auto_start=False)
    server = build_server(repo, jobs)
    result = await server.call_tool(tool_name, arguments)
    structured = result.structured_content
    if not isinstance(structured, dict):
        messages = [
            str(block.text)
            for block in result.content
            if getattr(block, "type", None) == "text" and getattr(block, "text", None)
        ]
        raise RuntimeError("; ".join(messages) or f"{tool_name} failed")
    if tool_name == "create_brain" and structured.get("queued") is True:
        brain_id = structured.get("brain_id")
        if not isinstance(brain_id, str) or not brain_id:
            raise RuntimeError("create_brain returned an invalid queued brain_id")
        start_worker(brain_id)
    return structured


def _add_pagination(parser: argparse.ArgumentParser, *, default_limit: int) -> None:
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int, default=default_limit)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="channel-brains",
        description="Use Channel Brains when the current task's MCP tool list is frozen.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    commands = parser.add_subparsers(dest="tool", required=True)

    create = commands.add_parser("create_brain", help="create or resume a channel brain")
    create.add_argument("--channel-url", required=True)
    create.add_argument("--max-videos", type=int, default=50)
    create.add_argument("--language", default="en")

    status = commands.add_parser("get_brain_status", help="read one or all brain statuses")
    status.add_argument("--brain-id")
    status.add_argument(
        "--wait-until-terminal",
        action="store_true",
        help="wait locally until the brain is ready, paused, failed, or times out",
    )
    status.add_argument(
        "--timeout-seconds", type=int, default=DEFAULT_MONITOR_TIMEOUT_SECONDS
    )
    status.add_argument(
        "--poll-interval-seconds", type=int, default=DEFAULT_MONITOR_POLL_SECONDS
    )

    videos = commands.add_parser("list_brain_videos", help="list videos for a brain")
    videos.add_argument("--brain-id", required=True)
    _add_pagination(videos, default_limit=20)

    search = commands.add_parser("search_brain", help="search timestamped caption evidence")
    search.add_argument("--query", required=True)
    search.add_argument("--brain-id")
    search.add_argument("--limit", type=int, default=8)

    transcript = commands.add_parser(
        "get_video_transcript", help="read stored transcript chunks"
    )
    transcript.add_argument("--brain-id", required=True)
    transcript.add_argument("--video-id", required=True)
    _add_pagination(transcript, default_limit=50)

    delete = commands.add_parser("delete_brain", help="delete a completed brain")
    delete.add_argument("--brain-id", required=True)
    delete.add_argument("--confirm", action="store_true")

    return parser


def _run_worker(brain_id: str) -> int:
    configure_logging_to_stderr()
    _, jobs = _runtime(auto_start=False)
    jobs.run_now(brain_id)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments and arguments[0] == "_worker":
        worker_parser = argparse.ArgumentParser(prog="channel-brains _worker")
        worker_parser.add_argument("brain_id")
        worker = worker_parser.parse_args(arguments[1:])
        return _run_worker(worker.brain_id)

    parser = build_parser()
    namespace = parser.parse_args(arguments)
    configure_logging_to_stderr()
    try:
        output = anyio.run(_execute, namespace.tool, _arguments(namespace))
    except Exception as exc:
        print(json.dumps({"status": "error", "message": str(exc)}), file=sys.stderr)
        return 1
    print(json.dumps(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
