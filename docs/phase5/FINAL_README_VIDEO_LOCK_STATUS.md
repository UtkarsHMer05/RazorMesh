# FINAL README + VIDEO TRUTH LOCK — Per-Gate Evidence Ledger (R001–R008)

**Pass:** the LAST bounded repository pass before the Buildathon video, 2026-09-01.
**Baseline:** start HEAD `fc37276` (Submission Lock complete).
**Scope discipline:** no phase, no redesign, no retrain, no frozen-eval rerun, no
recalibration, v2 never activated, nothing weakened, nothing pushed.
Evidence root: `docs/phase5/evidence/final-readme-video-lock/`.

| Gate | Status | Proof |
|---|---|---|
| R001 baseline | PASS | `r001-baseline/` — HEAD `fc37276`, clean tree, PRE_V2 active / v2 shadow-only NON-AUTHORITATIVE, the pre-fix demo response (structured lane minted a ticket then labeled it WITHHELD), README 15,979 B, 7 assets, 1,002 backend tests collected |
| R002 authority order | PASS | `r002-authority-order/` — demo rewritten to the pre-issuance evaluation seam; **ticket NOT ISSUED / attempt NOT CREATED / provider 0** with durable counts unchanged (live: tickets 386→386, attempts 148→148, calls 51→51); 7 tests; live + browser proof |
| R003 final numbers | PASS | Actual post-R002 regression: main **799 passed exit 0** · phase4 **203 passed exit 0** · live-ingress **13/13 exit 0** · vitest **35/35** · tsc clean · eslint 0 errors · build OK · security scan **PASS** · ruff/mypy clean; synced into README |
| R004+R005 README showcase | PASS | 17,409 B · 22 headings · 4 collapsible details · 1 valid Mermaid (Trusted Executor + Reconciliation, BLOCK→"Ticket NOT ISSUED") · nav row · video-link placeholder HTML comment (no fake URL) · 0 localhost links · 8/8 internal anchors resolve |
| R006 final screenshots | PASS | All 7 recaptured from the final build, content-verified at capture (01: 13/13 nodes + env badge + stop marker; 04: real `content_digest_mismatch` FAIL; 05: NOT ISSUED/NOT CREATED); 55–83 KB webp |
| R007 stale-claim scan | PASS | 16 banned phrases × README = 0 hits; "withheld" retained only where semantically correct (the pipeline's genuine issuance-prevention marker); no oversized binaries (assets 55–83 KB; corpus files are committed data by design) |
| R008 regression + rehearsal | PASS | 22-step browser rehearsal ALL PASS (below); hygiene re-verified |

---

## R002 — the semantic-demo authority gap (the core correction)

**Before:** the structured proof minted a real ExecutionTicket (via
`CheckoutService.authorize`), then the demo labeled the fused outcome "WITHHELD"
— conceptually wrong for the final authority story.

**After (production order, literally true):**

```
structured deterministic evaluation   REAL DecisionEngine.decide at the
        ↓                              pre-issuance seam (authorize() never called)
      ALLOW
        ↓
semantic verification                 REAL PRE_V2, canonical orientation
        ↓
      BLOCK   (p(contradiction) 0.9998)
        ↓
conservative fusion                  REAL fuse()
        ↓
      BLOCK
        ↓
DO NOT MINT ExecutionTicket          NOT ISSUED
        ↓
execution attempts = 0               NOT CREATED (durable count unchanged)
provider calls = 0                   unchanged
```

**Tests (7, all green):** real engine invoked; deterministic ALLOW; real PRE_V2 +
canonical orientation; engine-produced semantic probabilities; real fuse →
BLOCK; issuance function never called (NO DECISION_RECORDED / TICKET_ISSUED
audit events for the demo transaction, ZERO ticket rows for its intent);
ticket/attempt/provider counts unchanged; fresh transaction per run
(and fail-closed run mints nothing); frozen sets untouched.

**Browser truth (Security Lab card):**
`Structured RazorGuard ALLOW · Semantic BLOCK · Fusion BLOCK · ExecutionTicket NOT
ISSUED · Execution Attempt NOT CREATED · Provider calls 0` — no WITHHELD
wording, no mint claims.

## R008 — final 22-step rehearsal (all PASS)

1 preflight + warm-up → REQUIRED SYSTEMS READY ✓
2-4 buyer compile → confirm → agent search (3 candidates) ✓
5 merchant hidden-recurring mutation + diff on the same lineage ✓
6-13 execute boundary → real revalidation STALE_CHECKOUT (ticket_minted=false) ✓
14 provider calls = 0 (audit truth) ✓
15 audit read-only replay ✓
16 global chain verify CHAIN VALID over 2,789 events ✓
17 protocol-valid/intent-invalid → PROTOCOL_PASS → final BLOCK, provider false ✓
18 why semantic AI matters → ALLOW / BLOCK / BLOCK / NOT ISSUED / NOT CREATED / 0 ✓
19 safe path ✓
20 Razorpay Test order boundary (exactly-once, committed evidence) ✓
21 governance actual v2 shadow (canonical orientation, ignored for authority) ✓
22 AgentPay-X summary in canonical wording ✓

## Regression (exact, separate invocations — never one green run)

| Suite | Result |
|---|---|
| Backend main | **799 passed, exit 0** |
| Phase-4 acceptance | **203 passed, exit 0** |
| Live-ingress (isolated gate) | **13/13, exit 0** |
| Frontend | vitest **35/35** · tsc clean · eslint 0 errors · next build OK |
| Security | secret scan + pip-audit + pnpm audit **PASS 0 blocking** · ruff/mypy clean |

## GitHub presentation (recommended to the owner — NOT changed remotely)

- Description: *Zero-trust authorization infrastructure for agentic commerce —
  verifying human intent before AI-driven payments reach Razorpay.*
- Topics: razorpay, agentic-commerce, payment-security, ai-agents, zero-trust,
  mcp, payments, deberta, fastapi, nextjs, fintech
- Homepage: set to the final demo/video URL after upload
- License: none currently recorded in-repo (owner decision; prototype)

## Final acceptance token

```
RAZORMESH_FINAL_REPOSITORY_LOCK_PASS
/ README_SHOWCASE_FINAL
/ SEMANTIC_TICKET_BOUNDARY_REAL
/ VIDEO_READY
/ PRE_V2_ACTIVE
/ V2_REAL_SHADOW_NON_AUTHORITATIVE
```

Frozen rules honored: no retraining, no frozen-evaluation rerun, no
recalibration, v2 never activated, nothing pushed — the owner pushes manually.

**Development is stopped. Next action: RECORD THE BUILDATHON VIDEO.**
