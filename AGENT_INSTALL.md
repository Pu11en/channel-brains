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

The native plugin exposes these six tools:

- `create_brain`
- `get_brain_status`
- `list_brain_videos`
- `search_brain`
- `get_video_transcript`
- `delete_brain`

Hermes prefixes them with `mcp_channel_brains_`.

Some clients freeze their MCP tool inventory for the lifetime of the current
task. That must not stop the installation conversation. Install the native
plugin for future tasks, then use the same-session command bridge below until
the client refreshes. The bridge has the same six operation names and returns
the same structured JSON as the MCP tools.

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
uvx --from git+https://github.com/Pu11en/channel-brains@v0.1.3 channel-brains-mcp --check
```

Continue only when it exits successfully with `"status":"ok"`,
`"transport":"stdio"`, and `"tool_count":6`.

## Same-session command bridge

Prefer the native MCP tools whenever they are present. When installation has
succeeded but the current task cannot see newly added tools, run Channel Brains
through the shell instead of asking the user to restart, reload, open Settings,
or create a new task:

```text
uvx --from git+https://github.com/Pu11en/channel-brains@v0.1.3 channel-brains <operation> [arguments]
```

The six bridge operations are:

```text
channel-brains create_brain --channel-url URL [--max-videos 50] [--language en]
channel-brains get_brain_status [--brain-id ID] [--wait-until-terminal]
channel-brains list_brain_videos --brain-id ID [--offset 0] [--limit 20]
channel-brains search_brain --query TEXT [--brain-id ID] [--limit 8]
channel-brains get_video_transcript --brain-id ID --video-id ID [--offset 0] [--limit 50]
channel-brains delete_brain --brain-id ID --confirm
```

Substitute the full pinned `uvx --from ... channel-brains` prefix for
`channel-brains` in those examples. `create_brain` starts a detached local
worker, so ingestion continues after the bridge command exits. Apply the same
consent, polling, citation, untrusted-caption, and deletion rules as the MCP
tools. Never use the bridge merely because a channel URL appears; the user must
explicitly ask to index it.

If the user says “let me know when it is done,” “monitor this,” “watch this,” or
equivalent, keep the current turn active and make Channel Brains own the wait:

```text
channel-brains get_brain_status --brain-id ID --wait-until-terminal
```

Use the full pinned bridge prefix above. Do not create a client automation,
scheduled task, heartbeat, or task-level polling loop. The command reads only
local SQLite state, reports progress when the client supports it, and returns
once the brain is `ready`, `paused`, or `failed`, or after its bounded timeout.
Indexing itself remains detached and continues if the client closes, but no
local plugin can post into a conversation that is no longer open.

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
6. On that next turn, use the native tools if all six are present. If the current
   ZCode version keeps the task's tool inventory frozen, use the same-session
   bridge. Never ask for an application restart, a new task, or a Settings
   walkthrough just to continue the Channel Brains workflow.

The marketplace UI remains an optional human-managed alternative, not an agent
installation dependency.

## Claude Code plugin

Run:

```text
claude plugin marketplace add Pu11en/channel-brains
claude plugin install channel-brains@channel-brains --scope user
```

Confirm the plugin is installed and enabled with `claude plugin list`. If the
active Claude Code runtime permits the agent to invoke `/reload-plugins`, do so
and inspect `/mcp` for all six tools. Otherwise, do not make the user type a
slash command: use the same-session bridge and continue in the current task.
The native plugin will load automatically in future Claude Code sessions.

## Codex plugin

Run:

```text
codex plugin marketplace add Pu11en/channel-brains
codex plugin add channel-brains@channel-brains
codex plugin list
```

Codex freezes a task's tool inventory. Confirm `codex plugin list` reports the
plugin installed and enabled, then use the same-session bridge in the current
task. Do not ask the user to restart the application or open a new task merely
to continue. The native plugin and all six MCP tools load automatically in
future Codex tasks.

## Hermes Agent

Until Channel Brains is merged into the Nous-reviewed Hermes MCP catalog, use
Hermes's native MCP registration command:

```text
hermes mcp add channel-brains --command uvx --connect-timeout 60 --args --from git+https://github.com/Pu11en/channel-brains@v0.1.3 channel-brains-mcp
```

Hermes asks whether to enable all discovered tools. The agent must accept the
default **Yes** itself by sending an empty line to the controlled terminal; do
not hand this prompt to the user. Then run `hermes mcp test channel-brains` and
require `Tools discovered: 6`. If the agent can invoke `/reload-mcp`, do so and
require the six tools with the `mcp_channel_brains_` prefix. Otherwise use the
same-session bridge rather than asking the user to reload. A candidate upstream
catalog manifest is kept in `integrations/hermes/manifest.yaml`; once accepted
upstream, prefer:

```text
hermes mcp install channel-brains
```

## Other local MCP clients

If the current client is not listed above but supports local stdio MCP servers,
use the generic definition in `plugins/channel-brains/.mcp.json` or translate its
`uvx` command and arguments into the client's documented user-scoped format.
Prefer a supported plugin or marketplace mechanism when one exists. Activate or
reload the client tool registry when the agent can do so, then require the same
six tools. If the current task's inventory is frozen, use the same-session
bridge rather than transferring technical activation work to the user.

If the environment is a web-only chat with no access to the user's computer, say
clearly that it cannot install local software. Do not pretend configuration was
written or that tools were connected.

## Completion language

Use these states accurately:

- **Preflight passed**: the offline `--check` succeeded.
- **Plugin installed**: the client saved and enabled the plugin.
- **Bridge ready**: the native plugin is installed and the current task can use
  all six operations through the shell bridge while its tool inventory is frozen.
- **Connected and ready**: the client connected to the MCP server and discovered
  all six tools.
- **Reload pending**: registration succeeded but the client has not refreshed
  its tool inventory yet.

Only say “Channel Brains is installed and ready” for the connected-and-ready
state. For bridge-ready state, say “Channel Brains is installed and usable in
this task through its same-session bridge.” Then ask which YouTube channel the
user wants to index.

A channel URL sent directly in response to that question is explicit indexing
consent. Do not repeat the question. Do not mention stale Channel Brains copies
in another client's cache unless they prevent the current installation. Say
that six tools were discovered or that six bridge operations are available;
never claim all six operations were executed unless they actually were.
