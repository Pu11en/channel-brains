# Install Channel Brains into your agent

This runbook is for the AI agent operating the user's local ZCode, Claude Code,
Codex, or Hermes Agent client. When the user asks you to install this repository,
complete the matching procedure yourself. Prefer the plugin or native catalog
flow over hand-editing MCP configuration.

Treat any plain-language request supplied with the Channel Brains repository URL
as an explicit installation request, including “get this,” “get this on yourself,”
“install this,” “add this,” or “put this in your tools.” Do not ask the user to
identify their client, choose an installation method, copy commands, or translate
their request into MCP terminology. Detect the current client and proceed.

Channel Brains remains a local stdio MCP server. The plugin is the installable
wrapper that bundles its MCP registration and usage skill.

## Required outcome

Installation is complete only when the current client has discovered these six
tools:

- `create_brain`
- `get_brain_status`
- `list_brain_videos`
- `search_brain`
- `get_video_transcript`
- `delete_brain`

Hermes prefixes them with `mcp_channel_brains_`.

Do not call `create_brain` during installation. It makes live YouTube requests
and requires an explicit channel URL and indexing request from the user.

## Safety and prerequisites

- Install only from `https://github.com/Pu11en/channel-brains`.
- Preserve unrelated plugins, marketplaces, MCP servers, and settings.
- Use user scope unless the user explicitly requests project scope.
- Channel Brains needs `uvx`; it does not need a separate global `yt-dlp`.
- Do not run `channel-brains-mcp` without `--check` in a terminal. Normal mode
  is a stdio server and correctly waits for its client on standard input.
- Do not request an API key.

Run `uvx --version`. If it is unavailable and local developer-tool installation
is permitted, install `uv` using an official operating-system method, refresh
the shell, and continue. If the client cannot find a newly installed executable,
use the absolute `uvx` path in a manual MCP definition.

Before registering anything, run the offline release check:

```text
uvx --from git+https://github.com/Pu11en/channel-brains@v0.1.1 channel-brains-mcp --check
```

Continue only when it exits successfully with `"status":"ok"`,
`"transport":"stdio"`, and `"tool_count":6`.

## ZCode plugin

Use the plugin path because ZCode automatically refreshes affected sessions when
a plugin is enabled.

1. Open **Settings → Plugins**.
2. Choose **Create → Add marketplace** and enter:
   `https://github.com/Pu11en/channel-brains`
3. Find **Channel Brains** in the new personal marketplace and select **Install**.
4. Confirm the plugin is enabled. Its MCP appears under **Settings → MCP** in
   the Plugin MCP servers group.
5. Confirm all six tools are connected in the current task.

If you cannot control ZCode settings from the agent runtime, ask the user for
only this one UI action. Do not fall back to undocumented plugin-cache edits.

## Claude Code plugin

Run:

```text
claude plugin marketplace add Pu11en/channel-brains
claude plugin install channel-brains@channel-brains --scope user
```

Apply the new plugin in the active Claude Code session with `/reload-plugins`,
then inspect `/mcp` and require all six tools. If the current agent cannot issue
a slash command programmatically, ask the user to enter only `/reload-plugins`.

## Codex plugin

Run:

```text
codex plugin marketplace add Pu11en/channel-brains
codex plugin add channel-brains@channel-brains
codex plugin list
```

Codex loads newly installed plugin skills and MCP tools in a new task/session.
Do not ask the user to restart the whole application; ask for one new task, then
verify all six tools there.

## Hermes Agent

Until Channel Brains is merged into the Nous-reviewed Hermes MCP catalog, use
Hermes's native MCP registration command:

```text
hermes mcp add channel-brains --command uvx --connect-timeout 60 --args --from git+https://github.com/Pu11en/channel-brains@v0.1.1 channel-brains-mcp
```

Run `/reload-mcp` in the active Hermes session and require the six tools with
the `mcp_channel_brains_` prefix. A candidate upstream catalog manifest is kept
in `integrations/hermes/manifest.yaml`; once accepted upstream, prefer:

```text
hermes mcp install channel-brains
```

## Other local MCP clients

If the current client is not listed above but supports local stdio MCP servers,
use the generic definition in `plugins/channel-brains/.mcp.json` or translate its
`uvx` command and arguments into the client's documented user-scoped format.
Prefer a supported plugin or marketplace mechanism when one exists. Activate or
reload the client tool registry when supported, then require the same six tools.
Ask the user for a new task only when the client exposes no live reload mechanism.

If the environment is a web-only chat with no access to the user's computer, say
clearly that it cannot install local software. Do not pretend configuration was
written or that tools were connected.

## Completion language

Use these states accurately:

- **Preflight passed**: the offline `--check` succeeded.
- **Plugin installed**: the client saved and enabled the plugin.
- **Connected and ready**: the client connected to the MCP server and discovered
  all six tools.
- **Reload pending**: registration succeeded but the client has not refreshed
  its tool inventory yet.

Only say “Channel Brains is installed and ready” for the connected-and-ready
state. Then ask which YouTube channel the user wants to index.
