# Install Channel Brains into your agent

This file is written for the AI agent operating the user's local Codex, Claude Code,
Hermes Agent, or ZCode installation. If the user gave you this repository and asked
you to install it, complete this procedure yourself. Do not ask the user to copy
commands or choose a client you can identify from your own runtime.

## Required outcome

Install Channel Brains as a user-scoped local stdio MCP server and verify that it
advertises exactly these six tools:

- `create_brain`
- `get_brain_status`
- `list_brain_videos`
- `search_brain`
- `get_video_transcript`
- `delete_brain`

Do not call `create_brain` during installation. Creating a brain makes live YouTube
requests and requires an explicit channel URL from the user.

## Safety and scope

- Only install from `https://github.com/Pu11en/channel-brains` at tag `v0.1.1`.
- Preserve every unrelated entry in the user's existing MCP configuration.
- Use user scope, not project scope, unless the user explicitly asks otherwise.
- Do not run `channel-brains-mcp` without `--check` in a terminal. The normal command
  is a stdio server and correctly waits for an MCP client on standard input.
- Do not request an API key. Channel Brains does not require one.

## 1. Ensure `uvx` is available

First run `uvx --version`. If it is unavailable and you have permission to install
local developer tools, install `uv` using an official method appropriate to the
operating system:

- Windows: `winget install --id=astral-sh.uv -e`
- macOS with Homebrew: `brew install uv`
- macOS or Linux without Homebrew:
  `curl -LsSf https://astral.sh/uv/install.sh | sh`

Refresh the shell environment and locate the executable with `where.exe uvx` on
Windows or `command -v uvx` on macOS/Linux. When a GUI client cannot see the updated
`PATH`, use the discovered absolute `uvx` path as the MCP `command`.

If your permission system requires approval for installing `uv`, request that single
approval with a short explanation, then continue after it is granted.

## 2. Run the offline release check

Run:

```text
uvx --from git+https://github.com/Pu11en/channel-brains@v0.1.1 channel-brains-mcp --check
```

Continue only if the command exits successfully and its JSON output contains:

```json
{"status":"ok","transport":"stdio","tool_count":6}
```

This check must not contact YouTube. If it fails, report the command, exit status,
and error output. Do not write a broken MCP entry.

## 3. Detect and configure the current client

Use the section matching the agent you are currently running inside. Do not make the
user identify it for you.

### Codex

Prefer the Codex CLI when it is available:

```text
codex mcp add channel-brains -- uvx --from git+https://github.com/Pu11en/channel-brains@v0.1.1 channel-brains-mcp
```

Otherwise, merge this table into the user-level `~/.codex/config.toml` (on Windows,
the same path is under `%USERPROFILE%`):

```toml
[mcp_servers.channel-brains]
command = "uvx"
args = ["--from", "git+https://github.com/Pu11en/channel-brains@v0.1.1", "channel-brains-mcp"]
startup_timeout_sec = 60
tool_timeout_sec = 120
```

If an absolute executable path was required, replace `uvx` in `command` with it.
Verify the saved registration with `codex mcp list` when the CLI is available.

### Claude Code

Run:

```text
claude mcp add --transport stdio --scope user channel-brains -- uvx --from git+https://github.com/Pu11en/channel-brains@v0.1.1 channel-brains-mcp
```

If an absolute executable path was required, use it in place of `uvx`. Verify the
saved registration with `claude mcp get channel-brains` and `claude mcp list`.

### Hermes Agent

Merge this entry under `mcp_servers` in `~/.hermes/config.yaml` without replacing
other servers:

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

If an absolute executable path was required, use it for `command` instead of `uvx`.
Hermes registers the tools with names beginning `mcp_channel_brains_`.

### ZCode

Merge this server into `mcp.servers` in the user-level
`~/.zcode/cli/config.json`. Preserve all existing servers and unrelated settings:

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

If an absolute executable path was required, use it for `command` instead of `uvx`.
ZCode can also add the same definition through **Settings → MCP Servers → New MCP
Server** using **User** scope and **stdio** type. Confirm that the server is enabled.

## 4. Reload and verify

Reload or restart MCP servers using the current client's supported mechanism. If the
client cannot reload itself safely, finish all configuration first and ask the user
for only one action: close and reopen the client.

After reload, inspect the connected server and require all six tools listed above.
Do not claim installation succeeded based only on the config file or offline check.
If runtime discovery is impossible from the current session, say that configuration
and preflight succeeded but final discovery remains pending until the client reopens.

When verification succeeds, tell the user simply that Channel Brains is installed
and ready, then ask for the YouTube channel URL they want to index.
