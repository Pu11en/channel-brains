"""On-demand, resumable local ingestion jobs for Channel Brains."""

from __future__ import annotations

import logging
import queue
import threading
from collections.abc import Iterable
from typing import Any, Protocol

from filelock import FileLock

from channel_brains_mcp.db import Repository, sanitize_error, transaction
from channel_brains_mcp.youtube import (
    CaptionCue,
    CaptionDownloadError,
    CaptionSelection,
    select_channel_candidates,
)

logger = logging.getLogger(__name__)


class YoutubeClientLike(Protocol):
    """The injectable network boundary used by production and offline tests."""

    def extract_listing(self, normalized_url: str) -> Iterable[dict[str, object]]: ...

    def extract_metadata(self, webpage_url: str) -> dict[str, object] | None: ...

    def select_caption(self, info: dict[str, object], language: str) -> CaptionSelection | None: ...

    def download_caption_payload(self, selection: CaptionSelection) -> str: ...

    def parse_json3_cues(self, payload: str) -> list[CaptionCue]: ...

    def parse_vtt_cues(self, payload: str) -> list[CaptionCue]: ...

    def rolling_dedup_vtt(self, cues: list[CaptionCue]) -> list[CaptionCue]: ...

    def merge_cues_into_chunks(self, cues: list[CaptionCue]) -> list[dict[str, object]]: ...


class JobQueue:
    """A deduplicating in-process queue. File locking handles other processes."""

    def __init__(self) -> None:
        self._items: queue.Queue[str] = queue.Queue()
        self._pending: set[str] = set()
        self._lock = threading.Lock()

    def put(self, brain_id: str) -> bool:
        with self._lock:
            if brain_id in self._pending:
                return False
            self._pending.add(brain_id)
            self._items.put(brain_id)
            return True

    def get(self, timeout: float) -> str:
        return self._items.get(timeout=timeout)

    def done(self, brain_id: str) -> None:
        with self._lock:
            self._pending.discard(brain_id)
        self._items.task_done()

    def is_pending(self, brain_id: str) -> bool:
        with self._lock:
            return brain_id in self._pending

    @property
    def pending(self) -> set[str]:
        with self._lock:
            return set(self._pending)


class JobManager:
    """Lazy daemon worker that holds a cross-process lock during all network work."""

    def __init__(self, repo: Repository, youtube: YoutubeClientLike, lock_path: str) -> None:
        self._repo = repo
        self._youtube = youtube
        self._lock_path = lock_path
        self._queue = JobQueue()
        self._worker: threading.Thread | None = None
        self._state_lock = threading.Lock()

    @property
    def pending(self) -> set[str]:
        return self._queue.pending

    def is_queued(self, brain_id: str) -> bool:
        return self._queue.is_pending(brain_id)

    def enqueue(self, brain_id: str) -> bool:
        """Queue exactly once and lazily start one daemon worker on demand."""
        queued = self._queue.put(brain_id)
        if queued:
            self.start_worker()
        return queued

    def start_worker(self) -> None:
        """Start a worker only if one is not already live."""
        with self._state_lock:
            if self._worker is not None and self._worker.is_alive():
                return
            self._worker = threading.Thread(
                target=self._worker_loop,
                name="channel-brains-ingest",
                daemon=True,
            )
            self._worker.start()

    def _worker_loop(self) -> None:
        while True:
            try:
                brain_id = self._queue.get(timeout=0.2)
            except queue.Empty:
                return
            try:
                self._process_with_lock(brain_id)
            except Exception:
                logger.exception("Ingestion worker failed for brain %s", brain_id)
            finally:
                self._queue.done(brain_id)

    def _process_with_lock(self, brain_id: str) -> None:
        # FileLock blocks rather than overlapping network use in two harness processes.
        with FileLock(self._lock_path):
            ingest_brain(self._repo, brain_id, self._youtube)


def ingest_brain(repo: Repository, brain_id: str, youtube: YoutubeClientLike) -> None:
    """Synchronously discover and index one brain. Caller owns any cross-process lock."""
    brain = repo.get_brain(brain_id)
    if brain is None or brain["status"] == "ready":
        return

    # Recovery happens only at an explicit run, never on MCP process startup.
    repo.recover_brain(brain_id)
    brain = repo.get_brain(brain_id)
    if brain is None:
        return

    if int(brain["candidate_count"]) == 0:
        repo.set_brain(brain_id, status="discovering", last_error="")
        try:
            listing = youtube.extract_listing(str(brain["normalized_url"]))
            candidates, discovered_count, method = select_channel_candidates(
                listing, int(brain["max_videos"])
            )
        except Exception as exc:
            if _is_rate_limited(exc):
                repo.set_brain(
                    brain_id,
                    status="paused",
                    last_error="YouTube rate limited discovery (HTTP 429) after bounded retries. Create this brain again later to resume; persistent limits may require the documented cookie or proxy setting.",
                    clear_current_video=True,
                )
                return
            repo.mark_failed(brain_id, f"Channel discovery failed: {sanitize_error(exc)}")
            return
        if not candidates:
            repo.mark_failed(brain_id, "No usable regular videos found in the channel listing.")
            return
        repo.insert_candidate_manifest(
            brain_id,
            candidates,
            selection_method=method,
            selected_url=f"{brain['normalized_url']}/videos",
            discovered_count=discovered_count,
        )

    repo.set_brain(brain_id, status="ingesting", clear_current_video=True, last_error="")
    for video in repo.get_pending_videos(brain_id):
        repo.set_brain(
            brain_id,
            status="ingesting",
            current_video_title=str(video["title"]),
        )
        repo.upsert_video_status(brain_id, str(video["video_id"]), "processing")
        try:
            _ingest_one_video(repo, brain_id, video, youtube, str(brain["language"]))
        except Exception as exc:
            if _is_rate_limited(exc):
                repo.upsert_video_status(
                    brain_id,
                    str(video["video_id"]),
                    "pending",
                    error="Paused after YouTube rate limiting; safe to resume.",
                )
                repo.set_brain(
                    brain_id,
                    status="paused",
                    last_error="YouTube rate limited ingestion (HTTP 429) after bounded retries. Create this brain again later to resume; persistent limits may require the documented cookie or proxy setting.",
                    clear_current_video=True,
                )
                return
            repo.upsert_video_status(
                brain_id,
                str(video["video_id"]),
                "failed",
                error=sanitize_error(exc),
            )

    completed = repo.get_brain_status(brain_id)
    if isinstance(completed, dict) and int(completed["indexed_count"]) > 0:
        repo.set_brain(brain_id, status="ready", clear_current_video=True, last_error="")
    else:
        repo.mark_failed(brain_id, "No videos were successfully indexed.")


def _ingest_one_video(
    repo: Repository,
    brain_id: str,
    video: dict[str, Any],
    youtube: YoutubeClientLike,
    language: str,
) -> None:
    video_id = str(video["video_id"])
    webpage_url = str(video["webpage_url"])
    metadata = youtube.extract_metadata(webpage_url)
    if metadata is None:
        repo.upsert_video_status(brain_id, video_id, "failed", error="Video metadata was unavailable.")
        return
    if metadata.get("is_live") or metadata.get("is_live_broadcast") or metadata.get("scheduled_start"):
        repo.upsert_video_status(brain_id, video_id, "skipped", error="Video is currently live or scheduled.")
        return

    selection = youtube.select_caption(metadata, language)
    if selection is None:
        repo.upsert_video_status(
            brain_id, video_id, "skipped", error="No requested-language captions are available."
        )
        return
    try:
        payload = youtube.download_caption_payload(selection)
    except CaptionDownloadError as exc:
        if exc.status_code != 403:
            raise
        # Caption URLs can expire. Refresh metadata once and retry exactly once.
        metadata = youtube.extract_metadata(webpage_url)
        if metadata is None:
            raise
        selection = youtube.select_caption(metadata, language)
        if selection is None:
            repo.upsert_video_status(
                brain_id, video_id, "skipped", error="No requested-language captions are available."
            )
            return
        payload = youtube.download_caption_payload(selection)
    if not payload.strip():
        repo.upsert_video_status(brain_id, video_id, "failed", error="Caption payload was empty.")
        return

    cues = (
        youtube.parse_json3_cues(payload)
        if selection.format == "json3"
        else youtube.parse_vtt_cues(payload)
    )
    if selection.format == "vtt" and selection.kind == "automatic":
        cues = youtube.rolling_dedup_vtt(cues)
    if not cues:
        repo.upsert_video_status(brain_id, video_id, "skipped", error="Caption payload contained no usable cues.")
        return
    chunks = youtube.merge_cues_into_chunks(cues)
    if not chunks:
        repo.upsert_video_status(brain_id, video_id, "skipped", error="Caption cues produced no chunks.")
        return

    # Preserve existing chunks until the newly downloaded caption set has parsed successfully.
    with transaction(repo.db_path) as conn:
        repo.delete_video_chunks(conn, brain_id, video_id)
        for index, chunk in enumerate(chunks):
            repo.insert_chunk(
                conn,
                brain_id=brain_id,
                video_id=video_id,
                video_title=str(video["title"]),
                chunk_index=index,
                start_ms=int(chunk["start_ms"]),
                end_ms=int(chunk["end_ms"]),
                text=str(chunk["text"]),
            )
        repo.upsert_video_status(
            brain_id,
            video_id,
            "indexed",
            conn=conn,
            caption_language=selection.language,
            caption_kind=selection.kind,
            error="",
        )


def _is_rate_limited(exc: BaseException) -> bool:
    return getattr(exc, "status_code", None) == 429 or "429" in str(exc)
