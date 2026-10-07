"""Plain-HTML policy pages served by the hosted server for plugin review."""

from __future__ import annotations

SUPPORT_EMAIL = "drewpullen2003@gmail.com"

PRIVACY_HTML = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>Channel Brains Privacy Policy</title>
<style>body{{font-family:system-ui,sans-serif;max-width:720px;margin:2rem auto;padding:0 1rem;line-height:1.6}}h1{{font-size:1.5rem}}</style>
</head><body>
<h1>Channel Brains — Privacy Policy</h1>
<p>Last updated: 2026-10-06</p>
<p>Channel Brains is an MCP plugin that indexes the public captions of YouTube channels you
choose so you can search them with timestamped results inside ChatGPT.</p>
<h2>What we store</h2>
<ul>
<li><strong>Account identifier.</strong> When you connect Channel Brains, our sign-in provider
(Auth0) gives us a stable, opaque user ID. We use it only to keep your data separate from
other accounts. We never see your password.</li>
<li><strong>Channel and video data.</strong> The URLs of channels you ask us to index, and
public metadata for their videos (titles, view counts, upload dates, caption languages).</li>
<li><strong>Caption text.</strong> The publicly available caption text of the indexed videos,
stored so search works without contacting YouTube again.</li>
<li><strong>Indexing records.</strong> Each brain's status, progress counts, error summaries,
and the times it was created and last updated, so you can follow and resume indexing.</li>
</ul>
<h2>How we use it</h2>
<p>Only to provide the service: indexing the channels you request, searching them when you
ask, and showing indexing progress. We do not sell your data, use it for advertising, or use
it to train AI models.</p>
<h2>What we do not collect</h2>
<p>We do not collect payment information, contacts, precise location, or the contents of your
ChatGPT conversations. We receive only the tool calls ChatGPT makes, such as a channel URL or
the search words you ask to run. Search words are used to answer that request and are not
saved in your account's data.</p>
<h2>Who receives data</h2>
<ul>
<li><strong>Auth0</strong> (sign-in provider) stores your sign-in details, such as your email
address, under <a href="https://auth0.com/privacy">its own privacy policy</a>. Auth0 shares only
the opaque user ID with us.</li>
<li><strong>Railway</strong> (our hosting provider) runs the server and stores the data listed
above. Like any web host, Railway processes network information such as IP addresses to
deliver requests, and keeps short-lived server logs.</li>
<li><strong>YouTube</strong> receives automated requests from our servers, sent through an
internet connection we operate, to fetch public channel listings and captions. Your identity
is never sent to YouTube.</li>
</ul>
<p>We do not share your data with anyone else, except if required by law.</p>
<h2>Isolation</h2>
<p>Each account's brains are stored in a separate, per-account database. Other users cannot
list, read, search, or delete your data.</p>
<h2>Retention and deletion</h2>
<p>Your data is kept until you delete it. Deleting a brain removes its videos and captions
immediately. To delete everything tied to your account, email
<a href="mailto:{SUPPORT_EMAIL}">{SUPPORT_EMAIL}</a>; we remove it within 30 days.</p>
<h2>Children</h2>
<p>Channel Brains is not directed at children under 13.</p>
<h2>Contact</h2>
<p>Questions: <a href="mailto:{SUPPORT_EMAIL}">{SUPPORT_EMAIL}</a></p>
</body></html>"""

TERMS_HTML = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>Channel Brains Terms of Service</title>
<style>body{{font-family:system-ui,sans-serif;max-width:720px;margin:2rem auto;padding:0 1rem;line-height:1.6}}h1{{font-size:1.5rem}}</style>
</head><body>
<h1>Channel Brains — Terms of Service</h1>
<p>Last updated: 2026-09-29</p>
<h2>1. The service</h2>
<p>Channel Brains indexes publicly available YouTube captions for channels you explicitly
choose, and returns timestamped search results. It is provided "as is", without warranty of
any kind.</p>
<h2>2. Your responsibilities</h2>
<p>Only index channels you have the right to search. Do not use the service to infringe
copyrights, to harass anyone, or to violate YouTube's Terms of Service. Caption excerpts are
quotations of third-party content; respect the rights of their creators.</p>
<h2>3. Acceptable use</h2>
<p>Each account may hold a limited number of brains (currently 3) and each brain indexes at
most 50 videos. We may rate-limit or pause indexing to keep the service healthy.</p>
<h2>4. Availability</h2>
<p>We do not guarantee uninterrupted availability. Indexing may pause when upstream services
(YouTube) refuse requests; completed work is preserved and resumable.</p>
<h2>5. Liability</h2>
<p>To the maximum extent permitted by law, the operators are not liable for any damages
arising from use of the service.</p>
<h2>6. Changes</h2>
<p>These terms may be updated; continued use after an update constitutes acceptance.</p>
<h2>Contact</h2>
<p><a href="mailto:{SUPPORT_EMAIL}">{SUPPORT_EMAIL}</a></p>
</body></html>"""

LANDING_HTML = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>Channel Brains</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
body{font-family:system-ui,sans-serif;max-width:680px;margin:3rem auto;padding:0 1.2rem;line-height:1.65;color:#1a1a2e}
h1{font-size:2rem;margin-bottom:.2rem}p.lead{font-size:1.1rem;color:#444}
.badge{display:inline-block;background:#1E1B4B;color:#22D3EE;padding:.15rem .6rem;border-radius:999px;font-size:.8rem;margin-left:.4rem;vertical-align:middle}
code{background:#f1f1f4;padding:.15rem .4rem;border-radius:4px;font-size:.9em}
.step{display:flex;gap:.8rem;margin:.6rem 0}.step b{flex:0 0 1.6rem;height:1.6rem;border-radius:50%;background:#1E1B4B;color:#fff;display:flex;align-items:center;justify-content:center;font-size:.9rem}
footer{margin-top:2.5rem;border-top:1px solid #eee;padding-top:1rem;font-size:.9rem}
a{color:#0d9488}
</style></head><body>
<h1>Channel Brains <span class="badge">MCP plugin</span></h1>
<p class="lead">Ask ChatGPT anything a YouTube channel has ever said — with timestamps.</p>
<p>Channel Brains indexes the public captions of YouTube channels you choose and turns them
into searchable, timestamped evidence inside ChatGPT. Every answer cites the exact video and
second it came from, so you can trust — and check — what the channel actually said.</p>
<h2>How it works</h2>
<div class="step"><b>1</b><div>Add the Channel Brains plugin in ChatGPT and sign in.</div></div>
<div class="step"><b>2</b><div>Paste a YouTube channel URL and ask ChatGPT to index it.</div></div>
<div class="step"><b>3</b><div>Ask questions; get answers with clickable timestamps.</div></div>
<h2>For developers</h2>
<p>This is an MCP server speaking streamable HTTP with OAuth 2.1 sign-in:</p>
<p><code>https://channel-brains-production.up.railway.app/mcp</code></p>
<p>Source and local-install instructions: <a href="https://github.com/Pu11en/channel-brains">github.com/Pu11en/channel-brains</a></p>
<footer>
<a href="/privacy">Privacy policy</a> · <a href="/terms">Terms of service</a> ·
<a href="mailto:drewpullen2003@gmail.com">Support</a>
</footer>
</body></html>"""
