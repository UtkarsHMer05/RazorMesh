# RazorMesh Trust

**Zero-Trust Authorization Infrastructure for Agentic Commerce**

> **Protocol validity is not transaction authority.**
>
> The AI proposes. RazorGuard authorizes. The trusted executor executes.

RazorMesh is a zero-trust authorization layer between autonomous commerce agents
and Razorpay. It verifies — immediately before any payment moves — that the
**exact current transaction still matches the human's confirmed authorization**
(Intent-to-Execution Integrity). A message being schema-valid, correctly
signed, authenticated, and replay-safe says nothing about whether the human
authorized *this* transaction.

Unofficial buildathon prototype. All payments run in **Razorpay Test Mode only** —
no real money, no production claims.

---

## The problem

AI agents can generate payment actions that are **technically valid but no longer
match human intent**: a hidden recurring membership, a swapped merchant, a mutated
quantity or amount, a currency change. No payment stack re-checks
intent-to-transaction fit at execution time. The agent's message will happily
pass every protocol check while draining a budget the human never approved.

## The solution

RazorMesh re-verifies the **exact** intent immediately before execution, twice:
deterministically (hard financial rules) and semantically (an NLI model that
reads the transaction evidence against the human authorization). Semantics can
only **tighten** — never loosen — a RazorGuard decision. The AI never holds
payment authority: money moves only through a short-lived, single-use,
context-bound ExecutionTicket redeemed by a trusted executor.

## Architecture

```text
Human authorization (confirmed)
  → AI agent
  → MCP / UCP / AP2 / ACP / A2A
  → Protocol Firewall          (schema, signature, replay, idempotency)
  → AgentCommerceIR            (normalized commerce intent)
  → deterministic RazorGuard   (hard financial rules)
  + SemanticVerifier           (active: PRE_V2 DeBERTa + semantic-thresholds-v3)
  → conservative fusion        (BLOCK > CHALLENGE > ALLOW; semantics only tighten)
  → ExecutionTicket            (context-bound, short-lived, single-use)
  → trusted executor
  → Razorpay Test Mode
  → webhook / reconciliation / tamper-evident audit ledger
```

## Model governance — demonstrated, not hidden

The **AgentPay-IR v2** fine-tuned model (13,605-row training corpus, frozen
val/test/human-gold/OOD splits) was trained and evaluated **exactly once** on
frozen, human-gold-anchored data as a *candidate*. The frozen safety gate
**rejected its activation** (`M2_FROZEN_EVALUATION_FAIL / V2_NOT_ACTIVATED`):
it improved in-distribution macro-F1 (0.737 → 0.975) but **worsened unsafe
contradiction→entailment on the security-critical sets** (human gold 2 → 7,
fresh OOD 5 → 6). The active runtime remains **PRE_V2**
(`phase3-finetuned-v2`, policy `semantic-thresholds-v3`).

This is the governance system working: a better-looking model was refused because
it was less safe. Full one-shot evaluation evidence:
`docs/agentpay_ir_v2/FINAL_FROZEN_EVALUATION.md`.

## Measured results

| Gate | Result |
|---|---|
| **AgentPay-X** adversarial policy benchmark | **191-scenario benchmark: 100% safe-pass and 100% attack-block at the policy gate, 0 false allows, 0 false blocks, 0 exactly-once violations** — with separate provider/exactly-once acceptance tests. Strict per-case granularity is 156/191; the other 35 cases carry **documented firewall-granularity differences** (e.g. a malformed-JSONRPC attack blocks at the consistency layer rather than the firewall) while meeting the headline rates. Not 191 literal live provider attacks. |
| Frozen evaluation (active PRE_V2 vs rejected v2) | see table below |
| Backend test suite | 992 collected, exit 0 (live DeBERTa runtime in the loop; run as separate targeted suites — never claimed as one invocation) |
| Live-ingress isolation suite | 13/13 in isolation (the full-suite run can flake 2–3 of these from cross-test DB interference — documented, rerun-in-isolation is the recorded gate) |
| Static/type gates | ruff clean, mypy clean (97 files), tsc/eslint 0 errors |
| Frontend | vitest 35/35, next build OK |
| Security scan | PASS — 0 findings |

Frozen evaluation, one-shot, hash-pinned sets (final test 2,227 · human gold 301
· fresh OOD 665):

| Dataset | Active PRE_V2 macro-F1 | v2 candidate macro-F1 | Unsafe C→E (PRE_V2 → v2) |
|---|---|---|---|
| Final test | 0.737 | 0.975 | 43 → 13 |
| Human gold | **0.893** | 0.776 | **2 → 7 (worse — rejected)** |
| Fresh OOD | 0.822 | 0.918 | **5 → 6 (worse — rejected)** |

### Razorpay Test Mode acceptance (measured live)

| Chain | Result | Provider calls |
|---|---|---|
| SAFE: authorization → checkout → ALLOW → ticket → executor | Razorpay Test **order created** (`order_TW16VWnXEVnDA6`) | **exactly 1** |
| Hidden recurring term (attack) | final BLOCK, p(contradiction) 0.99995 | **0** |
| Protocol-valid / human-intent-invalid (attack) | protocol PASS, final BLOCK | **0** |
| Ticket replay (expired) | 403 `TICKET_EXPIRED` | 0 |
| Ticket replay (immediate reuse) | idempotent same-attempt return | 0 additional |

Webhook verification, provider-state reduction, and reconciliation are covered by
48/48 permanent tests. **Honest limitation:** the in-browser checkout completion
(typing test-card details in the Razorpay Test modal) is a human sandbox step —
the Razorpay test sandbox declines every automated instrument on this account —
so the live evidence proves everything up to and including provider order
creation and all rejection paths, not a completed payment.

## The demo (under one minute)

1. **Valid purchase** (Buyer page): the human authorizes "under ₹30,000, new
   only, no subscription"; the checkout matches; ALLOW; ExecutionTicket issued;
   the trusted executor creates a Razorpay Test order — contacted exactly once.
2. **Recurring term the human never authorized** (Security Lab): protocol PASS,
   RazorGuard BLOCK, SemanticVerifier contradiction, final BLOCK, no ticket,
   **Razorpay never contacted**.
3. **A cryptographically perfect attack** (Security Lab): schema-valid,
   signature-valid, replay-safe message carrying 2 units against a ≤ ₹3,000
   authorization — protocol PASS, intent mismatch, final BLOCK, **Razorpay never
   contacted**. *Protocol validity is not transaction authority — proven live.*
4. **Why semantic AI matters** (Security Lab): the deterministic rules ALLOW a
   structured-clean transaction; the REAL active model reads the commerce
   evidence against the human authorization, finds the contradiction
   (p(contradiction) ≈ 0.9998) and BLOCKs through conservative fusion — ticket
   withheld, provider called zero times.
5. **Mission Control** (`/mission-control`): one transaction end-to-end — the
   13-stage pipeline moves only as far as the real evidence says, live
   authorization-vs-current diff, mutations/revert/execute on the CURRENT
   trace, read-only replay, and DEMO PREFLIGHT proving every component ready.
6. **Governance truth** (`/governance`): the actual rejected AgentPay-IR v2
   checkpoint runs live in a non-authoritative shadow (canonical NLI
   orientation: premise = commerce evidence, hypothesis = human authorization);
   even when it disagrees, authority stays with the active model alone.

**Pages:** `/buyer` (purchase flow) · `/mission-control` (presenter console:
13-stage live pipeline, current-transaction diff, real actions on the current
trace, DEMO PREFLIGHT readiness probes, read-only replay) ·
`/merchant` (offer sandbox — mutate a real checkout and watch the same trace
drift) · `/protocols` (playground: real packet mutations, real UCP
RFC 9421/9530 + AP2 ES256 signature verification, per-stage verdicts, cross-
protocol consistency) · `/security-lab` (attack demos, per-stage decisions,
**Why semantic AI matters** — the real model tightening an ALLOW into BLOCK) ·
`/audit` (forensics: search by trace/intent/checkout/attempt/order id,
tamper-evident anchors in the global chain, read-only replay, tamper test) ·
`/governance` (active vs challenger model truth + the REAL rejected v2
running non-authoritatively in shadow, canonical NLI orientation).

## Quick local run

```bash
docker compose up -d          # PostgreSQL 18 + Redis 8 (loopback-only)
make setup                    # backend deps + dev keys + frontend deps
make dev-api                  # FastAPI on 127.0.0.1:8000
pnpm --dir apps/web dev       # Next.js on :3000
make test                     # backend + frontend suites
```

Razorpay **Test Mode** credentials go in `.env` (never committed; see
`.env.example`); with no credentials a mock provider is used and the UI says so.
No LLM API keys are required.

## Documentation

`docs/submission/BUILDATHON_FINAL_EVIDENCE.md` (submission evidence pack) ·
`docs/submission/RAZORPAY_TEST_ACCEPTANCE.md` (acceptance chains) ·
`docs/agentpay_ir_v2/` (corpus, frozen evaluation, model governance) ·
`SECURITY.md` (invariants SEC-001..030) · `ARCHITECTURE.md` · `DECISIONS.md`
(append-only decision log).

---

*Unofficial prototype for the Razorpay Buildathon. Test Mode only; no real
money; no production claims.*
