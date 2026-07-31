"""YouTube discovery, caption selection, and parsing with yt-dlp integration."""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable
from dataclasses import dataclass
from html import unescape
from io import StringIO

import yt_dlp

logger = logging.getLogger(__name__)


# --- URL helpers ---

_TERMINAL_TAB_RE = re.compile(r"/(videos|shorts|streams)$")
_YOUTUBE_HOSTS = ("www.youtube.com", "youtube.com", "m.youtube.com")


def normalize_channel_url(url: str) -> str:
    """Validate and canonicalize an accepted HTTPS YouTube channel URL."""
    if not isinstance(url, str) or not url.strip():
        raise ValueError("URL must be a non-empty string")
    parsed = urllib.parse.urlparse(url.strip())
    hostname = (parsed.hostname or "").lower()
    if parsed.scheme != "https":
        raise ValueError("Only HTTPS YouTube URLs are accepted")
    if hostname not in _YOUTUBE_HOSTS:
        raise ValueError("Not a supported YouTube channel URL")

    path = re.sub(r"/+", "/", parsed.path).rstrip("/")
    path = _TERMINAL_TAB_RE.sub("", path)
    if not (
        re.fullmatch(r"/@[^/]+", path)
        or re.fullmatch(r"/channel/UC[^/]+", path)
        or re.fullmatch(r"/c/[^/]+", path)
        or re.fullmatch(r"/user/[^/]+", path)
    ):
        raise ValueError("Use a YouTube /@handle, /channel/UC..., /c/name, or /user/name URL")
    return f"https://www.youtube.com{path}"


def build_listing_url(normalized_url: str) -> str:
    return f"{normalized_url}/videos"


def select_channel_candidates(
    entries: Iterable[dict[str, object]], max_videos: int
) -> tuple[list[dict[str, object]], int, str]:
    """Read a full regular-video listing and choose its top candidates locally.

    Each usable ID is considered once at its first listing position. Videos with known
    integer view counts rank first, descending, with original listing order breaking
    ties. Missing counts use latest-first order only after known rows. The dedicated
    latest fallback is used solely when no usable row reported a count.
    """
    if not 1 <= max_videos <= 50:
        raise ValueError("max_videos must be between 1 and 50")
    usable: list[dict[str, object]] = []
    seen_ids: set[str] = set()
    for listing_position, entry in enumerate(entries, start=1):
        video_id = entry.get("video_id") or entry.get("id")
        if not isinstance(video_id, str) or not video_id or video_id in seen_ids:
            continue
        seen_ids.add(video_id)
        if entry.get("is_live") or entry.get("is_live_broadcast") or entry.get("scheduled_start"):
            continue
        view_count = entry.get("view_count")
        known_view_count = view_count if isinstance(view_count, int) and not isinstance(view_count, bool) and view_count >= 0 else None
        usable.append(
            {
                "video_id": video_id,
                "title": str(entry.get("title") or "Untitled")[:200],
                "webpage_url": str(entry.get("webpage_url") or f"https://youtu.be/{video_id}"),
                "duration_seconds": entry.get("duration_seconds", entry.get("duration")),
                "view_count": known_view_count,
                "upload_date": entry.get("upload_date"),
                "_listing_position": listing_position,
            }
        )

    discovered_count = len(usable)
    known = [row for row in usable if row["view_count"] is not None]
    if not known:
        ordered = usable
        method = "latest_fallback"
    else:
        ordered = sorted(
            usable,
            key=lambda row: (
                0 if row["view_count"] is not None else 1,
                -int(row["view_count"]) if row["view_count"] is not None else 0,
                int(row["_listing_position"]),
            ),
        )
        method = "view_count" if len(known) == len(usable) else "view_count_partial"

    selected: list[dict[str, object]] = []
    for position, row in enumerate(ordered[:max_videos], start=1):
        selected.append({key: value for key, value in row.items() if key != "_listing_position"} | {"position": position})
    return selected, discovered_count, method


def is_valid_channel_url(url: str) -> bool:
    try:
        normalize_channel_url(url)
        return True
    except (ValueError, TypeError):
        return False


# --- Caption text helpers ---


def html_unescape_text(text: str) -> str:
    return unescape(text)


def remove_markup(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text)


def normalize_cue_text(text: str) -> str:
    text = html_unescape_text(text)
    text = remove_markup(text)
    text = text.replace("\n", " ").replace("\r", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


@dataclass
class CaptionCue:
    start_ms: int
    end_ms: int
    text: str


def parse_json3_cues(payload: str) -> list[CaptionCue]:
    try:
        data = json.loads(payload)
    except (json.JSONDecodeError, TypeError):
        return []

    events = data.get("events", [])
    cues: list[CaptionCue] = []
    for evt in events:
        segs = evt.get("segs")
        if not segs:
            continue
        start_ms = int(evt.get("tStartMs", 0))
        dur_ms = int(evt.get("dDurationMs", 0))
        text = "".join(seg.get("utf8", "") for seg in segs)
        text = normalize_cue_text(text)
        if not text:
            continue
        cues.append(CaptionCue(start_ms=start_ms, end_ms=start_ms + dur_ms, text=text))

    # Stable sort by (start_ms, original_index) — enumerate preserves insertion order for ties
    # Since we built cues in original order and sort is stable, sorting by start_ms alone preserves order
    cues.sort(key=lambda c: c.start_ms)

    # Exact-deduplicate identical (start_ms, end_ms, text)
    seen: set[tuple[int, int, str]] = set()
    deduped: list[CaptionCue] = []
    for cue in cues:
        key = (cue.start_ms, cue.end_ms, cue.text)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(cue)

    # Infer bounded end times for zero-duration events
    for i, cue in enumerate(deduped):
        if cue.end_ms - cue.start_ms <= 0:
            if i + 1 < len(deduped):
                cue.end_ms = min(deduped[i + 1].start_ms, cue.start_ms + 10_000)
            else:
                cue.end_ms = cue.start_ms + 2_000

    return deduped


def parse_vtt_cues(payload: str) -> list[CaptionCue]:
    import webvtt

    cues: list[CaptionCue] = []
    try:
        vtt = webvtt.from_buffer(StringIO(payload))
    except Exception as exc:
        logger.warning("VTT parse failed: %s", exc)
        return []

    for cue in vtt.captions:
        start_match = re.match(r"(\d+):(\d+):(\d+)\.?(\d*)", cue.start)
        end_match = re.match(r"(\d+):(\d+):(\d+)\.?(\d*)", cue.end)
        if not start_match or not end_match:
            continue

        def _to_ms(m: re.Match) -> int:
            h, mi, s = int(m.group(1)), int(m.group(2)), int(m.group(3))
            ms_frac = m.group(4)
            ms = int(ms_frac.ljust(3, "0")[:3]) if ms_frac else 0
            return h * 3600_000 + mi * 60_000 + s * 1000 + ms

        start_ms_val = _to_ms(start_match)
        end_ms_val = _to_ms(end_match)
        text = normalize_cue_text(cue.text)
        if not text:
            continue
        cues.append(CaptionCue(start_ms=start_ms_val, end_ms=end_ms_val, text=text))

    return cues


def merge_cues_into_chunks(
    cues: list[CaptionCue],
    target_seconds: int = 45,
    max_chars: int = 900,
) -> list[dict[str, object]]:
    chunks: list[dict[str, object]] = []
    if not cues:
        return chunks

    current_start_ms = cues[0].start_ms
    current_end_ms = cues[0].end_ms
    combined_text = cues[0].text
    current_cues = [cues[0]]

    def flush_chunk() -> None:
        nonlocal current_cues, current_start_ms, current_end_ms, combined_text
        if not current_cues:
            return
        start_seconds = current_start_ms // 1000
        end_seconds = current_end_ms // 1000
        chunks.append(
            {
                "start_ms": current_start_ms,
                "end_ms": current_end_ms,
                "start_seconds": start_seconds,
                "end_seconds": end_seconds,
                "text": combined_text,
            }
        )
        current_cues = []
        combined_text = ""

    for cue in cues[1:]:
        elapsed = (cue.start_ms - current_start_ms) / 1000.0
        would_exceed_time = elapsed >= target_seconds
        would_exceed_chars = (len(combined_text) + len(cue.text) + 1) > max_chars

        if current_cues and (would_exceed_time or would_exceed_chars):
            flush_chunk()
            current_start_ms = cue.start_ms
            current_end_ms = cue.end_ms
            combined_text = cue.text
            current_cues = [cue]
        else:
            current_cues.append(cue)
            current_end_ms = max(current_end_ms, cue.end_ms)
            combined_text = (combined_text + " " + cue.text).strip() if combined_text else cue.text

    flush_chunk()
    return chunks


def rolling_dedup_vtt(cues: list[CaptionCue]) -> list[CaptionCue]:
    if not cues:
        return cues
    result: list[CaptionCue] = [cues[0]]
    recent_words: list[str] = cues[0].text.split()[:50]

    for cue in cues[1:]:
        cue_words = cue.text.split()
        overlap = 0
        for n in range(min(30, len(recent_words), len(cue_words)), 0, -1):
            if recent_words[-n:] == cue_words[:n]:
                overlap = n
                break
        remaining = cue_words[overlap:]
        if not remaining:
            continue
        new_cue = CaptionCue(
            start_ms=cue.start_ms,
            end_ms=cue.end_ms,
            text=" ".join(remaining),
        )
        result.append(new_cue)
        recent_words = (recent_words + remaining)[-50:]

    return result


@dataclass
class CaptionSelection:
    language: str
    kind: str  # 'manual' or 'automatic'
    format: str  # 'json3' or 'vtt'
    payload: str
    original_language: str | None = None


def select_caption_track(
    info: dict[str, object],
    language: str = "en",
) -> CaptionSelection | None:
    """Select a requested-language caption track without accepting translation fallbacks."""
    requested = language.lower()
    primary = requested.split("-", 1)[0]
    subtitles = _caption_mapping(info.get("subtitles"))
    automatic = _caption_mapping(info.get("automatic_captions"))

    # Manual captions may use a regional language key. Exact match wins, then variants.
    for key in _matching_language_keys(subtitles, requested, primary, original_only=False):
        selection = _selection_from_tracks(subtitles[key], requested, "manual")
        if selection is not None:
            return selection

    # Automatic captions: original-language keys are safe, and outrank plain keys.
    for key in _matching_language_keys(automatic, requested, primary, original_only=True):
        selection = _selection_from_tracks(automatic[key], requested, "automatic")
        if selection is not None:
            return selection

    # A plain auto key is safe only when metadata says the video's original language matches.
    original_language = str(info.get("language") or "").lower().split("-", 1)[0]
    if original_language != primary:
        return None
    for key in _matching_language_keys(automatic, requested, primary, original_only=False):
        selection = _selection_from_tracks(automatic[key], requested, "automatic")
        if selection is not None:
            return selection
    return None


def _caption_mapping(value: object) -> dict[str, object]:
    return {str(key): track for key, track in value.items()} if isinstance(value, dict) else {}


def _matching_language_keys(
    tracks: dict[str, object], requested: str, primary: str, *, original_only: bool
) -> list[str]:
    candidates: list[tuple[int, str]] = []
    for key in tracks:
        normalized = key.lower()
        if "live_chat" in normalized:
            continue
        is_original = normalized.endswith("-orig")
        base = normalized[:-5] if is_original else normalized
        if original_only != is_original:
            continue
        if base == requested:
            candidates.append((0, key))
        elif base == primary or base.startswith(f"{primary}-"):
            candidates.append((1, key))
    return [key for _, key in sorted(candidates, key=lambda item: (item[0], item[1].lower()))]


def _selection_from_tracks(track_data: object, language: str, kind: str) -> CaptionSelection | None:
    for format_name in ("json3", "vtt"):
        payload = _payload_for_format(track_data, format_name)
        if payload:
            return CaptionSelection(language=language, kind=kind, format=format_name, payload=payload)
    return None


def _payload_for_format(track_data: object, format_name: str) -> str:
    if isinstance(track_data, str):
        return track_data if format_name == "json3" else ""
    if isinstance(track_data, list):
        for row in track_data:
            if isinstance(row, dict) and str(row.get("ext") or "").lower() == format_name:
                payload = _extract_payload(row)
                if payload:
                    return payload
        return ""
    if not isinstance(track_data, dict):
        return ""
    value = track_data.get(format_name)
    if value is not None:
        return _extract_payload(value)
    if str(track_data.get("ext") or "").lower() == format_name:
        return _extract_payload(track_data)
    return ""


def _extract_payload(track_data: object) -> str:
    if isinstance(track_data, list):
        for item in track_data:
            payload = _extract_payload(item)
            if payload:
                return payload
        return ""
    if isinstance(track_data, dict):
        payload = track_data.get("data") or track_data.get("url") or ""
        return str(payload) if payload else ""
    return str(track_data) if isinstance(track_data, str) else ""


def extract_video_info_dict(info: dict[str, object]) -> dict[str, object]:
    return {
        "title": str(info.get("title", "")),
        "duration": info.get("duration"),
        "view_count": info.get("view_count"),
        "upload_date": info.get("upload_date"),
        "webpage_url": str(info.get("webpage_url", "")),
        "channel_id": info.get("channel_id"),
        "channel": str(info.get("channel", "")),
        "language": info.get("language"),
        "is_live": bool(info.get("is_live", False)),
        "is_live_broadcast": bool(info.get("is_live_broadcast", False)),
        "is_live_stream": bool(info.get("is_live_stream", False)),
        "scheduled_start": info.get("scheduled_start"),
        "availability": info.get("availability"),
        "subtitles": info.get("subtitles") or {},
        "automatic_captions": info.get("automatic_captions") or {},
    }


class CaptionDownloadError(RuntimeError):
    """Caption URL retrieval failed; status_code is safe for retry policy."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class YoutubeClient:
    """Production yt-dlp adapter for YouTube channel operations."""

    def __init__(self) -> None:
        self._ydl_opts: dict[str, object] = {
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "skip_download": True,
            "extract_flat": "in_playlist",
            "lazy_playlist": False,
            "ignoreerrors": False,
            "socket_timeout": 20,
            "retries": 3,
            "extractor_retries": 3,
        }
        self._logger = _YtdlLogger()

    def extract_listing(self, normalized_url: str) -> list[dict[str, object]]:
        listing_url = build_listing_url(normalized_url)
        ydl_opts = {**self._ydl_opts, "logger": self._logger}

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(listing_url, download=False)

        entries = result.get("entries", []) if isinstance(result, dict) else []
        # Exhaust the complete listing before selection. Ranking belongs in the pure helper
        # so missing counts and stable ties are handled identically in tests and production.
        return [dict(entry) for entry in entries if isinstance(entry, dict)]

    def extract_metadata(self, webpage_url: str) -> dict[str, object] | None:
        ydl_opts: dict[str, object] = {
            **self._ydl_opts,
            "logger": self._logger,
            "extract_flat": False,
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(webpage_url, download=False)
            return extract_video_info_dict(info) if info else None
        except yt_dlp.utils.DownloadError as exc:
            logger.warning("Metadata extraction failed for %s: %s", webpage_url, exc)
            return None

    def download_caption_payload(self, selection: CaptionSelection) -> str:
        """Fetch a yt-dlp caption URL, or return fixture text supplied by a test double."""
        if not selection.payload.startswith(("https://", "http://")):
            return selection.payload
        request = urllib.request.Request(
            selection.payload,
            headers={"User-Agent": "Mozilla/5.0 (compatible; ChannelBrains/0.1)"},
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            raise CaptionDownloadError(f"Caption download returned HTTP {exc.code}", exc.code) from exc
        except urllib.error.URLError as exc:
            raise CaptionDownloadError("Caption download failed") from exc

    def select_caption(
        self, info: dict[str, object], language: str
    ) -> CaptionSelection | None:
        return select_caption_track(info, language)

    @staticmethod
    def parse_json3_cues(payload: str) -> list[CaptionCue]:
        return parse_json3_cues(payload)

    @staticmethod
    def parse_vtt_cues(payload: str) -> list[CaptionCue]:
        return parse_vtt_cues(payload)

    @staticmethod
    def rolling_dedup_vtt(cues: list[CaptionCue]) -> list[CaptionCue]:
        return rolling_dedup_vtt(cues)

    @staticmethod
    def merge_cues_into_chunks(cues: list[CaptionCue]) -> list[dict[str, object]]:
        return merge_cues_into_chunks(cues)


class _YtdlLogger:
    """Forward yt-dlp log messages to Python logging via stderr only."""

    def debug(self, msg: str) -> None:
        logger.debug(msg)

    def warning(self, msg: str) -> None:
        logger.warning(msg)

    def error(self, msg: str) -> None:
        logger.error(msg)

    def report_warning(self, msg: str) -> None:
        logger.warning(msg)

    def report_error(self, msg: str) -> None:
        logger.error(msg)