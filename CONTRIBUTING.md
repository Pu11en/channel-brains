# Contributing to Channel Brains

Thanks for your interest in contributing. Channel Brains is a small, local MCP server
and the goal is to keep it that way: no hosted services, no cloud dependencies, no API keys.

## Setup

```bash
git clone https://github.com/Pu11en/channel-brains.git
cd channel-brains
uv sync --extra dev
```

## Before you open a pull request

Run the full verification loop. CI runs the same commands:

```bash
uv sync --extra dev --locked
uv run ruff check .
uv run pytest
uv build
```

All four must pass. The default test suite is fully offline and should complete in
under a minute.

## What counts as a good change

- **Keep it local.** Anything that adds a hosted service, cloud account, or external
  API key is out of scope. The product's value is that it runs entirely on your machine.
- **Keep the surface area at six tools.** Proposing a new MCP tool is a design
  discussion, not a quick fix — open an issue first.
- **Don't break the install flow.** The agent-install runbook in `AGENT_INSTALL.md`
  and the plugin manifests are load-bearing. Changes there need extra care.
- **Match the existing style.** The codebase uses `ruff` with the rules configured in
  `pyproject.toml`; line length is 100, target is Python 3.10+.

## Live (network) tests

Tests that hit real YouTube are marked `live` and skipped by default. Run them
manually before a release:

```bash
uv run pytest -m live tests/test_live_youtube.py
```

They are paced; expect them to take a while. Don't add `live`-marked tests to the
default suite.

## Reporting issues

Open an issue with:

- What you expected
- What happened
- The exact channel URL and the `get_brain_status` output (redact nothing sensitive —
  it's all local)
- Your OS, Python version, and how you installed (plugin name or `uvx`)

## Security

See [SECURITY.md](SECURITY.md). In short: it's a local tool; cookies are the only
sensitive material, and they never leave your machine or get committed.

## License

By contributing, you agree your contributions are licensed under the project's
[MIT license](LICENSE).
