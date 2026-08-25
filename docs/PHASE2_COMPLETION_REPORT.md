# RazorMesh Trust — Phase 2 Completion Report

**Razorpay Test Mode Integration — local prototype, credential-safe, Test Mode only.**

Status: **ALL 50 PHASE-2 MILESTONES PASS.** Phase 3 awaits human approval.
Generated: 2026-08-25. No secrets are stored in this document; credentials live
only in the gitignored root `.env` (mode 600).

---

## 1. Central properties (re-verified end-to-end)

> **The AI proposes. RazorGuard authorizes. The trusted executor executes.**
> **Intent-to-Execution Integrity:** a financial action executes only while the
> exact current transaction remains inside the human-confirmed authorization and
> the trusted execution context.

Phase-2 additions proven LIVE and in CI:
- Server-authoritative amounts only; the browser supplies zero pricing data.
- Callback signatures verify against the SERVER-stored order id and the exact
  server-issued execution attempt (P2-S08/D-037).
- Webhooks verify HMAC over RAW bytes before any parse; rejections mutate
  nothing (proven by pre/post mutation counts, M31/M32).
- Durable event-id dedup at the database level; duplicates never double-commit
  (M33/M42 storm tests).
- Delivery order is never assumed; every permutation converges to one effect
  (M34 matrix + concurrent mixed-event storms, M42).
- `payment.failed` → `payment.captured` reconciles exactly-once from the
  retained reservation, preventing interim authorization-capacity reuse
  (documented Razorpay behavior; D-037).
- Timeout/5xx after send ⇒ PROVIDER_UNKNOWN: identity + reservation held, no
  blind retry as a fresh payment; receipt-based discovery recovers correlation
  only through authority validation (M41/D-036).
- BLOCKED/CHALLENGED never execute; no execution without a valid ticket.

## 2. Phase-1 revalidation (M01–M05)

Clean-room acceptance 10/10 on hardened baseline `cef5a6f`; focused security
suites green; benchmark 14 pairs P=R=F1=1.0 at freeze; baseline frozen in
`docs/PHASE2_BASELINE.md` (HEAD `5186cca`, migration `d8b412f091c3`, cov 96%).
No Razorpay call of any kind occurred before M12.

## 3. Architecture delivered

```
RazorGuard ALLOW → reservation → ExecutionTicket → durable ExecutionAttempt
    → executor.create_order (server-authoritative amount/currency)
        → validate returned id/amount/currency/receipt/status
        ├─ definitive rejection/auth → FAILED + release
        └─ timeout/5xx/malformed     → PROVIDER_UNKNOWN + REQUIRED + HELD
    → launch payload (PUBLIC key_id + attempt/order/context) → browser
    → Standard Checkout → callback {attempt_id, payment_id, order_id, sig}
        → exact context + HMAC(SERVER order|payment) + provider fetch
        → current authorization/checkout revalidation before settlement
    → verified webhooks (raw-body HMAC) + x-razorpay-event-id inbox dedup
    → ONE provider-state reducer (callback | webhook | fetch | discovery)
        → exactly-once reservation commit / guarded late-capture reconcile
        → synthetic fulfilment ELIGIBLE → hash-chained Evidence Ledger
ReconciliationService (D-036): read-only receipt discovery → authority-checked
claim → reducer-only settlement → reconcile_state=RESOLVED; ops surface:
GET /ops/reconciliation/required, POST /ops/reconciliation/{id}.
```

State dimensions stay separate: attempt state / provider snapshots /
reservation / fulfilment. PostgreSQL is durable financial truth; Redis is
coordination only.

Key modules: `providers/razorpay.py` (client D-030, taxonomy, verification,
correlation, discovery), `executor.py`, `reducer.py`, `reconciliation.py`,
`webhook_inbox.py`, routes (`buyer`, `webhooks`, `ops`, `audit`,
`security_lab`), frontend `apps/web/src/app/buyer/page.tsx` +
`lib/razorpay.ts`.

## 4. Versions & dependencies

Python 3.13 / FastAPI 0.141.1 / SQLAlchemy 2.0.52 / httpx 0.28.1 (D-030 —
official SDK 2.0.1 declined: Beta classifier, opt-in auto-retry foot-gun,
extra deps). Frontend Next.js dev-line + React 19, Vitest, Playwright. All
versions pinned via uv.lock / pnpm-lock.yaml; pip-audit + pnpm audit clean at
M48 (see `VERSION_MANIFEST.md`).

## 5. Razorpay integration semantics (verified vs official docs R-013/R-014)

| Area | Implementation |
|---|---|
| Orders | server-side create; receipt=`r_{attempt_id}` ≤40; notes=5 opaque refs ≤15×256; create/fetch response id, amount, currency and receipt validated |
| Checkout | official v1 script loaded once; launch payload public-only; same-order re-open only pre-outcome |
| Callback verify | exact execution-attempt/intent/checkout/order binding; HMAC-SHA256(server-stored order\|payment, key_secret), constant-time; current authority revalidated before capture commit |
| Webhooks | raw-body HMAC before parse; event-id required; financial amount/currency correlated to durable attempt; size cap 413; error precedence pinned (413→400 EVENT_UNKNOWN→403 SIG) |
| Dedup | provider_events PK claim; DB-level concurrency safe |
| Ordering | not assumed; permutation + concurrent-storm convergence proven |
| authorized | informative-only (D-031); cannot regress SUCCEEDED nor fulfil EXECUTING |
| failed→captured | FAILED retains reservation/REQUIRED; verified capture converts the same hold to committed exactly once and is loudly audited |

## 6. Real Test Mode evidence (human-gated)

- **M38 success** (payment #3): ALLOW→ticket→order→failed→late-capture
  reconcile→SUCCEEDED/ELIGIBLE; 4 real signed webhooks verified=true;
  reserved→committed EXACTLY ONCE by the live webhook path; provider fetch
  matches; audit chain valid. Live defect found+fixed: authorized-in-FAILED
  snapshot semantics (D-034).
- **M39**: cross-source reconciliation doc incl. honest losses disclosure (D-033).
- **M40 failure** (attempt exa_01M0TKTPWPR593Y4HNW48BF0SE / order_TTionNHkv0TPGs /
  pay_TTipbCGaqWBrVD, 479900 INR): payment.failed webhook verified=true →
  attempt FAILED/NOT_ELIGIBLE, released exactly once (spend v3
  ensure→reserve→release), committed unchanged, PAYMENT_FAILED audited (chain
  valid, 13 events), provider fetch matches, callback_verified_at NULL correct.
  UI propagation lag fixed via read-only `/buyer/status` re-sync (D-035).
  This is preserved historical evidence: D-037 subsequently superseded the
  release-on-provider-failure policy with a conservative hold because the same
  transaction may later capture.
- **M49 clean-room**: fresh disposable instance — safe Test Order
  (order_TTlJ8vS3wCvEnp) created/fetched; LIVE signed captured-webhook settled
  it exactly once (reserved=0, committed=64890 minor, duplicate inert).

Full details: `docs/PHASE2_M38_*.md`, `docs/PHASE2_M39_EVIDENCE_RECONCILIATION.md`,
`docs/PHASE2_M40_EVIDENCE.md`, `PHASE2_STATUS.md` per-milestone sections.

## 7. Provider-unknown behavior (M41/D-036)

Timeout ⇒ PROVIDER_UNKNOWN + reconcile_state=REQUIRED + reservation held;
same-ticket re-entry returns the SAME attempt with ZERO extra provider calls
(transport-counted). Reconciliation = bounded read-only orders listing scanned
for exact receipt match; multiple matches conflict loudly; discovered orders
claimed ONLY after amount/currency validation under partial-unique indexes;
post-claim webhooks correlate normally; fetched "paid" reduces through the ONE
reducer to an exactly-once settlement that marks RESOLVED. Ops surface is
read-only listing + single safe pass (404/409 controlled).

## 8. Independent exit audit and final quality gates

The post-completion master-prompt audit found and repaired missing negative
proofs despite the historical suite being green: provider response authority,
exact callback attempt/cross-principal-session binding, stale authority at
settlement, webhook amount/currency correlation, failed-payment capacity reuse,
signed malformed webhook handling, and permissive non-test configuration.
D-037 and the final PHASE2_STATUS
addendum contain the full rationale and evidence.

- Backend pytest **375 passed** (unit/integration/security/Hypothesis stateful/
  concurrency/permutation/lab/benchmark/artifact gates).
- mypy strict clean from repo root AND services/api (54 files) — the earlier
  config-discovery gap was closed permanently in M15.
- ruff clean; frontend tsc/eslint/vitest 11/build clean; Playwright 5/5
  including stubbed-checkout E2E with DOM+wire secret scans (M46).
- Security Lab registry 22/22 synthetic scenarios; paired benchmark 20 pairs
  P=R=F1=1.0 (M43).
- `make security-check`: secret scan 0 findings; pip-audit clean; pnpm audit
  clean (M48 full battery table in PHASE2_STATUS).

## 9. Performance (M47, `docs/PHASE2_PERFORMANCE.json`)

Local compute clearly separated from network: full trusted path (mock charge)
p50 ≈ 58.5 ms; callback HMAC ≈ 0.002 ms; webhook ingest end-to-end (HMAC+DB
claim+reducer settle+commit) p50 ≈ 67.6 ms; REAL Test create_order p50 111 ms
(max 497); fetch_order p50 454 ms (n=5). Provider network time exceeds the
entire local trust path several-fold. Caveats recorded: Apple M2/arm64 dev
machine, disposable DBs, Test Mode ≠ Live production traffic, human modal time
excluded (recorded separately as non-system reference).

## 10. Limitations & known caveats (honest)

1. Test Mode only; no Live Mode code path exists (type-level + runtime guard).
2. Synthetic fulfilment only — ELIGIBLE marks readiness; nothing ships goods.
3. Receipt discovery scans one bounded page (count≤100) — adequate for Test
   Mode scale; production needs a provider-side receipt index or cursor paging.
4. Events API 404 for this account (R-018): event evidence relies on deliveries
   + fetch reconciliation, not the Events API.
5. Human wall-time dominates live flows; performance numbers exclude humans.
6. zrok share URLs are ephemeral; `RAZORPAY_WEBHOOK_PUBLIC_URL` must be updated
   after tunnel restarts (`make phase2-up`, `docs/PHASE2_TUNNEL.md`).
7. Cross-session buyer attempt redisplay remains future work (page reload
   resets component state; backend stays authoritative).
8. One ERROR row in the durable inbox from M38 diagnosis retained deliberately
   as operational history.
9. This is still a local prototype without production identity/session
   infrastructure. Cross-principal callback isolation is proven through
   ticket-bound attempts and provider order signatures; production auth is a
   later-phase/deployment concern and must not be inferred from this prototype.
10. A failed provider payment now conservatively retains its reservation while
    late capture remains possible. Phase 2 does not automate a timeout-based
    release because elapsed time alone is not provider truth; an explicit
    operator terminal-release workflow remains later work.

## 11. Human gates exercised

- M36 webhook Dashboard configuration (+tunnel) — completed by human.
- M38 guided REAL Test SUCCESS checkout — completed by human.
- M40 guided REAL Test FAILURE checkout — completed by human.
- Conditional gates avoided or absorbed: capture settings default; zrok
  installed via Homebrew with human awareness (D-032 deferred signed-delivery
  proof into M38 per human instruction, documented R-016).

## 12. No-Live evidence statement

Zero requests were ever sent with live credentials: `RAZORPAY_MODE` is
`Literal["test"]` (live unrepresentable), `rzp_live_` prefixes are rejected in
any mode at runtime (probe reproduced at M49: RAZORPAY_LIVE_KEY_REJECTED), and
the only `rzp_live_` string in the tree is the guard itself. Every real call
used the human-provided Test keys from `.env`.

## 13. Reproduction

```bash
docker compose down -v && docker compose up -d
make migrate && make seed
make test-db                      # provision razormesh_test for the suite (P2-M38 isolation)
uv run --project services/api pytest            # 375 passed
cd apps/web && pnpm i && pnpm test && npx playwright test
make security-check && make benchmark
# live-mode legs (require .env Test credentials):
uv run --project services/api python scripts/rzp_auth_check.py
PAYMENT_PROVIDER=mock ... scripts/acceptance.py   # mock clean-room acceptance
uv run --project services/api python scripts/rzp_first_order.py
```

## 14. Commit ledger

92 committed revisions currently exist; Phase-2 milestone commits
`P2-M01 … P2-M50` are individual, gated and local-only (never pushed).
Committed completion HEAD: `3e63bcb`. The independent exit-audit repairs and
evidence are intentionally uncommitted pending current human authorization.
Phase-1 history is untouched.

---

## 15. Phase-3 / Phase-4 preparation — INTERFACES AND NOTES ONLY

Nothing below is implemented; these are boundary notes so future work can
attach without redesigning the trust core.

### Phase 3 — Agentic reasoning layer (LLM + DeBERTa + optional XGBoost, Colab/Modal)
- Injection point: `DecisionEngine` rule list (`rules/*`) — a learned scorer
  may ADD reason codes/scores but MUST NOT bypass deterministic hard rules
  (money/catalog/policy) nor the ALLOW/BLOCK finality contract.
- Interface: extend `decider.Decision` with an optional `model_score` field and
  keep `intent_authorization_hash` covering ONLY authorization-relevant
  projections (untrusted model output must never enter the hash).
- Data authority: PostgreSQL stays authoritative; training artifacts live
  outside the repo (Colab/Modal notebooks), consumed at most as versioned model
  files with recorded hashes in VERSION_MANIFEST.
- Trust rule for models: model output is UNTRUSTED CONTENT — it may inform a
  CHALLENGE, never grant authority (mirrors UNTRUSTED_INSTRUCTION lab family).
- Secrets: any LLM API keys follow the `.env` SecretStr pattern (P2-S03/S04).

### Phase 4 — Protocol surfaces (MCP/UCP/AP2/ACP/x402)
- The buyer HTTP surface (`POST /buyer/propose|execute|callback`,
  `/buyer/status`) is the stable seam a protocol adapter would translate into
  protocol messages; the trusted executor/reducer remain the ONLY settlement
  authorities.
- Idempotency: protocol retries must map onto the existing ticket-derived
  idempotency + event-id dedup; adapters MUST NOT create new financial
  operations.
- Evidence: adapters append their own ledger events (pattern: M44 events) and
  never write attempt rows directly.

---

**STOP.** Per the master prompt, Phase 3 begins only upon explicit human
approval. Approved completion phrase applies to Phase 2:

> **Phase-2 Razorpay Test Mode integration complete.**
