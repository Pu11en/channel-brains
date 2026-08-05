# Manual MCP client configuration

The automated install flow (see the [README](../README.md#install) and
[`AGENT_INSTALL.md`](../AGENT_INSTALL.md)) covers Codex, Claude Code, ZCode, and Hermes.
These snippets are fallbacks for manual setup or clients not covered by the plugin flow.

All examples use the pinned `Pu11en/channel-brains` release. Use a startup/connect
timeout of at least 60 seconds.

## Hermes Agent

Add this entry under `mcp_servers` in your Hermes configuration, then run `/reload-mcp`:

```yaml
mcp_servers:
  channel_brains:
    command: uvx
    args:
      - --from
      - git+https://github.com/Pu11en/channel-brains@v0.1.4
      - channel-brains-mcp
    timeout: 120
    connect_timeout: 60
```

Hermes discovers the six tools at startup and registers them with an `mcp_channel_brains_` prefix.

## Claude Code

Register it at user scope:

```bash
claude mcp add --transport stdio --scope user channel-brains -- \
  uvx --from "git+https://github.com/Pu11en/channel-brains@v0.1.4" channel-brains-mcp
```

Confirm it is available:

```bash
claude mcp list
```

## Codex CLI

Add this to `~/.codex/config.toml`:

```toml
[mcp_servers.channel-brains]
command = "uvx"
args = ["--from", "git+https://github.com/Pu11en/channel-brains@v0.1.4", "channel-brains-mcp"]
```

Open a new Codex task after saving the file.

## ZCode

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
          "git+https://github.com/Pu11en/channel-brains@v0.1.4",
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

## OpenCode

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
        "git+https://github.com/Pu11en/channel-brains@v0.1.4",
        "channel-brains-mcp"
      ],
      "enabled": true
    }
  }
}
```

Restart OpenCode to load the server.
