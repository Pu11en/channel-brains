#!/usr/bin/env bash
# Authorize every dynamically-registered ChatGPT client (tpc_*) for the Channel Brains API.
# ChatGPT registers a fresh OAuth client on each plugin-add attempt; without a client
# grant Auth0 rejects the authorize request ("not authorized to access resource server").
#
# Uses the non-expiring M2M watchdog client stored at
# ~/.config/channel-brains/auth0-watchdog.json (client-credentials; scopes are limited
# to read:clients, read/create:client_grants). Run once now, then leave a looping
# instance detached so freshly registered clients are granted within seconds.
set -euo pipefail
CONF="$HOME/.config/channel-brains/auth0-watchdog.json"
INTERVAL="${1:-0}"  # seconds between sweeps; +INTERVAL loops forever

read -r DOMAIN CLIENT_ID CLIENT_SECRET AUDIENCE < <(python3 - "$CONF" <<'PY'
import json, sys
cfg = json.load(open(sys.argv[1]))
print(cfg["domain"], cfg["client_id"], cfg["client_secret"], cfg["audience"])
PY
)
API="https://$DOMAIN/api/v2"

sweep() {
  local token
  token=$(curl -sS -m 20 -X POST "https://$DOMAIN/oauth/token" \
    -H 'Content-Type: application/json' \
    -d "{\"grant_type\":\"client_credentials\",\"client_id\":\"$CLIENT_ID\",\"client_secret\":\"$CLIENT_SECRET\",\"audience\":\"$API/\"}" \
    | python3 -c "import json,sys; print(json.load(sys.stdin).get('access_token',''))")
  [ -n "$token" ] || { echo "watchdog: no token" >&2; return 1; }
  curl -sS -m 20 -H "Authorization: Bearer $token" "$API/clients?per_page=100" > /tmp/a0-clients.json
  curl -sS -m 20 -H "Authorization: Bearer $token" "$API/client-grants?per_page=100" > /tmp/a0-grants.json
  local count
  count=$(python3 - /tmp/a0-clients.json /tmp/a0-grants.json "$AUDIENCE" <<'PY'
import json, sys
clients_raw, grants, audience = json.load(open(sys.argv[1])), json.load(open(sys.argv[2])), sys.argv[3]
clients = clients_raw.get("clients", clients_raw) if isinstance(clients_raw, dict) else clients_raw
granted = {(g["client_id"], g.get("subject_type", "client")) for g in grants if g.get("audience") == audience}
need = [
    c["client_id"]
    for c in clients
    if c["client_id"].startswith("tpc_")
    and ("user" not in {t for cid, t in granted if cid == c["client_id"]}
         or "client" not in {t for cid, t in granted if cid == c["client_id"]})
]
open("/tmp/a0-need.json", "w").write("\n".join(need))
print(len(need))
PY
)
  local granted_now=0
  while read -r cid; do
    [ -n "$cid" ] || continue
    # Auth0 requires separate grants per subject type: "client" for machine tokens,
    # "user" for the authorization-code login flow ChatGPT uses.
    for st in client user; do
      curl -sS -m 20 -X POST -H "Authorization: Bearer $token" -H 'Content-Type: application/json' \
        "$API/client-grants" \
        -d "{\"client_id\":\"$cid\",\"audience\":\"$AUDIENCE\",\"scope\":[],\"subject_type\":\"$st\"}" \
        >/dev/null 2>&1 || true
    done
    echo "watchdog: granted $cid"
    granted_now=$((granted_now + 1))
  done < /tmp/a0-need.json
  [ "$granted_now" -eq 0 ] || echo "watchdog: $granted_now client(s) granted"
}

if [ "$INTERVAL" -gt 0 ] 2>/dev/null; then
  while true; do
    sweep || true
    sleep "$INTERVAL"
  done
else
  sweep
fi
