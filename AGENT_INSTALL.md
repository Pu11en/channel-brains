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

Use ZCode's agent-supported inline plugin directory. This is the primary ZCode
flow: do not stop and ask the user to operate Settings when local file and shell
tools are available.

1. Keep the cloned repository available until installation finishes.
2. From the repository root, run:

   ```text
   uv run --no-project python scripts/install_zcode_plugin.py
   ```

3. Read `~/.zcode/cli/config.json` and validate it as JSON. Confirm that
   `plugins.enabled` is `true` and that `plugins.dirs` contains the absolute
   `~/.zcode/plugins/channel-brains` path. Preserve every unrelated plugin,
   MCP server, and setting.
4. Do not edit ZCode marketplace or plugin-cache internals. The installer copies
   only the bundled plugin into the stable user plugin directory and atomically
   merges that supported directory into the user config.
5. Continue in the current task. The current model request cannot gain tools
   halfway through a turn, so ask which YouTube channel the user wants to index.
   Their channel-URL reply is the next turn in this same task, when ZCode can
   refresh the plugin-provided MCP tools.
6. On that next turn, require all six tools before calling `create_brain`. If the
   current ZCode version keeps the task's tool inventory frozen, report
   **Reload pending** and ask for one new task. Never ask for an application
   restart or a Settings walkthrough.

The marketplace UI remains an optional human-managed alternative, not an agent
installation dependency.

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
