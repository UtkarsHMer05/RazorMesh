# Phase-2 Webhook Tunnel Setup (Test Mode)

Official guidance (R-014, checked 2026-08-24): Razorpay cannot reach `localhost`;
common tunnels (ngrok.io, loca.lt, requestbin…) are **blacklisted**; **zrok** is the
recommended tool. Test-mode Dashboard webhook setup prompts for OTP **754081**.

## One-time (human)

1. Create a free zrok account: <https://my.zrok.io> and copy your enable token.
2. Enable this machine (token stays local):
   ```bash
   zrok enable <YOUR_TOKEN>
   ```

## Every run

Recommended one-command workflow (P2-M37): brings up infra, migrations, seed,
API, web and the tunnel idempotently, then verifies readiness:

```bash
make phase2-up          # = scripts/phase2_start.sh
```

Tunnel only (starts the API if needed, then shares it):

```bash
scripts/webhook_tunnel.sh
```

Both print a public HTTPS URL such as
`https://<random>.share.zrok.io`. Append the webhook path:

```
<public-url>/api/v1/webhooks/razorpay
```

## Register in Razorpay Test Mode Dashboard

1. Log in → switch to **Test Mode**.
2. Account & Settings → Webhooks → **Add New Webhook** (OTP when prompted: 754081).
3. Paste the full public URL from above.
4. Secret: use the value ALREADY stored in your `.env` as `RAZORPAY_WEBHOOK_SECRET`
   (do NOT paste it into any chat; type/paste it directly in the Dashboard field).
5. Select events: `payment.authorized`, `payment.captured`, `payment.failed`,
   `order.paid`.
6. Save. Note (R-016/D-032, checked 2026-08-24): current official docs state
   "Test events get triggered on a transaction done in the Test mode" — there
   is no Dashboard test-notification button for this account, so signed
   deliveries are produced by the first real Test Mode transaction (M38).

## Point RazorMesh at the URL

Put the printed base URL into `.env`:

```dotenv
RAZORPAY_WEBHOOK_PUBLIC_URL=https://<random>.share.zrok.io
```

and restart the API.

## Verify

Perform a Test Mode transaction (e.g. the M38 success checkout) and watch:
`/tmp/razormesh_api.log` plus `GET /audit/timeline` — verified events appear in the
`provider_events` inbox and evidence ledger.
