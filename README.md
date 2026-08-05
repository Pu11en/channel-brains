# Channel Brains

**Tell your AI to install it. It does.**

[![CI](https://github.com/Pu11en/channel-brains/actions/workflows/ci.yml/badge.svg)](https://github.com/Pu11en/channel-brains/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/Pu11en/channel-brains?color=blue&label=release)](https://github.com/Pu11en/channel-brains/releases)
[![Python](https://img.shields.io/badge/python-3.10%E2%80%913.14-blue)](https://github.com/Pu11en/channel-brains)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Channel Brains is a **local MCP server** that indexes the public captions of any
YouTube channel into a searchable database on your own machine — then lets your AI
coding agent query it with timestamped citations back to the exact second of video.

No API key. No cloud. No account. It runs entirely on your computer.

> Paste this into your local AI coding agent (Codex, Claude Code, ZCode, or Hermes):
>
> > **Get this on yourself: https://github.com/Pu11en/channel-brains**
>
> That's the whole instruction. The agent identifies its own client, installs the
> right plugin, and verifies the six tools. You don't need to know what MCP or a
> plugin marketplace is.

## Why

Every podcast, lecture, and dev stream is a library of knowledge — but video is
unsearchable. Channel Brains turns a channel's spoken content into a database your
agent can cite. Ask a question, get the answer with a link to the exact moment
someone said it.

## See it

Point Channel Brains at a channel, wait for it to index, then search. Here it is
searching Matt Pocock's channel for "generics" — note the timestamped citation back
to the source video:

```text
$ channel-brains search_brain --brain-id 8c45c891e781 --query "generics"

rank 1 · Generics: The most intimidating TypeScript feature
       https://youtu.be/dLPgQRbVquo?t=0  (0:00)
       "…we are going to be focusing on 10 tips to make you a master of
       typescript generics… they give you the power to make abstractions, to make
       your code a lot more DRY…"

rank 2 · A Complete Guide To Vercel's AI SDK
       https://youtu.be/mojZpktAiYQ?t=965  (16:05)
       "…use generateObject instead of generateText… we pass it a schema with a
       Zod schema…"

rank 3 · Generics: The most intimidating TypeScript feature
       https://youtu.be/dLPgQRbVquo?t=45  (0:45)
```

Every result links to the precise second the words were spoken. Your agent gets
grounded, quotable evidence — not a hallucination.

## How it works

1. You give your agent a channel URL.
2. Channel Brains ingests the public captions via `yt-dlp` (no API key), selecting
   up to 50 videos by view count, and stores them in a local SQLite FTS5 database.
3. Ingestion is resumable and rate-limit-aware — it pauses cleanly on HTTP 429 and
   picks up where it left off.
4. Your agent searches that database and returns matches with timestamped YouTube links.

It is deliberately small and local:

- No hosted service, Docker, browser dashboard, embeddings, or LLM runtime
- No YouTube API key, database server, or cloud account
- One local SQLite database per user, protected by a cross-process ingestion lock
- One channel ingestion job at a time, with resumable per-video progress
- The only network requests are public YouTube requests made by `yt-dlp` during ingestion

## Install

**The easy way** — paste this to your local AI coding agent and let it install itself:

> Get this on yourself: https://github.com/Pu11en/channel-brains

**The manual way** — requires [uv](https://docs.astral.sh/uv/). MCP clients launch the
pinned production release with:

```bash
uvx --from "git+https://github.com/Pu11en/channel-brains@v0.1.4" channel-brains-mcp
```

Verify the installation without starting the MCP server or contacting YouTube:

```bash
uvx --from "git+https://github.com/Pu11en/channel-brains@v0.1.4" channel-brains-mcp --check
```

A successful check prints one JSON object with `"status": "ok"`, `"transport":
"stdio"`, and `"tool_count": 6`.

The server communicates only through standard input and output. Do not run it as an HTTP service.

> **Note:** Installation requires a local AI coding agent (Codex, Claude Code, ZCode,
> or Hermes) that can run commands on your computer. A web-only chat (ChatGPT,
> Claude.ai) cannot install a local MCP server.

## The six tools

Channel Brains exposes exactly these six tools to your agent:

| Tool | Purpose |
| --- | --- |
| `create_brain` | Validate a channel URL, persist a brain, and start local ingestion. |
| `get_brain_status` | Read a snapshot or wait locally for completion, with progress and no YouTube requests. |
| `list_brain_videos` | Page through indexed, skipped, pending, and failed video records. |
| `search_brain` | Search local FTS5 caption chunks and return timestamped YouTube citations. |
| `get_video_transcript` | Page through stored caption chunks for one indexed video. |
| `delete_brain` | Remove a completed brain and all its local records. Active ingestion is refused. |

## First workflow

1. Add the server to an MCP client using the install method above.
2. Call `create_brain` with a supported YouTube channel URL, such as `https://www.youtube.com/@OpenAI`.
3. Immediately call `get_brain_status` once with `wait_until_terminal=true` and keep
   the same turn active until it returns.
4. Use `search_brain` to retrieve timestamped caption matches.

The initial ingestion scans the complete channel listing so it can select up to 50
videos by view count. Caption availability and YouTube rate limits determine how much
can be indexed.

## Configuration

### Local data and privacy

By default, Channel Brains stores its SQLite database and lock file in the platform's
user-data directory:

- Windows: `%LOCALAPPDATA%\channel-brains-mcp`
- macOS: `~/Library/Application Support/channel-brains-mcp`
- Linux: `~/.local/share/channel-brains-mcp`

Set `CHANNEL_BRAINS_HOME` before launching the MCP server to use another location:

```bash
CHANNEL_BRAINS_HOME=/path/to/channel-brains-data uvx --from "git+https://github.com/Pu11en/channel-brains@v0.1.4" channel-brains-mcp
```

Captions and search indexes stay on the local machine. The only network requests are
public YouTube requests made by `yt-dlp` and caption URL retrieval during ingestion.

### Persistent YouTube rate limits

Channel Brains first uses paced anonymous requests and bounded retries. If YouTube
keeps returning HTTP 429 from your network, explicitly opt in to one of yt-dlp's
authenticated cookie sources in the MCP server environment:

```text
CHANNEL_BRAINS_YOUTUBE_COOKIES_FROM_BROWSER=firefox
```

Or provide a Netscape-format cookie file:

```text
CHANNEL_BRAINS_YOUTUBE_COOKIES_FILE=/private/path/youtube-cookies.txt
```

Set only one cookie source. Browser cookies grant the server the same YouTube session
access as that browser; keep cookie files private and never commit them. A network
proxy can be configured separately with `CHANNEL_BRAINS_YOUTUBE_PROXY`, using an
`http`, `https`, `socks4`, `socks5`, or `socks5h` URL. After changing the MCP
environment, restart the server and call `create_brain` again with the same channel
URL to resume.

## Manual MCP client configuration

The automated install above covers Codex, Claude Code, ZCode, and Hermes. For any
other MCP client, the generic server definition is:

```json
{
  "command": "uvx",
  "args": [
    "--from",
    "git+https://github.com/Pu11en/channel-brains@v0.1.4",
    "channel-brains-mcp"
  ]
}
```

Use a startup/connect timeout of at least 60 seconds. The first `uvx` run downloads
the pinned package and can be slower than later starts.

Per-client configuration snippets (Hermes YAML, Codex TOML, ZCode/OpenCode JSON) are
in [`docs/clients.md`](docs/clients.md).

## For AI agents

The automated agent installation flow is fully specified in
[`AGENT_INSTALL.md`](AGENT_INSTALL.md). If you are an agent that has been asked to
install this repository, read that file completely and execute the matching client
procedure. Do not start YouTube ingestion during installation; wait for an explicit
channel URL and indexing request.

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

- Public YouTube captions can be unavailable, expired, restricted, or rate-limited. No
  local client can guarantee that an external YouTube request succeeds 100% of the
  time; Channel Brains guarantees bounded behavior, resumable progress, and explicit
  status when YouTube refuses a request.
- Search is lexical SQLite FTS5 search, not semantic search or an answer-generation system.
- The server indexes captions only. It does not download videos, reuse video footage, or create a knowledge graph.
- A channel can contain many videos. The first local ingestion may take time.

## License

MIT. © Drew Pullen. See [LICENSE](LICENSE).
