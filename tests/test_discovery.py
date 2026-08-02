"""Focused offline tests for complete-listing candidate selection."""

from __future__ import annotations

from channel_brains_mcp.youtube import select_channel_candidates


def _entry(video_id: str, views: int | None, **extra: object) -> dict[str, object]:
    return {
        "id": video_id,
        "title": f"Title {video_id}",
        "webpage_url": f"https://www.youtube.com/watch?v={video_id}",
        "view_count": views,
        **extra,
    }


def test_sorts_complete_listing_by_descending_view_count_with_stable_ties() -> None:
    entries = [
        _entry("latest", 5),
        _entry("popular-first", 100),
        _entry("popular-tie", 100),
        _entry("middle", 50),
    ]

    selected, discovered_count, method = select_channel_candidates(entries, max_videos=3)

    assert discovered_count == 4
    assert method == "view_count"
    assert [row["video_id"] for row in selected] == ["popular-first", "popular-tie", "middle"]
    assert [row["position"] for row in selected] == [1, 2, 3]


def test_places_missing_count_entries_after_known_counts() -> None:
    entries = [_entry("missing-new", None), _entry("known", 7), _entry("missing-old", None)]

    selected, discovered_count, method = select_channel_candidates(entries, max_videos=50)

    assert discovered_count == 3
    assert method == "view_count_partial"
    assert [row["video_id"] for row in selected] == ["known", "missing-new", "missing-old"]


def test_uses_latest_order_only_when_every_usable_entry_lacks_view_count() -> None:
    entries = [_entry("latest", None), _entry("older", None), _entry("oldest", None)]

    selected, discovered_count, method = select_channel_candidates(entries, max_videos=2)

    assert discovered_count == 3
    assert method == "latest_fallback"
    assert [row["video_id"] for row in selected] == ["latest", "older"]


def test_reads_all_lazy_entries_before_selecting_and_deduplicates_video_ids() -> None:
    consumed: list[str] = []

    def listing():
        for item in [_entry("one", 1), _entry("one", 999), _entry("two", 10), _entry("live", 500, is_live=True)]:
            consumed.append(str(item["id"]))
            yield item

    selected, discovered_count, method = select_channel_candidates(listing(), max_videos=50)

    assert consumed == ["one", "one", "two", "live"]
    assert discovered_count == 2
    assert method == "view_count"
    assert [row["video_id"] for row in selected] == ["two", "one"]


def test_missing_listing_url_uses_canonical_watch_url_without_redirect() -> None:
    selected, _, _ = select_channel_candidates(
        [{"id": "abc123xyz00", "title": "Video", "view_count": 1}],
        max_videos=1,
    )

    assert selected[0]["webpage_url"] == "https://www.youtube.com/watch?v=abc123xyz00"
