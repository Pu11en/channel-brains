"""Offline contract tests for the multi-client plugin distribution."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from channel_brains_mcp.config import VERSION
from channel_brains_mcp.server import TOOL_NAMES

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "channel-brains"
RELEASE_SOURCE = f"git+https://github.com/Pu11en/channel-brains@v{VERSION}"


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_shared_mcp_definition_launches_the_pinned_release() -> None:
    definition = load_json(PLUGIN / ".mcp.json")
    codex_server = definition["mcpServers"]["channel-brains"]
    claude = load_json(PLUGIN / ".claude-plugin" / "plugin.json")
    zcode = load_json(PLUGIN / ".zcode-plugin" / "plugin.json")
    claude_server = claude["mcpServers"]["channel-brains"]
    zcode_server = zcode["mcpServers"]["channel-brains"]

    assert codex_server == {
        "command": "uvx",
        "args": ["--from", RELEASE_SOURCE, "channel-brains-mcp"],
    }
    expected_plugin_server = {"type": "stdio", **codex_server}
    assert claude_server == expected_plugin_server
    assert zcode_server == expected_plugin_server


def test_client_manifests_share_identity_version_skill_and_mcp_definition() -> None:
    manifest_paths = (
        PLUGIN / ".codex-plugin" / "plugin.json",
        PLUGIN / ".claude-plugin" / "plugin.json",
        PLUGIN / ".zcode-plugin" / "plugin.json",
    )

    for path in manifest_paths:
        manifest = load_json(path)
        assert manifest["name"] == "channel-brains"
        assert manifest["version"] == VERSION
        assert manifest["skills"] == "./skills/"
        assert "TODO" not in path.read_text(encoding="utf-8")

    assert load_json(manifest_paths[0])["mcpServers"] == "./.mcp.json"
    assert isinstance(load_json(manifest_paths[1])["mcpServers"], dict)
    assert isinstance(load_json(manifest_paths[2])["mcpServers"], dict)


def test_marketplaces_resolve_the_same_plugin_directory() -> None:
    codex = load_json(ROOT / ".agents" / "plugins" / "marketplace.json")
    claude = load_json(ROOT / ".claude-plugin" / "marketplace.json")
    zcode = load_json(ROOT / "marketplace.json")

    assert codex["name"] == claude["name"] == zcode["name"] == "channel-brains"
    assert codex["plugins"][0]["source"]["path"] == "./plugins/channel-brains"
    assert claude["plugins"][0]["source"] == "./plugins/channel-brains"
    assert zcode["plugins"][0]["source"] == "./plugins/channel-brains"
    assert claude["plugins"][0]["version"] == VERSION
    assert zcode["plugins"][0]["version"] == VERSION


def test_usage_skill_names_the_complete_tool_contract() -> None:
    skill = (PLUGIN / "skills" / "channel-brains" / "SKILL.md").read_text(
        encoding="utf-8"
    )

    assert "TODO" not in skill
    for tool_name in TOOL_NAMES:
        assert f"`{tool_name}`" in skill
    assert "untrusted third-party content" in skill
    assert "no separate global `yt-dlp`" in skill
    assert RELEASE_SOURCE in skill
    assert "same-session bridge" in skill
    assert "wait_until_terminal=true" in skill
    assert "Never create a client automation" in skill


def test_hermes_candidate_manifest_uses_the_same_release_and_tools() -> None:
    manifest = (ROOT / "integrations" / "hermes" / "manifest.yaml").read_text(
        encoding="utf-8"
    )

    assert "manifest_version: 1" in manifest
    assert f'    - "{RELEASE_SOURCE}"' in manifest
    assert f'  version: "{VERSION}"' in manifest
    for tool_name in TOOL_NAMES:
        assert f"    - {tool_name}" in manifest


def test_agent_install_uses_automatic_client_activation_commands() -> None:
    runbook = (ROOT / "AGENT_INSTALL.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "Get this on yourself: https://github.com/Pu11en/channel-brains" in readme
    assert "get this on yourself" in runbook.lower()
    assert "Do not ask the user to" in runbook
    assert "claude plugin install channel-brains@channel-brains" in runbook
    assert "codex plugin add channel-brains@channel-brains" in runbook
    assert "hermes mcp add channel-brains" in runbook
    assert "hermes mcp test channel-brains" in runbook
    assert "sending an empty line" in runbook
    assert "python scripts/install_zcode_plugin.py" in runbook
    assert "plugins.dirs" in runbook
    assert "Never ask for an application" in runbook
    assert "/reload-plugins" in runbook
    assert "/reload-mcp" in runbook
    assert "does not need a separate global `yt-dlp`" in runbook
    assert f"uvx --from {RELEASE_SOURCE} channel-brains <operation>" in runbook
    assert "use the same-session bridge" in runbook.lower()
    assert "--wait-until-terminal" in runbook
    assert "scheduled task" in runbook


def test_zcode_installer_preserves_config_and_is_idempotent(tmp_path: Path) -> None:
    config_path = tmp_path / ".zcode" / "cli" / "config.json"
    target_path = tmp_path / ".zcode" / "plugins" / "channel-brains"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        json.dumps(
            {
                "mcp": {"servers": {"existing": {"command": "existing-server"}}},
                "plugins": {"enabled": False, "dirs": ["/keep/me"], "custom": "keep"},
                "unrelated": {"keep": True},
            }
        ),
        encoding="utf-8",
    )
    command = [
        sys.executable,
        str(ROOT / "scripts" / "install_zcode_plugin.py"),
        "--target",
        str(target_path),
        "--config",
        str(config_path),
    ]

    first = subprocess.run(command, check=True, capture_output=True, text=True)
    second = subprocess.run(command, check=True, capture_output=True, text=True)

    assert json.loads(first.stdout)["status"] == "installed"
    assert json.loads(second.stdout)["config_changed"] is False
    config = load_json(config_path)
    assert config["mcp"]["servers"]["existing"] == {"command": "existing-server"}
    assert config["plugins"]["enabled"] is True
    assert config["plugins"]["dirs"] == ["/keep/me", str(target_path.resolve())]
    assert config["plugins"]["custom"] == "keep"
    assert config["unrelated"] == {"keep": True}
    assert load_json(target_path / ".zcode-plugin" / "plugin.json")["name"] == "channel-brains"


def test_zcode_installer_refuses_to_replace_an_unrelated_directory(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    target_path = tmp_path / "existing-data"
    target_path.mkdir()
    marker = target_path / "keep.txt"
    marker.write_text("do not overwrite", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "install_zcode_plugin.py"),
            "--target",
            str(target_path),
            "--config",
            str(config_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert marker.read_text(encoding="utf-8") == "do not overwrite"
    assert not config_path.exists()
