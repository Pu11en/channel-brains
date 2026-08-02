# Channel Brains

**Channel Brains** is a local, stdio MCP server that indexes publicly available YouTube captions into a searchable SQLite FTS5 database. It runs on your computer, needs no API key, and preserves timestamped links back to the original videos.

It is deliberately small and local:

- No hosted service, Docker, browser dashboard, embeddings, or LLM runtime
- No YouTube API key, database server, or cloud account
- One local SQLite database per user, protected by a cross-process ingestion lock
- One channel ingestion job at a time, with resumable per-video progress
- Search results cite the original video and timestamp

## Install with your AI agent

Send this single message to Codex, Claude Code, Hermes Agent, or ZCode:

> Install this MCP into yourself: https://github.com/Pu11en/channel-brains

That is the entire beginner installation flow. The agent should read
[`AGENT_INSTALL.md`](AGENT_INSTALL.md), detect which supported client it is running
inside, install the prerequisite if needed, run the offline health check, add the
user-scoped stdio server, and verify that all six tools are available.

The agent needs permission to run terminal commands and edit its local MCP
configuration. A web-only chat that cannot access your computer cannot install a
local MCP server. If the client cannot reload MCP servers while it is running, the
agent will finish the configuration and ask you to reopen the client once.

## Manual install

Requires [uv](https://docs.astral.sh/uv/).

MCP clients launch the pinned production release with:

```bash
uvx --from "git+https://github.com/Pu11en/channel-brains@v0.1.1" channel-brains-mcp
```

Verify the installation without starting the MCP server or contacting YouTube:

```bash
uvx --from "git+https://github.com/Pu11en/channel-brains@v0.1.1" channel-brains-mcp --check
```

A successful check prints one JSON object with `"status": "ok"`, `"transport":
"stdio"`, and `"tool_count": 6`.

Running the command without `--check` in a terminal intentionally waits for MCP
messages on stdin. Your MCP client owns that process.

The release is published from [`Pu11en/channel-brains`](https://github.com/Pu11en/channel-brains).

For development:

```bash
uv sync --extra dev
uv run channel-brains-mcp --check
```

The server communicates only through standard input and output. Do not run it as an HTTP service.

## Agent server definition

The automated agent flow is defined in [`AGENT_INSTALL.md`](AGENT_INSTALL.md). The
generic server definition used by that flow is:

```json
{
  "command": "uvx",
  "args": [
    "--from",
    "git+https://github.com/Pu11en/channel-brains@v0.1.1",
    "channel-brains-mcp"
  ]
}
```

Use a startup/connect timeout of at least 60 seconds. The first `uvx` run downloads
the pinned package and can be slower than later starts.

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

- Windows: `%LOCALAPPDATA%\channel-brains-mcp`
- macOS: `~/Library/Application Support/channel-brains-mcp`
- Linux: `~/.local/share/channel-brains-mcp`

Set `CHANNEL_BRAINS_HOME` before launching the MCP server to use another location:

```bash
CHANNEL_BRAINS_HOME=/path/to/channel-brains-data uvx --from "git+https://github.com/Pu11en/channel-brains@v0.1.1" channel-brains-mcp
```

Captions and search indexes stay on the local machine. The only network requests are public YouTube requests made by `yt-dlp` and caption URL retrieval during ingestion.

### Persistent YouTube rate limits

Channel Brains first uses paced anonymous requests and bounded retries. If YouTube keeps
returning HTTP 429 from your network, explicitly opt in to one of yt-dlp's authenticated
cookie sources in the MCP server environment:

```text
CHANNEL_BRAINS_YOUTUBE_COOKIES_FROM_BROWSER=firefox
```

Or provide a Netscape-format cookie file:

```text
CHANNEL_BRAINS_YOUTUBE_COOKIES_FILE=/private/path/youtube-cookies.txt
```

Set only one cookie source. Browser cookies grant the server the same YouTube session
access as that browser; keep cookie files private and never commit them. A network proxy
can be configured separately with `CHANNEL_BRAINS_YOUTUBE_PROXY`, using an `http`,
`https`, `socks4`, `socks5`, or `socks5h` URL. After changing the MCP environment,
restart the server and call `create_brain` again with the same channel URL to resume.

## MCP client configuration

All examples use the published `Pu11en/channel-brains` release command.

### Hermes Agent

Add this entry under `mcp_servers` in your Hermes configuration, then restart Hermes:

```yaml
mcp_servers:
  channel_brains:
    command: uvx
    args:
      - --from
      - git+https://github.com/Pu11en/channel-brains@v0.1.1
      - channel-brains-mcp
    timeout: 120
    connect_timeout: 60
```

Hermes discovers the six tools at startup and registers them with an `mcp_channel_brains_` prefix.

### Claude Code

Register it at user scope:

```bash
claude mcp add --transport stdio --scope user channel-brains -- \
  uvx --from "git+https://github.com/Pu11en/channel-brains@v0.1.1" channel-brains-mcp
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
args = ["--from", "git+https://github.com/Pu11en/channel-brains@v0.1.1", "channel-brains-mcp"]
```

Restart Codex after saving the file.

### ZCode

Merge this server into `mcp.servers` in the user-level
`~/.zcode/cli/config.json`, then reload ZCode:

```json
{
  "mcp": {
    "servers": {
      "channel-brains": {
        "command": "uvx",
        "args": [
          "--from",
          "git+https://github.com/Pu11en/channel-brains@v0.1.1",
          "channel-brains-mcp"
        ]
      }
    }
  }
}
```

Preserve every existing server and unrelated setting in that file. ZCode also
accepts the generic server definition through **Settings → MCP Servers → New MCP
Server** with **User** scope and **stdio** type.

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
        "git+https://github.com/Pu11en/channel-brains@v0.1.1",
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

The default test suite is fully offline. The manual live release gate exercises a real
channel through caption ingestion and timestamped local search:

```bash
uv run pytest -m live tests/test_live_youtube.py
```

Override the default channel when needed:

```bash
CHANNEL_BRAINS_LIVE_CHANNEL=https://www.youtube.com/@OpenAI uv run pytest -m live tests/test_live_youtube.py
```

YouTube requests are paced. HTTP 429 responses receive bounded retries and then pause
the brain without losing completed work. Call `create_brain` again later with the same
channel URL to resume.

## Limitations

- Public YouTube captions can be unavailable, expired, restricted, or rate-limited.
  No local client can guarantee that an external YouTube request succeeds 100% of the
  time; Channel Brains guarantees bounded behavior, resumable progress, and explicit
  status when YouTube refuses a request.
- Search is lexical SQLite FTS5 search, not semantic search or an answer-generation system.
- The server indexes captions only. It does not download videos, reuse video footage, or create a knowledge graph.
- A channel can contain many videos. The first local ingestion may take time.

## License

MIT. See [LICENSE](LICENSE).
