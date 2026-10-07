#!/usr/bin/env bash
# Home egress tunnel for the hosted Channel Brains server (Option B).
# Starts: 1) a local SOCKS5 proxy (pproxy, bound to 127.0.0.1 only)
#         2) a bore TCP tunnel (bore.pub, free, no account) exposing that proxy
# Then prints the socks5 URL to set as Railway CHANNEL_BRAINS_YOUTUBE_PROXY.
# Restart this script after any reboot; the bore port changes, so update Railway.
set -euo pipefail

SOCKS_PORT="${SOCKS_PORT:-1080}"
BORE="${HOME}/.local/bin/bore"
NGROK="${HOME}/.local/bin/ngrok"

if ! curl -sS -m 3 --socks5-hostname "127.0.0.1:${SOCKS_PORT}" https://api.ipify.org >/dev/null 2>&1; then
  echo "starting pproxy on 127.0.0.1:${SOCKS_PORT}"
  nohup uvx --python 3.12 pproxy -l "socks5://127.0.0.1:${SOCKS_PORT}" >/tmp/pproxy.log 2>&1 &
  sleep 5
  curl -sS -m 15 --socks5-hostname "127.0.0.1:${SOCKS_PORT}" https://api.ipify.org >/dev/null
fi

if ! pgrep -f "bore local" >/dev/null 2>&1; then
  echo "starting bore tunnel"
  nohup "$BORE" local "${SOCKS_PORT}" --to bore.pub >/tmp/bore.log 2>&1 &
  sleep 5
fi

HOSTPORT=$(grep -o "listening at [^ ]*" /tmp/bore.log | tail -1 | cut -d' ' -f3)
if [ -z "${HOSTPORT:-}" ]; then
  echo "bore tunnel did not report an address; check /tmp/bore.log" >&2
  exit 1
fi

echo
echo "proxy egress IP: $(curl -sS -m 20 --socks5-hostname 127.0.0.1:${SOCKS_PORT} https://api.ipify.org)"
echo "public tunnel:   ${HOSTPORT}"
echo
echo "Set on Railway:"
echo "  railway variable set \"CHANNEL_BRAINS_YOUTUBE_PROXY=socks5h://${HOSTPORT}\""
echo "(ngrok fallback, if bore.pub is ever down: ${NGROK} tcp ${SOCKS_PORT} — free TCP requires a card on file)"
