# Security Policy

## Scope

Channel Brains is a **local** MCP server. It runs entirely on your machine. There is
no hosted service, no account system, and no server for an attacker to compromise
remotely. The threats that matter are local: what gets stored on disk and what leaves
your machine over the network.

## What it stores

- A SQLite database and a lock file in your platform's user-data directory
  (or `CHANNEL_BRAINS_HOME` if you set it).
- Indexed public YouTube captions. These are public content — not sensitive.

## What it sends over the network

The **only** outbound requests are:

- Public YouTube requests made by `yt-dlp` during ingestion.
- Caption URL retrieval during ingestion.

Nothing else leaves your machine. Search is local. There is no telemetry, analytics,
or call-home.

## Cookies (the one sensitive case)

If you opt in to cookie-based authentication for YouTube rate limits, the cookies you
provide grant Channel Brains the same YouTube session access as the source browser or
cookie file.

- **Never commit cookie files** to this or any repository.
- Keep `CHANNEL_BRAINS_YOUTUBE_COOKIES_FILE` pointing at a private path.
- Cookie material stays on your machine; it is not transmitted anywhere except YouTube.

## Reporting a vulnerability

If you believe you've found a security issue, please open a private security advisory:

1. Go to <https://github.com/Pu11en/channel-brains/security/advisories/new>
2. Describe the issue and reproduction steps.

Please **do not** open a public issue for security vulnerabilities. I will respond
and, if a fix is warranted, credit responsible disclosure in the release notes.

## Supported versions

Only the [latest release](https://github.com/Pu11en/channel-brains/releases) receives
security fixes.
