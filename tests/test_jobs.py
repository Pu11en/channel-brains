"""Offline fixture-driven ingestion integration tests."""

from __future__ import annotations

from pathlib import Path

from channel_brains_mcp.db import Repository, initialize_database
from channel_brains_mcp.jobs import ingest_brain
from channel_brains_mcp.youtube import (
    CaptionDownloadError,
    CaptionSelection,
    merge_cues_into_chunks,
    parse_json3_cues,
    parse_vtt_cues,
    rolling_dedup_vtt,
    select_caption_track,
)


class FixtureYoutube:
    """A deterministic YouTube adapter with no network access."""

    def __init__(self) -> None:
        self.metadata_calls: list[str] = []

    def extract_listing(self, normalized_url: str) -> list[dict[str, object]]:
        assert normalized_url == "https://www.youtube.com/@fixture"
        return [
            {"id": "manual01", "title": "Manual video", "webpage_url": "https://youtu.be/manual01", "view_count": 40},
            {"id": "auto0001", "title": "Automatic video", "webpage_url": "https://youtu.be/auto0001", "view_count": 30},
            {"id": "skip0001", "title": "No captions", "webpage_url": "https://youtu.be/skip0001", "view_count": 20},
            {"id": "fail0001", "title": "Unavailable", "webpage_url": "https://youtu.be/fail0001", "view_count": 10},
        ]

    def extract_metadata(self, webpage_url: str) -> dict[str, object] | None:
        self.metadata_calls.append(webpage_url)
        if webpage_url.endswith("fail0001"):
            return None
        if webpage_url.endswith("skip0001"):
            return {"subtitles": {}, "automatic_captions": {}, "language": "en"}
        if webpage_url.endswith("manual01"):
            return {
                "language": "en",
                "subtitles": {
                    "en": {
                        "json3": {
                            "data": '{"events":[{"tStartMs":"12000","dDurationMs":"4000","segs":[{"utf8":"Manual evidence about pricing."}]}]}'
                        }
                    }
                },
                "automatic_captions": {},
            }
        return {
            "language": "en",
            "subtitles": {},
            "automatic_captions": {
                "en-orig": {
                    "vtt": {
                        "data": "WEBVTT\n\n00:00:01.000 --> 00:00:03.000\nrolling words here\n\n00:00:03.000 --> 00:00:05.000\nwords here remain\n"
                    }
                }
            },
        }

    def select_caption(self, info: dict[str, object], language: str):
        return select_caption_track(info, language)

    def download_caption_payload(self, selection: CaptionSelection) -> str:
        return selection.payload

    def parse_json3_cues(self, payload: str):
        return parse_json3_cues(payload)

    def parse_vtt_cues(self, payload: str):
        return parse_vtt_cues(payload)

    def rolling_dedup_vtt(self, cues):
        return rolling_dedup_vtt(cues)

    def merge_cues_into_chunks(self, cues):
        return merge_cues_into_chunks(cues)


def test_fixture_ingest_indexes_captions_skips_missing_and_does_not_duplicate(tmp_path: Path) -> None:
    db_path = tmp_path / "channel_brains.sqlite3"
    initialize_database(db_path)
    repo = Repository(db_path)
    brain_id = "a0b1c2d3e4f5"
    repo.create_brain(
        brain_id,
        "https://www.youtube.com/@fixture",
        "https://www.youtube.com/@fixture",
        None,
        "Fixture channel",
        "en",
        4,
    )
    youtube = FixtureYoutube()

    ingest_brain(repo, brain_id, youtube)

    status = repo.get_brain_status(brain_id)
    assert status["status"] == "ready"
    assert status["indexed_count"] == 2
    assert status["skipped_count"] == 1
    assert status["failed_count"] == 1
    assert status["chunk_count"] == 2
    assert repo.search_chunks("pricing", ["pricing"], brain_id=brain_id)[0]["video_id"] == "manual01"

    # Explicit resume/re-ingest retains exactly one atomic chunk set per video.
    ingest_brain(repo, brain_id, youtube)
    assert repo.get_brain_status(brain_id)["chunk_count"] == 2


def test_rate_limit_pauses_discovery_instead_of_failing(tmp_path: Path) -> None:
    class RateLimitedYoutube(FixtureYoutube):
        def extract_listing(self, normalized_url: str) -> list[dict[str, object]]:
            raise CaptionDownloadError("listing rate limited", 429)

    db_path = tmp_path / "channel_brains.sqlite3"
    initialize_database(db_path)
    repo = Repository(db_path)
    brain_id = "b0b1c2d3e4f5"
    repo.create_brain(brain_id, "https://www.youtube.com/@fixture", "https://www.youtube.com/@fixture", None, None, "en", 1)

    ingest_brain(repo, brain_id, RateLimitedYoutube())

    status = repo.get_brain_status(brain_id)
    assert status["status"] == "paused"
    assert "429" in status["last_error"]


def test_expired_caption_url_refreshes_metadata_exactly_once(tmp_path: Path) -> None:
    class RefreshingYoutube(FixtureYoutube):
        def __init__(self) -> None:
            super().__init__()
            self.download_attempts = 0

        def extract_listing(self, normalized_url: str) -> list[dict[str, object]]:
            return [{"id": "manual01", "title": "Manual", "webpage_url": "https://youtu.be/manual01", "view_count": 1}]

        def download_caption_payload(self, selection: object) -> str:
            self.download_attempts += 1
            if self.download_attempts == 1:
                raise CaptionDownloadError("expired", 403)
            return super().download_caption_payload(selection)

    db_path = tmp_path / "channel_brains.sqlite3"
    initialize_database(db_path)
    repo = Repository(db_path)
    brain_id = "c0b1c2d3e4f5"
    repo.create_brain(brain_id, "https://www.youtube.com/@fixture", "https://www.youtube.com/@fixture", None, None, "en", 1)
    youtube = RefreshingYoutube()

    ingest_brain(repo, brain_id, youtube)

    assert youtube.download_attempts == 2
    assert youtube.metadata_calls == ["https://youtu.be/manual01", "https://youtu.be/manual01"]
    assert repo.get_brain_status(brain_id)["indexed_count"] == 1
