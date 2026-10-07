#!/usr/bin/env bash
# Self-healing home egress tunnel for the hosted Channel Brains server.
# Verifies the FULL public path (bore.pub:<port> -> pproxy -> internet); if any
# part is dead or zombie, kills and restarts both, then re-publishes the port to
# Railway only when it changed. Safe to run every 5 minutes via Task Scheduler.
set -uo pipefail

export PATH="$HOME/.local/bin:$PATH"
cd "$(dirname "$0")/.." || exit 1
LOG=/tmp/ensure_tunnel.log
exec >>"$LOG" 2>&1
echo "--- $(date -Is) ensure_tunnel run"

SOCKS_PORT="${SOCKS_PORT:-1080}"

current_port() {
  grep -o "listening at [^ ]*" /tmp/bore.log 2>/dev/null | tail -1 | cut -d" " -f3
}

publicly_healthy() {
  local port
  port=$(current_port)
  [ -n "$port" ] || return 1
  curl -sS -m 12 --socks5-hostname "$port" https://api.ipify.org >/dev/null 2>&1
}

if ! publicly_healthy; then
  echo "public tunnel unhealthy; restarting"
  pkill -f "bore local" 2>/dev/null
  pkill -f "pproxy -l" 2>/dev/null
  sleep 1
  : > /tmp/bore.log
  nohup uvx --python 3.12 pproxy -l "socks5://127.0.0.1:${SOCKS_PORT}" >/tmp/pproxy.log 2>&1 &
  sleep 4
  nohup "$HOME/.local/bin/bore" local "${SOCKS_PORT}" --to bore.pub >/tmp/bore.log 2>&1 &
  sleep 6
  publicly_healthy || { echo "tunnel still unhealthy after restart"; exit 1; }
fi

HOSTPORT=$(current_port)
[ -n "${HOSTPORT:-}" ] || { echo "no bore address found"; exit 1; }

DESIRED="socks5h://${HOSTPORT}"
CURRENT=$(railway variables 2>/dev/null | grep -io "socks5h://[a-zA-Z0-9./:-]*" | head -1)
if [ "$DESIRED" != "$CURRENT" ]; then
  echo "port changed (${CURRENT:-none} -> ${DESIRED}); updating Railway"
  railway variable set "CHANNEL_BRAINS_YOUTUBE_PROXY=${DESIRED}"
else
  echo "railway already points at ${DESIRED}"
fi
echo "tunnel publicly healthy via ${HOSTPORT}"
