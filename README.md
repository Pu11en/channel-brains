# Channel Brains

**Channel Brains** is a local, stdio MCP server that indexes publicly available YouTube captions into a searchable SQLite FTS5 database. It runs on your computer, needs no API key, and preserves timestamped links back to the original videos.

It is deliberately small and local:

- No hosted service, Docker, browser dashboard, embeddings, or LLM runtime
- No YouTube API key, database server, or cloud account
- One local SQLite database per user, protected by a cross-process ingestion lock
- One channel ingestion job at a time, with resumable per-video progress
- Search results cite the original video and timestamp

## Install

Requires [uv](https://docs.astral.sh/uv/).

After the public v0.1.0 release, run it directly from GitHub:

```bash
uvx --from "git+https://github.com/<OWNER>/channel-brains@v0.1.0" channel-brains-mcp
```

Replace `<OWNER>` with the GitHub account that owns the published repository. The exact release URL will replace this placeholder when publishing is complete.

For development:

```bash
uv sync --extra dev
uv run channel-brains-mcp
```

The server communicates only through standard input and output. Do not run it as an HTTP service.

## First workflow

1. Add the server to an MCP client using one of the configurations below.
2. Call `create_brain` with a supported YouTube channel URL, such as `https://www.youtube.com/@OpenAI`.
3. Poll `get_brain_status` until the brain is `ready`, `paused`, or `failed`.
4. Use `search_brain` to retrieve timestamped caption matches.

The initial ingestion scans the complete channel listing so it can select up to 50 videos by view count. Caption availability and YouTube rate limits determine how much can be indexed.

## MCP tools

Channel Brains exposes exactly these six tools:

| Tool | Purpose |
| --- | --- |
| `create_brain` | Validate a channel URL, persist a brain, and start local ingestion. |
| `get_brain_status` | Read progress, counts, selection method, and errors without network access. |
| `list_brain_videos` | Page through indexed, skipped, pending, and failed video records. |
| `search_brain` | Search local FTS5 caption chunks and return timestamped YouTube citations. |
| `get_video_transcript` | Page through stored caption chunks for one indexed video. |
| `delete_brain` | Remove a completed brain and all its local records. Active ingestion is refused. |

## Local data and privacy

By default, Channel Brains stores its SQLite database and lock file in the platform’s user-data directory:

- Windows: `%LOCALAPPDATA%\channel-brains`
- macOS: `~/Library/Application Support/channel-brains`
- Linux: `~/.local/share/channel-brains`

Set `CHANNEL_BRAINS_HOME` before launching the MCP server to use another location:

```bash
CHANNEL_BRAINS_HOME=/path/to/channel-brains-data uvx --from "git+https://github.com/<OWNER>/channel-brains@v0.1.0" channel-brains-mcp
```

Captions and search indexes stay on the local machine. The only network requests are public YouTube requests made by `yt-dlp` and caption URL retrieval during ingestion.

## MCP client configuration

All examples use the release command. Substitute your real GitHub owner for `<OWNER>`.

### Hermes Agent

Add this entry under `mcp_servers` in your Hermes configuration, then restart Hermes:

```yaml
mcp_servers:
  channel_brains:
    command: uvx
    args:
      - --from
      - git+https://github.com/<OWNER>/channel-brains@v0.1.0
      - channel-brains-mcp
    timeout: 120
    connect_timeout: 60
```

Hermes discovers the six tools at startup and registers them with an `mcp_channel_brains_` prefix.

### Claude Code

Register it at user scope:

```bash
claude mcp add -s user channel-brains -- \
  uvx --from "git+https://github.com/<OWNER>/channel-brains@v0.1.0" channel-brains-mcp
```

Confirm it is available:

```bash
claude mcp list
```

### Codex CLI

Add this to `~/.codex/config.toml`:

```toml
[mcp_servers.channel-brains]
command = "uvx"
args = ["--from", "git+https://github.com/<OWNER>/channel-brains@v0.1.0", "channel-brains-mcp"]
```

Restart Codex after saving the file.

### OpenCode

Add a local MCP server entry to your OpenCode configuration:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "channel-brains": {
      "type": "local",
      "command": [
        "uvx",
        "--from",
        "git+https://github.com/<OWNER>/channel-brains@v0.1.0",
        "channel-brains-mcp"
      ],
      "enabled": true
    }
  }
}
```

Restart OpenCode to load the server.

## Development and verification

```bash
uv sync --extra dev --locked
uv run ruff check .
uv run pytest
uv build
```

The test suite is offline except for the deliberately separate manual live YouTube smoke test.

## Limitations

- Public YouTube captions can be unavailable, expired, restricted, or rate-limited.
- Search is lexical SQLite FTS5 search, not semantic search or an answer-generation system.
- The server indexes captions only. It does not download videos, reuse video footage, or create a knowledge graph.
- A channel can contain many videos. The first local ingestion may take time.

## License

MIT. See [LICENSE](LICENSE).
