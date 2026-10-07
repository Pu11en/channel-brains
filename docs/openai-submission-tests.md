# Channel Brains — OpenAI Submission Test Cases

Executed against production on 2026-10-06 by the maintainer. Each case is runnable by a
reviewer with the demo account and the plugin's public MCP URL
(`https://channel-brains-production.up.railway.app/mcp`) without internal context.

## Demo credentials
- Email: `drewp716@yahoo.com`
- Password: withheld from the public repo — recorded in the submission portal's reviewer credentials.
- No MFA is enabled on this account.

## Positive test cases (5)

### P1 — Connect the plugin and load its tools
1. In ChatGPT, add the Channel Brains plugin (directory listing or provided MCP URL).
2. Complete the OAuth sign-in with the demo account.
3. Expected: connection succeeds; the plugin exposes `create_brain`, `get_brain_status`,
   `list_brain_videos`, `search_brain`, `get_video_transcript`, `delete_brain`, `get_profile`.
   - Result 2026-10-06: PASS (7 tools listed over the authenticated public endpoint).

### P2 — Index a channel end to end
1. Ask: "index this channel: https://www.youtube.com/channel/UCNZEktrsM5oJZ-MK4jKPMOQ"
2. Expected: the plugin reports progress and reaches `ready` with indexed videos and
   caption chunks, zero failures.
   - Result 2026-10-06: PASS (158 discovered, 50 selected, 50 indexed, 1,678 chunks,
     0 failures; performed from ChatGPT by a non-operator account).

### P3 — Search returns timestamped citations
1. Ask: "search this channel for AI, give me timestamps".
2. Expected: ranked results citing video title, timestamp, and a `youtu.be/<id>?t=<seconds>`
   URL grounded in the stored captions; no invented answers.
   - Result 2026-10-06: PASS (e.g. [0:39] "10 Github Repos That Will Kill Your Monthly S…"
     → https://youtu.be/jMAe1h39rHo?t=39).

### P4 — Account isolation
1. As the demo account, create a brain.
2. Query the same brain ID from the operator's separate connection.
3. Expected: the demo account's data is invisible to other accounts (count = 0) and vice
   versa; each account holds its own brains.
   - Result 2026-10-06: PASS (cross-account status lookups return count = 0 in both
     directions; enforced by per-account storage namespaces keyed to the verified token
     subject).

### P5 — Delete requires confirmation and removes data
1. Call delete without confirmation, then with `confirm=true`.
2. Expected: refusal first, permanent removal second; subsequent status lookups find nothing.
   - Result 2026-10-06: PASS (refused without confirm; deleted videos + chunks with
     confirmation; brain gone afterward).

## Negative test cases (3)

### N1 — Invalid channel URL
1. Ask: "index this channel: https://example.com/notyoutube".
2. Expected: an error result explaining the URL must be an HTTPS YouTube channel URL
   (`/@handle`, `/channel/UC…`, `/c/name`, or `/user/name`); nothing is queued; no network
   work is performed.
   - Result 2026-10-06: PASS (error message matches; brain not created).

### N2 — Nonexistent YouTube channel
1. Ask: "index this channel: https://www.youtube.com/@definitelynotrealchannelxx9q7".
2. Expected: discovery fails with an explicit cause ("YouTube returned 404: channel or
   resource not found") recorded on the brain, surfaced honestly to the user.
   - Result 2026-10-06: PASS (exact 404 cause reported; retried cleanly once YouTube was
   reachable).

### N3 — Unauthenticated access to the MCP endpoint
1. Send MCP requests to the public endpoint without a bearer token.
2. Expected: HTTP 401 with `WWW-Authenticate` challenge; OAuth metadata at
   `/.well-known/oauth-protected-resource` advertises the sign-in server; no tool executes.
   - Result 2026-10-06: PASS (401 + challenge; metadata 200; no unauthenticated tool calls
     possible).

## Supporting checks (not part of the 5+3)
- Privacy policy and terms served by the application at `/privacy` and `/terms` (HTTP 200).
- Tool annotations present and accurate (read tools marked read-only; `delete_brain`
  destructive; `create_brain` open-world).
- Retrying a failed brain reports `status: queued` with `monitoring_required: true`
  (hosts are correctly told to wait for the resumed job).
- Per-account brain limit (3) enforced at creation; re-indexing an existing channel is
  never blocked.
