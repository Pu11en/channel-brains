"""Pydantic output models for the six MCP tools."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CreateBrainResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    brain_id: str
    status: str
    normalized_url: str
    max_videos: int
    language: str
    queued: bool
    monitoring_required: bool = False
    monitoring_instruction: str | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    message: str


class BrainStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    brain_id: str
    normalized_url: str
    channel_name: str | None = None
    status: str
    selection_method: str | None = None
    discovered_count: int
    candidate_count: int
    pending_count: int
    processing_count: int
    indexed_count: int
    skipped_count: int
    failed_count: int
    chunk_count: int
    current_video_title: str | None = None
    last_error: str | None = None
    created_at: str
    updated_at: str


class BrainStatusResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    brains: list[BrainStatus]
    count: int
    waited: bool = Field(default=False, exclude_if=lambda value: not value)
    terminal: bool = Field(default=False, exclude_if=lambda value: not value)
    timed_out: bool = Field(default=False, exclude_if=lambda value: not value)


class VideoSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    position: int
    video_id: str
    title: str
    url: str
    view_count: int | None = None
    status: str
    caption_language: str | None = None
    caption_source: str | None = None
    error: str | None = None


class VideoListResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    brain_id: str
    offset: int
    limit: int
    total: int
    next_offset: int | None = None
    videos: list[VideoSummary]


class SearchHit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rank: int
    brain_id: str
    brain_name: str
    video_id: str
    video_title: str
    upload_date: str
    start_seconds: int
    end_seconds: int
    timestamp: str
    url: str
    text: str


class SearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    brain_id: str | None = None
    brain_statuses: list[BrainStatus]
    results: list[SearchHit]
    presentation_instruction: str
    untrusted_content_warning: str


class TranscriptChunk(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_index: int
    start_seconds: int
    end_seconds: int
    timestamp: str
    url: str
    text: str


class TranscriptResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    brain_id: str
    video_id: str
    video_title: str
    offset: int
    limit: int
    total: int
    next_offset: int | None = None
    chunks: list[TranscriptChunk]
    untrusted_content_warning: str


class DeleteBrainResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    brain_id: str
    deleted: bool
    deleted_video_count: int
    deleted_chunk_count: int
    message: str
