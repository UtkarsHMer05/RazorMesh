#!/usr/bin/env bash
# P2-M37: one reliable start workflow for the Phase-2 local stack.
#
#   scripts/phase2_start.sh
#
# Idempotent and non-destructive: brings up whatever is not already running,
# then verifies readiness for a real Test Mode checkout (M38).
# Never prints secret values. Never touches the system PostgreSQL on :5432.

set -euo pipefail
cd "$(dirname "$0")/.."

API_PORT="${RAZORMESH_API_PORT:-8000}"
WEB_PORT="${RAZORMESH_WEB_PORT:-3000}"
API_LOG=/tmp/razormesh_api.log
WEB_LOG=/tmp/razormesh_web.log
TUNNEL_LOG=/tmp/razormesh_tunnel.log

step() { printf '\n== %s\n' "$1"; }

step "1/7 Docker infra (postgres 127.0.0.1:15432, redis 127.0.0.1:16379)"
docker compose up -d >/dev/null
for _ in $(seq 1 30); do
  docker exec razormesh-postgres pg_isready -U razormesh >/dev/null 2>&1 && break
  sleep 1
done
docker exec razormesh-postgres pg_isready -U razormesh >/dev/null
echo "postgres: ready"
docker exec razormesh-redis redis-cli ping >/dev/null
echo "redis: ready"

step "2/7 Migrations (alembic upgrade head)"
uv run --project services/api alembic upgrade head | tail -1

step "3/7 Catalog seed (idempotent)"
uv run --project services/api python -m razormesh_api.catalog >/dev/null
echo "seed: ok"

step "4/7 Config sanity (variable names only, never values)"
uv run --project services/api python - <<'PY'
from razormesh_api.settings import (
    ProviderConfigError,
    Settings,
    validate_payment_provider_config,
)

s = Settings()
print(f"payment_provider: {s.payment_provider}")
print(f"razorpay_mode: {s.razorpay_mode}")
try:
    validate_payment_provider_config(s)
    print("config guard: ok")
except ProviderConfigError as exc:
    print("config guard: PROBLEMS:")
    for problem in exc.problems:
        print(f"  - {problem}")
    raise SystemExit(1)
PY

step "5/7 API on 127.0.0.1:${API_PORT}"
if curl -sf "http://127.0.0.1:${API_PORT}/health" >/dev/null 2>&1; then
  echo "api: already running"
else
  nohup uv run --project services/api \
    uvicorn razormesh_api.api.main:app --host 127.0.0.1 --port "${API_PORT}" \
    > "${API_LOG}" 2>&1 &
  for _ in $(seq 1 30); do
    curl -sf "http://127.0.0.1:${API_PORT}/health" >/dev/null 2>&1 && break
    sleep 1
  done
  curl -sf "http://127.0.0.1:${API_PORT}/health" >/dev/null
  echo "api: started (log ${API_LOG})"
fi

step "6/7 Web on 127.0.0.1:${WEB_PORT}"
if curl -sf -o /dev/null "http://127.0.0.1:${WEB_PORT}/"; then
  echo "web: already running"
else
  (cd apps/web && nohup pnpm dev > "${WEB_LOG}" 2>&1 &)
  for _ in $(seq 1 60); do
    curl -sf -o /dev/null "http://127.0.0.1:${WEB_PORT}/" && break
    sleep 1
  done
  curl -sf -o /dev/null "http://127.0.0.1:${WEB_PORT}/"
  echo "web: started (log ${WEB_LOG})"
fi

step "7/7 Public webhook tunnel (zrok)"
PUBLIC_URL="$(grep -E '^RAZORPAY_WEBHOOK_PUBLIC_URL=' .env | cut -d= -f2- || true)"
EFFECTIVE_URL="${PUBLIC_URL:-}"
if [ -n "${PUBLIC_URL}" ] && curl -sf --max-time 10 "${PUBLIC_URL}/health" >/dev/null 2>&1; then
  echo "tunnel: live at ${PUBLIC_URL}"
else
  echo "tunnel: RAZORPAY_WEBHOOK_PUBLIC_URL missing or unreachable."
  if ! command -v zrok >/dev/null 2>&1 || ! zrok status >/dev/null 2>&1; then
    echo "zrok is not installed/enabled — see scripts/webhook_tunnel.sh prerequisites."
    exit 1
  fi
  nohup zrok share public "http://127.0.0.1:${API_PORT}" --headless \
    > "${TUNNEL_LOG}" 2>&1 &
  NEW_URL=""
  for _ in $(seq 1 30); do
    NEW_URL="$(grep -Eo 'https://[a-z0-9]+\.shares\.zrok\.io' "${TUNNEL_LOG}" | head -1 || true)"
    [ -n "${NEW_URL}" ] && break
    sleep 1
  done
  if [ -z "${NEW_URL}" ]; then
    echo "tunnel: failed to start — inspect ${TUNNEL_LOG}"
    exit 1
  fi
  EFFECTIVE_URL="${NEW_URL}"
  echo "tunnel: NEW share ${NEW_URL} (log ${TUNNEL_LOG})"
  echo "ACTION REQUIRED — the share is NOT reserved:"
  echo "  1. Update the Dashboard webhook URL to ${NEW_URL}/api/v1/webhooks/razorpay (OTP 754081)."
  echo "  2. Set RAZORPAY_WEBHOOK_PUBLIC_URL=${NEW_URL} in .env"
fi

step "Readiness"
echo -n "local  /ready: "
curl -s "http://127.0.0.1:${API_PORT}/ready"
echo
echo -n "public /ready: "
curl -s --max-time 10 "${EFFECTIVE_URL}/ready"
echo
echo
echo "Stack ready. Buyer UI: http://localhost:${WEB_PORT}/buyer"
echo "(Use localhost, NOT 127.0.0.1: dev CORS allows the WEB_ORIGIN http://localhost:3000.)"
echo "Webhook inbox: ${EFFECTIVE_URL}/api/v1/webhooks/razorpay"
