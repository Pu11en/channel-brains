# Channel Brains

## One-line installation

Paste this into your local AI coding workspace:

> Get this on yourself: https://github.com/Pu11en/channel-brains

That is the complete user instruction. The AI should identify its own client,
install the appropriate Channel Brains plugin or MCP adapter, activate it, and
verify the six tools. You should not need to know what MCP, `uvx`, JSON, TOML,
YAML, or a plugin marketplace is.

**Channel Brains** is a local, stdio MCP server that indexes publicly available YouTube captions into a searchable SQLite FTS5 database. It runs on your computer, needs no API key, and preserves timestamped links back to the original videos.

It is deliberately small and local:

- No hosted service, Docker, browser dashboard, embeddings, or LLM runtime
- No YouTube API key, database server, or cloud account
- One local SQLite database per user, protected by a cross-process ingestion lock
- One channel ingestion job at a time, with resumable per-video progress
- Search results cite the original video and timestamp

## What the AI does

Natural requests such as “get this on yourself,” “install this,” or “add this to
your tools,” when accompanied by the repository URL, all mean the same thing.
The AI must not make the user restate the request using technical terminology.

The agent reads
[`AGENT_INSTALL.md`](AGENT_INSTALL.md), detects which supported client it is running
inside, installs the prerequisite if needed, runs the offline health check, installs the
client-appropriate plugin or catalog adapter, and verifies that all six tools are available.
If the current task cannot refresh newly installed MCP tools, the AI uses the
same six operations through the bundled command bridge and continues immediately.

Channel Brains is still an MCP server: the plugin is the easy-to-install wrapper that
bundles the MCP registration and usage instructions. The same repository provides
compatible packaging for ZCode, Claude Code, and Codex, plus a Hermes adapter.

The agent needs permission to install a plugin and run local commands. A web-only chat
that cannot access your computer cannot install a local MCP server.

## Direct plugin installation

All plugin routes require [uv](https://docs.astral.sh/uv/). The plugin uses `uvx` to
launch the pinned release. `yt-dlp` is included in that release and must not be
installed globally.

### ZCode

The AI installs the bundled plugin itself by running this from its repository
clone:

```bash
uv run --no-project python scripts/install_zcode_plugin.py
```

The installer copies Channel Brains to ZCode's stable user plugin directory and
safely adds that directory to `~/.zcode/cli/config.json`. It preserves unrelated
plugins, MCP servers, and settings. No marketplace clicking or application
restart is required; the user's channel URL can be the next message in the same
task. On ZCode versions that freeze a task's tool inventory, the AI uses the
same-session bridge until native tools become visible.

### Claude Code

```bash
claude plugin marketplace add Pu11en/channel-brains
claude plugin install channel-brains@channel-brains --scope user
```

For an existing installation, run `claude plugin marketplace update
channel-brains` followed by `claude plugin update
channel-brains@channel-brains --scope user`.

Claude Code can activate it with `/reload-plugins`. If the agent cannot invoke
that command itself, it continues through the same-session bridge; the user does
not have to reload anything.

### Codex

```bash
codex plugin marketplace add Pu11en/channel-brains
codex plugin add channel-brains@channel-brains
```

For an existing installation, run `codex plugin marketplace upgrade
channel-brains` before repeating `codex plugin add`. Re-adding a configured
marketplace does not refresh its snapshot.

The native tools appear automatically in future Codex tasks. The installation
task remains immediately usable through the same-session bridge.

### Hermes Agent

```bash
hermes mcp add channel-brains --command uvx --connect-timeout 60 --args --from git+https://github.com/Pu11en/channel-brains@v0.1.3 channel-brains-mcp
```

The installing AI accepts Hermes's default **enable all six tools** prompt and
verifies discovery. Hermes can activate it with `/reload-mcp`; otherwise the AI
uses the same-session bridge. A candidate manifest for the reviewed Hermes MCP
catalog is included at
[`integrations/hermes/manifest.yaml`](integrations/hermes/manifest.yaml).

### Same-session bridge

Claude Code, Codex, ZCode, and other clients may freeze the current task's MCP
tool inventory. Installation still finishes in that task. The AI runs the same
six operation names through this pinned local command until native MCP tools are
available:

```bash
uvx --from "git+https://github.com/Pu11en/channel-brains@v0.1.3" channel-brains get_brain_status
```

`create_brain` starts a detached local worker, so indexing continues after the
one-shot command returns. This bridge is for agent continuity, not a second
product the user must learn; native plugin tools remain the preferred interface.

When the user asks to be notified at completion, the AI makes one plugin-owned
wait instead of creating a scheduled task:

```bash
uvx --from "git+https://github.com/Pu11en/channel-brains@v0.1.3" channel-brains \
  get_brain_status --brain-id BRAIN_ID --wait-until-terminal
```

The process watches local SQLite state and returns at `ready`, `paused`,
`failed`, or timeout. Indexing survives a closed client, but notification in the
conversation requires that this wait call remain active.

## Manual install

Requires [uv](https://docs.astral.sh/uv/).

MCP clients launch the pinned production release with:

```bash
uvx --from "git+https://github.com/Pu11en/channel-brains@v0.1.3" channel-brains-mcp
```

Verify the installation without starting the MCP server or contacting YouTube:

```bash
uvx --from "git+https://github.com/Pu11en/channel-brains@v0.1.3" channel-brains-mcp --check
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
    "git+https://github.com/Pu11en/channel-brains@v0.1.3",
    "channel-brains-mcp"
  ]
}
```

Use a startup/connect timeout of at least 60 seconds. The first `uvx` run downloads
the pinned package and can be slower than later starts.

## First workflow

1. Add the server to an MCP client using one of the configurations below.
2. Call `create_brain` with a supported YouTube channel URL, such as `https://www.youtube.com/@OpenAI`.
3. When asked to notify at completion, call `get_brain_status` once with
   `wait_until_terminal=true`; otherwise take status snapshots only on request.
4. Use `search_brain` to retrieve timestamped caption matches.

The initial ingestion scans the complete channel listing so it can select up to 50 videos by view count. Caption availability and YouTube rate limits determine how much can be indexed.

## MCP tools

Channel Brains exposes exactly these six tools:

| Tool | Purpose |
| --- | --- |
| `create_brain` | Validate a channel URL, persist a brain, and start local ingestion. |
| `get_brain_status` | Read a snapshot or wait locally for completion, with progress and no YouTube requests. |
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
CHANNEL_BRAINS_HOME=/path/to/channel-brains-data uvx --from "git+https://github.com/Pu11en/channel-brains@v0.1.3" channel-brains-mcp
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

## Manual MCP client configuration

These definitions are fallbacks for clients where plugin installation is unavailable.
All examples use the published `Pu11en/channel-brains` release command.

### Hermes Agent

Add this entry under `mcp_servers` in your Hermes configuration, then run `/reload-mcp`:

```yaml
mcp_servers:
  channel_brains:
    command: uvx
    args:
      - --from
      - git+https://github.com/Pu11en/channel-brains@v0.1.3
      - channel-brains-mcp
    timeout: 120
    connect_timeout: 60
```

Hermes discovers the six tools at startup and registers them with an `mcp_channel_brains_` prefix.

### Claude Code

Register it at user scope:

```bash
claude mcp add --transport stdio --scope user channel-brains -- \
  uvx --from "git+https://github.com/Pu11en/channel-brains@v0.1.3" channel-brains-mcp
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
args = ["--from", "git+https://github.com/Pu11en/channel-brains@v0.1.3", "channel-brains-mcp"]
```

Open a new Codex task after saving the file.

### ZCode

Merge this server into `mcp.servers` in the user-level
`~/.zcode/cli/config.json`, then open a new ZCode task:

```json
{
  "mcp": {
    "servers": {
      "channel-brains": {
        "command": "uvx",
        "args": [
          "--from",
          "git+https://github.com/Pu11en/channel-brains@v0.1.3",
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
        "git+https://github.com/Pu11en/channel-brains@v0.1.3",
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
