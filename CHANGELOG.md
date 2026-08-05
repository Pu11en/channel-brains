# Changelog

All notable changes to Channel Brains are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.4] - 2026-08-03

### Added
- Plugin-owned indexing monitoring: after an explicit indexing request, the agent
  makes one owned wait for completion instead of asking the user to check progress. ([#5](https://github.com/Pu11en/channel-brains/pull/5))
- Same-session command bridge so the install task stays usable when a client freezes
  the current task's MCP tool inventory. ([#2](https://github.com/Pu11en/channel-brains/pull/2))

### Changed
- Plugin upgrades are now idempotent — re-running install on an existing setup is safe. ([#4](https://github.com/Pu11en/channel-brains/pull/4))

## [0.1.3] - 2026-08-02

### Added
- Plugin-owned indexing wait so progress reporting happens within the same task. ([#3](https://github.com/Pu11en/channel-brains/pull/3))
- Automated one-line installation and same-session use. ([#2](https://github.com/Pu11en/channel-brains/pull/2))

## [0.1.2] - 2026-08-02

### Added
- Plugin-first installation across ZCode, Claude Code, and Codex client plugins,
  plus a Hermes adapter. ([#1](https://github.com/Pu11en/channel-brains/pull/1))

## [0.1.1] - 2026-08-02

### Changed
- Hardened the MCP release and agent installation flow.

## [0.1.0] - 2026-07-30

### Added
- Initial release of the Channel Brains MCP server.
- Six tools: `create_brain`, `get_brain_status`, `list_brain_videos`, `search_brain`,
  `get_video_transcript`, `delete_brain`.
- Local SQLite FTS5 caption index with timestamped YouTube citations.
- Resumable per-video ingestion with a cross-process lock.
- Offline test suite plus a manual live-YouTube release gate.
- CI across Python 3.10–3.14 on Linux, macOS, and Windows.

[0.1.4]: https://github.com/Pu11en/channel-brains/releases/tag/v0.1.4
[0.1.3]: https://github.com/Pu11en/channel-brains/releases/tag/v0.1.3
[0.1.2]: https://github.com/Pu11en/channel-brains/releases/tag/v0.1.2
[0.1.1]: https://github.com/Pu11en/channel-brains/releases/tag/v0.1.1
[0.1.0]: https://github.com/Pu11en/channel-brains/releases/tag/v0.1.0
