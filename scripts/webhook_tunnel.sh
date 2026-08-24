#!/usr/bin/env bash
# P2-M35: public HTTPS tunnel to the local webhook endpoint (zrok per official
# Razorpay localhost guidance; ngrok.io/loca.lt etc. are blacklisted).
#
# Prerequisites (one-time, HUMAN):
#   1. Create a free account at https://my.zrok.io  ->  copy your enable token.
#   2. Run:  zrok enable <YOUR_TOKEN>               (never paste it into chat)
#
# Usage:
#   scripts/webhook_tunnel.sh            # starts tunnel for http://127.0.0.1:8000
#
# Then register the printed public URL in the Razorpay Test Dashboard
# (see docs/PHASE2_TUNNEL.md) using the webhook secret ALREADY in .env.

set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v zrok >/dev/null 2>&1; then
  echo "zrok is not installed. Install with:  brew install zrok"
  exit 1
fi

if ! zrok status >/dev/null 2>&1; then
  echo "zrok environment not enabled."
  echo "Run once:  zrok enable <YOUR_TOKEN>   # token from https://my.zrok.io"
  exit 1
fi

API_PORT="${RAZORMESH_API_PORT:-8000}"
if ! curl -sf "http://127.0.0.1:${API_PORT}/health" >/dev/null 2>&1; then
  echo "Starting local API on :${API_PORT} ..."
  nohup uv run --project services/api \
    uvicorn razormesh_api.api.main:app --host 127.0.0.1 --port "${API_PORT}" \
    > /tmp/razormesh_api.log 2>&1 &
  sleep 4
fi

echo "Sharing public URL -> http://127.0.0.1:${API_PORT}  (Ctrl-C to stop)"
echo "Register the printed URL + /api/v1/webhooks/razorpay in the Test Dashboard."
exec zrok share public "http://127.0.0.1:${API_PORT}" --headless
