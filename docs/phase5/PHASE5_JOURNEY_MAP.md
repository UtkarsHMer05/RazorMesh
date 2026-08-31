# PHASE5_JOURNEY_MAP.md — M002 Current Browser Journeys (frozen baseline)

Every judge-facing click/API from Buyer through Razorpay, Protocol live run, Security suite,
Audit lookup and Merchant. Classification key:

- **DB** — value derived from durable Postgres state via backend
- **backend-derived** — computed by backend at request time (decision, signature, hash)
- **provider-derived** — derived from payment provider (Razorpay test / mock)
- **fixture** — static synthetic constants embedded in fixtures
- **static** — hardcoded frontend copy/data

## Route inventory (apps/web/src/app)

| Route | File | Purpose |
|---|---|---|
| `/` | page.tsx + _components | Landing (static marketing, no APIs) |
| `/buyer` | buyer/page.tsx (522L) + IntentDraftPanel.tsx | Checkout flow |
| `/merchant` | merchant/page.tsx (100L) | Read-only catalog table |
| `/protocols` | protocols/page.tsx (704L) + types.ts | Gateway inspector + live runs |
| `/security-lab` | security-lab/page.tsx (280L) | Scenario registry + demo scenarios |
| `/audit` | audit/page.tsx (345L) | Event timeline + chain verify + tamper |
| `/reviewer` | reviewer/page.tsx | Owner-only semantic review UI (gated) |

## Buyer journey (validated in browser 2026-08-30)

| Step | Action | API | Classification |
|---|---|---|---|
| Load | page mount | `GET /catalog/products?limit=100` | DB (52 products) |
| Load | page mount | `POST /buyer/fixture-intent` | backend-derived (creates fixture authorization `intent_...`) |
| Type mandate | textarea + Compile | `POST /buyer/intent-drafts/compile` | backend-derived (TokenRouter compile; draft id; hard/semantic constraints; **provider/model name currently exposed — fix in M020/M021**) |
| Confirm | Confirm authorization | `POST /buyer/intent-drafts/{id}/confirm` | backend-derived (CONFIRMED state; audit event) |
| Choose product | radio list | — (client) | DB-backed options |
| Propose | Propose checkout | `POST /buyer/propose` | backend-derived (server-recomputed total, RazorGuard decision, signed single-use ticket on ALLOW) |
| Pay | Pay securely | `POST /buyer/execute` | backend-derived (execution attempt + provider launch payload — key/order from backend) |
| Modal | checkout.js | `https://checkout.razorpay.com/v1/checkout.js` | provider-derived |
| Result | handler | `POST /buyer/callback` | backend + provider-derived (signature-verified) |
| Resync | ondismiss / Refresh | `GET /buyer/status?intent_id&checkout_id` | backend-derived |

Observed browser result (Sony WH-1000XM5 ×1): ALLOW, total ₹4,799.00, ticket bound.
Observed compile: DRAFT → hard constraints JSON (max_amount 500000 minor INR, brand Sony, recurring_forbidden) → CONFIRMED on click.

**Known defect (owner-reported, §8):** payment failure leaves modal open + stale EXECUTING; dismiss vs failure vs success states ambiguous → fix mandated by M095–M100.

## Merchant journey

| Step | Action | API | Classification |
|---|---|---|---|
| Load | page mount | `GET /catalog/merchants?limit=100` + `GET /catalog/products?limit=100` | DB |

No other interaction exists. Entire page is read-only (static presentation of DB rows).
**Gap:** no mutation surface at all — Merchant sandbox must be built (M036+).

## Protocols journey (validated in browser)

| Step | Action | API | Classification |
|---|---|---|---|
| Load | mount | `GET /api/phase4/acceptance/runs` → backend `GET /phase4/acceptance/runs` | backend-derived (in-memory registry, DB intents) |
| Static sections | — | none | **static/fixture** (labeled "Sample data — fixture snapshot... not a live run") |
| Trigger live run | button | `POST /api/phase4/acceptance/prepare` (via proxy) → backend prepare (real MCP+UCP+AP2+ACP+A2A chain, firewall, IR, consistency, RazorGuard, semantic) | backend-derived |
| 409 rejected | rendered as rejection card with per-stage verdicts (D-056) | same endpoint | backend-derived |
| Finalize | button (PREPARED runs) | `POST /api/phase4/acceptance/finalize` (reauthorize + execute + order via provider) | backend + provider-derived |

Observed: live run acc-...9cb6cc67 → COMPLETED/MATCH/ALLOW (protocol PASS, sig verified, semantic p(entail) 0.999); finalize → COMPLETED with audit receipt. Registry is **in-memory** (lost on restart) — trace persistence design in M004 must not depend on it.

## Security Lab journey (validated in browser)

| Step | Action | API | Classification |
|---|---|---|---|
| Load | mount | `GET /security-lab/scenarios` | backend-derived registry (22 scenarios) |
| Run suite | Execute scenario suite | `POST /security-lab/run` | backend-derived (real pipeline vs mock provider) |
| Scenario B | button | `POST /phase4/acceptance/demo/scenario-b-semantic-violation` | backend-derived (D-056 full-evidence rejection) |
| Scenario C | button | `POST /phase4/acceptance/demo/scenario-c-protocol-valid-intent-invalid` | backend-derived |

Observed Scenario B: PROTOCOL_PASS → RazorGuard BLOCK (RECURRING_NOT_ALLOWED) → semantic BLOCK p(contra) 1.0000 → fused BLOCK → ticket no → Razorpay no. Exactly the §13.5 attack-movie skeleton with real evidence.

## Audit journey (validated in browser)

| Step | Action | API | Classification |
|---|---|---|---|
| Load | mount | `GET /audit/timeline?limit=50` | DB (hash-chained events) |
| Verify | Verify hash chain | `GET /audit/verify` | backend-derived (walks chain: 1073 events VALID at probe time) |
| Inspect intent | text input | `GET /audit/state/{intent_id}` | DB |
| Tamper sim | button | `POST /audit/tamper-test` | backend-derived (non-mutating simulation) |

**Gap:** search accepts only exact intent_id; no trace-level grouping; dense event wall primary UX → M079+.

## Cross-cutting API classification notes

1. `POST /buyer/fixture-intent` creates a **fixture authorization** — synthetic, clearly a demo input. All fixture scenarios are labeled test/synthetic in UI.
2. Protocol page static snapshot sections are explicitly labeled "Sample data — fixture snapshot from the Phase-4 proof harness, not a live run" (truthful static).
3. AgentPay-X tiles on /protocols are static regression results (labeled); canonical run gate is the pytest suite; UI must not present them as live traffic (M074 keeps this).
4. No SSE/websocket endpoints exist. Live updates today require manual re-fetch (M012 fixes with bounded polling or SSE).
5. No merchant-mutation, protocol-mutation, ranking, trace, mission-control endpoints exist — all to be added in Phase 5.
6. `/reviewer` is owner-only (RAZORMESH_REVIEWER_ENABLED=1) — never part of judge flow; its APIs must never be linked from demo pages.
7. Money rendering: backend minor units → frontend format ₹4,799.00; server-recomputed totals confirmed in browser.

## Missing transitions for the judge story (feeds M003)

- Buyer has no visible agent-search/ranking (it's a radio list) — M025–M029.
- No cross-page trace continuity (IDs are opaque per-page) — M009–M016.
- No merchant mutation → drift detection movie — M036+.
- No protocol mutation/attack controls — M050+.
- Security Lab shows tables, not an animated pipeline movie — M063+.
- Audit lacks search-by-trace, timeline, diff, provider card — M079+.
- Payment failure lifecycle bug — M095+.
- No Mission Control — M101+.
