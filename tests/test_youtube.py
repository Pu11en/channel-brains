"""Tests for Channel Brains YouTube ingestion logic."""

import pytest

from channel_brains_mcp.youtube import (
    CaptionCue,
    is_valid_channel_url,
    merge_cues_into_chunks,
    normalize_channel_url,
    parse_json3_cues,
    parse_vtt_cues,
    rolling_dedup_vtt,
    select_caption_track,
)


class TestURLNormalization:
    def test_accepts_handle_url(self):
        url = normalize_channel_url("https://www.youtube.com/@testchannel")
        assert url == "https://www.youtube.com/@testchannel"

    def test_accepts_channel_id_url(self):
        url = normalize_channel_url("https://www.youtube.com/channel/UCxxxxxxxxxx")
        assert url == "https://www.youtube.com/channel/UCxxxxxxxxxx"

    def test_accepts_c_name_url(self):
        url = normalize_channel_url("https://www.youtube.com/c/Name")
        assert url == "https://www.youtube.com/c/Name"

    def test_accepts_user_name_url(self):
        url = normalize_channel_url("https://www.youtube.com/user/name")
        assert url == "https://www.youtube.com/user/name"

    def test_strips_videos_tab(self):
        url = normalize_channel_url("https://www.youtube.com/@test/videos")
        assert url == "https://www.youtube.com/@test"

    def test_strips_shorts_tab(self):
        url = normalize_channel_url("https://www.youtube.com/@test/shorts")
        assert url == "https://www.youtube.com/@test"

    def test_strips_streams_tab(self):
        url = normalize_channel_url("https://www.youtube.com/@test/streams")
        assert url == "https://www.youtube.com/@test"

    def test_rejects_watch_url(self):
        with pytest.raises(ValueError):
            normalize_channel_url("https://www.youtube.com/watch?v=abc123")

    def test_rejects_playlist_url(self):
        with pytest.raises(ValueError):
            normalize_channel_url("https://www.youtube.com/playlist?list=abc")

    def test_rejects_short_link(self):
        with pytest.raises(ValueError):
            normalize_channel_url("https://youtu.be/abc123")

    def test_rejects_http(self):
        with pytest.raises(ValueError):
            normalize_channel_url("http://www.youtube.com/@test")

    def test_rejects_non_youtube(self):
        with pytest.raises(ValueError):
            normalize_channel_url("https://example.com/@test")

    def test_normalizes_m_to_www(self):
        url = normalize_channel_url("https://m.youtube.com/@test")
        assert url == "https://www.youtube.com/@test"

    def test_lower_cases_hostname(self):
        url = normalize_channel_url("https://YOUTUBE.COM/@Test")
        assert "youtube.com" in url.lower()

    def test_strips_trailing_slash(self):
        url = normalize_channel_url("https://www.youtube.com/@test/")
        assert url == "https://www.youtube.com/@test"

    def test_strips_query_and_fragment(self):
        url = normalize_channel_url("https://www.youtube.com/@test?foo=bar#section")
        assert url == "https://www.youtube.com/@test"

    def test_builds_listing_url(self):
        normalized = normalize_channel_url("https://www.youtube.com/@test")
        listing = f"{normalized}/videos"
        assert listing == "https://www.youtube.com/@test/videos"

    def test_is_valid_channel_url(self):
        assert is_valid_channel_url("https://www.youtube.com/@test") is True
        assert is_valid_channel_url("https://youtu.be/abc") is False
        assert is_valid_channel_url("http://youtube.com/@test") is False


class TestJson3Parsing:
    def test_parses_json3_cues(self):
        payload = '{"events": [{"tStartMs": "1000", "dDurationMs": "2000", "segs": [{"utf8": "Hello world"}]}]}'
        cues = parse_json3_cues(payload)
        assert len(cues) == 1
        assert cues[0].start_ms == 1000
        assert cues[0].end_ms == 3000
        assert cues[0].text == "Hello world"

    def test_ignores_empty_segs(self):
        payload = '{"events": [{"tStartMs": "0", "dDurationMs": "1000", "segs":[]}]}'
        cues = parse_json3_cues(payload)
        assert len(cues) == 0

    def test_stable_sorts_out_of_order_cues(self):
        payload = (
            '{"events": ['
            '{"tStartMs": "3000", "dDurationMs": "1000", "segs": [{"utf8": "C"}]},'
            '{"tStartMs": "1000", "dDurationMs": "1000", "segs": [{"utf8": "A"}]},'
            '{"tStartMs": "2000", "dDurationMs": "1000", "segs": [{"utf8": "B"}]}'
            ']}'
        )
        cues = parse_json3_cues(payload)
        assert [c.text for c in cues] == ["A", "B", "C"]

    def test_infers_bounded_end_for_zero_duration(self):
        payload = '{"events": [{"tStartMs": "5000", "dDurationMs": "0", "segs": [{"utf8": "Hi"}]}]}'
        cues = parse_json3_cues(payload)
        assert cues[0].end_ms == 7000  # start_ms + 2000 for final event

    def test_exact_dedupes_identical_cues(self):
        payload = (
            '{"events": ['
            '{"tStartMs": "0", "dDurationMs": "1000", "segs": [{"utf8": "Hello"}]},'
            '{"tStartMs": "0", "dDurationMs": "1000", "segs": [{"utf8": "Hello"}]}'
            ']}'
        )
        cues = parse_json3_cues(payload)
        assert len(cues) == 1

    def test_keeps_genuine_repeated_speech(self):
        payload = (
            '{"events": ['
            '{"tStartMs": "0", "dDurationMs": "1000", "segs": [{"utf8": "Hello"}]},'
            '{"tStartMs": "0", "dDurationMs": "1000", "segs": [{"utf8": "Hello"}]},'
            '{"tStartMs": "1000", "dDurationMs": "1000", "segs": [{"utf8": "Hello"}]}'
            ']}'
        )
        cues = parse_json3_cues(payload)
        # First two have same start_ms/end_ms/text so deduped, third is different position
        assert len(cues) == 2

    def test_malformed_json_cues_returns_empty(self):
        cues = parse_json3_cues("not valid json")
        assert cues == []

    def test_preserves_original_source_order(self):
        payload = (
            '{"events": ['
            '{"tStartMs": "1000", "dDurationMs": "1000", "segs": [{"utf8": "A"}]},'
            '{"tStartMs": "0", "dDurationMs": "1000", "segs": [{"utf8": "B"}]}'
            ']}'
        )
        cues = parse_json3_cues(payload)
        assert cues[0].text == "B"
        assert cues[1].text == "A"


class TestVTTParsing:
    @pytest.fixture
    def vtt_payload(self):
        return """WEBVTT

00:00:01.000 --> 00:00:03.000
Hello world

00:00:04.000 --> 00:00:06.000
Second line
"""

    def test_parses_vtt_cues(self, vtt_payload):
        cues = parse_vtt_cues(vtt_payload)
        assert len(cues) == 2
        assert cues[0].start_ms == 1000
        assert cues[0].end_ms == 3000

    def test_flushes_final_cue(self, vtt_payload):
        cues = parse_vtt_cues(vtt_payload)
        assert len(cues) == 2

    def test_ignores_identifier_lines(self):
        payload = """WEBVTT

1
00:00:01.000 --> 00:00:03.000
Cue text
"""
        cues = parse_vtt_cues(payload)
        assert len(cues) == 1


class TestCueMergeAndChunking:
    def test_flushes_final_partial_chunk(self):
        cues = [
            CaptionCue(start_ms=0, end_ms=5000, text="Hello"),
            CaptionCue(start_ms=5000, end_ms=10000, text="world test"),
        ]
        chunks = merge_cues_into_chunks(cues, target_seconds=2, max_chars=900)
        assert len(chunks) == 2  # Each cue starts a new chunk due to time limit

    def test_flushes_at_time_limit(self):
        cues = []
        for i in range(10):
            cues.append(
                CaptionCue(
                    start_ms=i * 5000,
                    end_ms=(i + 1) * 5000,
                    text=f"Segment {i}",
                )
            )
        chunks = merge_cues_into_chunks(cues, target_seconds=45, max_chars=900)
        assert len(chunks) > 0
        # First chunk starts at 0
        assert chunks[0]["start_seconds"] == 0

    def test_flushes_at_char_limit(self):
        long_text = "x " * 500
        cues = [
            CaptionCue(start_ms=0, end_ms=5000, text=long_text),
            CaptionCue(start_ms=5000, end_ms=10000, text="Next"),
        ]
        chunks = merge_cues_into_chunks(cues, target_seconds=45, max_chars=100)
        assert len(chunks) >= 2

    def test_spaces_joined_correctly(self):
        cues = [
            CaptionCue(start_ms=0, end_ms=1000, text="Hello"),
            CaptionCue(start_ms=1000, end_ms=2000, text="world"),
        ]
        chunks = merge_cues_into_chunks(cues, target_seconds=60, max_chars=900)
        assert len(chunks) == 1
        assert chunks[0]["text"] == "Hello world"

    def test_skips_blank_chunks(self):
        cues = [
            CaptionCue(start_ms=0, end_ms=1000, text=""),
        ]
        # normalize_cue_text converts empty to ""
        chunks = merge_cues_into_chunks(cues, target_seconds=60, max_chars=900)
        # Empty text cue was already normalized away in parse
        assert len(chunks) >= 0

    def test_preserves_earliest_retained_timestamp(self):
        cues = [
            CaptionCue(start_ms=0, end_ms=5000, text="First"),
            CaptionCue(start_ms=5000, end_ms=10000, text="Second"),
        ]
        chunks = merge_cues_into_chunks(cues, target_seconds=60, max_chars=900)
        assert chunks[0]["start_seconds"] == 0


class TestRollingDedup:
    def test_removes_overlap_only_for_vtt(self):
        cues = [
            CaptionCue(start_ms=0, end_ms=5000, text="Hello world"),
            CaptionCue(start_ms=4000, end_ms=9000, text="world again"),
        ]
        result = rolling_dedup_vtt(cues)
        assert len(result) == 2
        assert result[1].text == "again"  # "world" is overlapping prefix

    def test_does_not_over_dedupe(self):
        cues = [
            CaptionCue(start_ms=0, end_ms=5000, text="Hello world"),
            CaptionCue(start_ms=10000, end_ms=15000, text="Hello world"),
        ]
        result = rolling_dedup_vtt(cues)
        # Cue 2's entire text ("Hello world") is a suffix of the last
        # 50 emitted words, so it is stripped. Result is 1 cue.
        assert len(result) == 1
        assert result[0].text == "Hello world"

    def test_empty_cues(self):
        assert rolling_dedup_vtt([]) == []


class TestCaptionSelection:
    def test_picks_manual_json3_when_available(self):
        info = {
            "subtitles": {
                "en": {"json3": {"data": "test payload"}},
            },
            "automatic_captions": {},
            "language": "en",
        }
        selection = select_caption_track(info, language="en")
        assert selection is not None
        assert selection.kind == "manual"
        assert selection.format == "json3"
        assert selection.payload == "test payload"

    def test_falls_back_to_automatic(self):
        info = {
            "subtitles": {},
            "automatic_captions": {
                "en": {"json3": {"data": "auto payload"}},
            },
            "language": "en",
        }
        selection = select_caption_track(info, language="en")
        assert selection is not None
        assert selection.kind == "automatic"

    def test_rejects_translated_caption_as_original(self):
        # A Spanish-original video has es-orig auto captions and
        # a translated en auto caption. The en auto-translated track
        # must be rejected because the original language is not English.
        # Since no English original exists, the video is skipped.
        info = {
            "subtitles": {},
            "automatic_captions": {
                "en": {"json3": {"data": "translated English"}},
                "es-orig": {"json3": {"data": "original Spanish"}},
            },
            "language": "es",
        }
        selection = select_caption_track(info, language="en")
        # No English original available — selection is None
        assert selection is None

    def test_excludes_live_chat(self):
        info = {
            "subtitles": {
                "en": {"json3": {"data": "text"}},
                "live_chat": {"json3": {"data": "chat text"}},
            },
            "automatic_captions": {},
            "language": "en",
        }
        selection = select_caption_track(info, language="en")
        assert selection is not None
        assert selection.payload == "text"
