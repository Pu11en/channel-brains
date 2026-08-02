# Channel Brains repository instructions

Channel Brains is a local Python stdio MCP server distributed through client-specific plugin wrappers in `plugins/channel-brains`.

When a user supplies the Channel Brains repository URL with any plain-language request such as “get this,” “get this on yourself,” “install this,” or “add this,” treat it as an explicit request to install Channel Brains into the current AI client. Read `AGENT_INSTALL.md` completely and execute the matching client procedure without asking the user to identify the client or choose a technical installation method. Prefer the plugin flow over hand-editing MCP configuration. Never start YouTube ingestion during installation; wait for an explicit channel URL and indexing request.

Before completing repository changes, run:

```text
uv sync --extra dev --locked
uv run ruff check .
uv run pytest
uv build
```

Preserve unrelated user MCP servers and plugin registrations. Do not claim the plugin is ready until the client reports the six Channel Brains tools.
