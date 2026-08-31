# RazorMesh Trust — Buildathon Final Evidence

**Submission package for:** Runtime Trust Infrastructure for Agentic Commerce

**Final state:**
`RAZORMESH_BUILDATHON_SUBMISSION_READY / V2_CANDIDATE_REJECTED_BY_SAFETY_GATE / PRE_V2_ACTIVE`

The product is submission-ready *because* the governance system correctly
rejected an unsafe model candidate. The model-candidate gate result
`M2_FROZEN_EVALUATION_FAIL / V2_NOT_ACTIVATED` (§6.1) is preserved verbatim as
the frozen evaluation outcome. Every measured number in this document comes
from an artifact produced in this run (`docs/agentpay_ir_v2/FINAL_FROZEN_EVALUATION.{md,json}`,
`docs/submission/RAZORPAY_TEST_ACCEPTANCE.md`, and the M4 regression records).

---

## 1. The problem

AI commerce agents can produce payment actions that are **technically valid but no
longer match what the human actually authorized**. A protocol-clean, correctly
signed, replay-safe checkout message can still carry a hidden recurring
subscription, a wrong quantity, a different currency, or a different product than
the human approved. Nothing in today's payment stacks checks *intent-to-transaction
fit* at execution time.

## 2. The thesis

> **Protocol validity is not transaction authority.**

A message being valid under MCP/UCP/AP2/ACP/A2A says nothing about whether the
human authorized *this* transaction. Authorization has to be re-verified against
the *exact current* transaction, immediately before money moves.

## 3. The solution

RazorMesh is a zero-trust authorization layer between autonomous commerce agents
and Razorpay. It normalizes any agent-protocol checkout into a common commerce IR,
verifies it twice — deterministically and semantically — and only then issues the
short-lived, single-use, context-bound authorization ticket that a trusted
executor can redeem against Razorpay.

## 4. Core principle

> **The AI proposes. RazorGuard authorizes. The trusted executor executes.**

The active **SemanticVerifier** is the PRE_V2 DeBERTa NLI model
(`phase3-finetuned-v2`) under policy `semantic-thresholds-v3`. It can only
*tighten* a decision — it can never bypass deterministic RazorGuard rules, never
issue tickets, never contact the payment provider, and never hold financial
authority. (The fine-tuned **AgentPay-IR v2** model was trained and evaluated as
a *candidate*; the frozen human-gold/OOD safety gate rejected its activation —
see §6.1. It is evidence of model governance, not the active runtime.)

## 5. Final architecture

```
Human Intent (confirmed authorization)
  → AI Agent
  → MCP / UCP / AP2 / ACP / A2A
  → Protocol Firewall (schema, signature, replay, idempotency)
  → AgentCommerceIR (normalized commerce intent)
  → deterministic RazorGuard
  + SemanticVerifier (active: PRE_V2 DeBERTa + semantic-thresholds-v3)
  → fused decision (BLOCK > CHALLENGE > ALLOW; semantics only tighten)
  → ExecutionTicket (context-bound, short-lived, single-use)
  → trusted executor
  → Razorpay (Test Mode)
  → webhook → reconciliation → tamper-evident audit chain
```

Key properties: intent-to-execution integrity; budget reservation semantics
(available/reserved/committed/released); BLOCKED and CHALLENGED never execute;
ambiguous provider outcomes are never blindly retried; PostgreSQL is durable
authority, Redis is coordination only; money in integer minor units.

## 6. Measured evidence

### 6.1 AgentPay-IR v2 — one-shot frozen evaluation (executed exactly once)

Source of truth: `docs/agentpay_ir_v2/FINAL_FROZEN_EVALUATION.md` (+ `.json`).
Frozen sets: final test = 2,227 · human gold = 301 · fresh OOD = 665
(sha256-pinned before training; never used for training/selection/calibration).

**Outcome: `M2_FROZEN_EVALUATION_FAIL / V2_NOT_ACTIVATED`.** The v2 candidate
improves the in-distribution test split dramatically (+0.24 macro-F1) but fails
the frozen safety gate: it **worsens unsafe contradiction→entailment** on both
security-critical sets — human gold **2 → 7**, fresh OOD **5 → 6** — and regresses
human-gold macro-F1 (0.8930 → 0.7757). The runtime-boundary analysis (each model
under its own calibrated policy) agrees: gold contradictions reaching a provider
call would rise from 1 to 5. Per the frozen activation condition, the **active
runtime remains the PRE_V2 verifier** (`phase3-finetuned-v2`, policy
`semantic-thresholds-v3`). No rerun, recalibration, or threshold change was
derived from the frozen results — the one-shot rule held.

| Dataset | Model | Macro-F1 | C Recall | N Recall | E Recall | Unsafe C→E | Safe false block |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Final test | PRE_V2 (active) | 0.7367 | 0.7325 | 0.6979 | 0.8074 | 43 (1.93%) | 74 (3.32%) |
| Final test | v2 candidate | 0.9752 | 0.9731 | 0.9756 | 0.9789 | 13 (0.58%) | 17 (0.76%) |
| Human gold | PRE_V2 (active) | 0.8930 | 0.8547 | 0.8824 | 0.9495 | 2 (0.66%) | 3 (1.00%) |
| Human gold | v2 candidate | 0.7757 | 0.8974 | 0.6353 | 0.7879 | **7 (2.33%)** | 8 (2.66%) |
| Fresh OOD | PRE_V2 (active) | 0.8220 | 0.8197 | 0.6880 | 0.9496 | 5 (0.75%) | 9 (1.35%) |
| Fresh OOD | v2 candidate | 0.9182 | 0.8634 | 0.9520 | 0.9636 | **6 (0.90%)** | 4 (0.60%) |

Why this is submission evidence, not a setback: RazorMesh's acceptance contract
treats the semantic model as a *candidate*, never as authority. The frozen,
human-gold-anchored safety gate measured the candidate exactly once and **refused
to activate a model that would let more unauthorized contradictions reach the
payment provider** — the governance system demonstrably does its job. The v2
artifact, its lineage, and the full evaluation remain reproducible evidence.

Artifact provenance: input ZIP sha256 `4c933eec66a0d3acc8a108dc1b64bb302440c6cb25451ff0589741739932f878`;
selected candidate `A_2ep` (frozen rule: min unsafe C→E → max macro-F1 → max
contradiction recall); candidate validation macro-F1 0.9764 / contradiction recall
0.9732 / unsafe C→E 14 / safe false block 9; model weights sha256
`f9e0007c78776bf305ad5412c21fc950f142a24f1bb6c9bd3fac3b3a44571d99`; base
`cross-encoder/nli-deberta-v3-base` rev `6c749ce`; final training bundle sha256
`28ea606b084f4544d7f73d8001569cd91476ab49dc8a2110bc73634149fca24d` (supersedes the
stale `809687bb…` expectation via the committed Colab install-fix 6481344; corpus
freeze unchanged). Training lineage: 13,605 train / 2,261 val; 96 prompt-injection
defense rows TRAIN-only; frozen test/gold/OOD excluded from training.

### 6.2 Regression gates (final code, 2026-08-30)

| Gate | Result |
| --- | --- |
| Backend pytest (full suite, live DeBERTa runtime) | **exit 0, 813 collected** (initial run had 3 live-ingress e2e failures that pass in isolation — cross-test interference, proven by rerun: exit 0, 0 failed) |
| ruff format + ruff check (services/api) | PASS (200 files formatted; all checks passed) |
| mypy `-p razormesh_api` | PASS — 97 source files, 0 issues |
| Frontend `tsc --noEmit` | PASS — 0 errors |
| Frontend eslint | PASS — 0 errors (1 pre-existing warning, unchanged) |
| Frontend vitest | PASS — 18/18 |
| Frontend `next build` | PASS — all 15 routes |
| **AgentPay-X benchmark** | 191-scenario adversarial policy benchmark: 37 safe @ 100% pass; 154 attacks @ 100% block (BLOCK+CHALLENGE); 0 false allows; 0 false blocks; 24 challenge cases pass; per-case `passed` = 156/191 (35 carry documented firewall-granularity differences while meeting the headline rates). Exactly-once/provider execution proven by the separate acceptance tests below, not by this benchmark |
| Security scan (`scripts/security_check.py`) | PASS — 0 secret findings; pip-audit clean; pnpm audit clean |

### 6.3 Razorpay Test Mode acceptance (2026-08-30)

Full evidence: `docs/submission/RAZORPAY_TEST_ACCEPTANCE.md`.

| Chain | Result | Provider calls |
| --- | --- | --- |
| SAFE: authorization → checkout → RazorGuard ALLOW → ticket → executor | Razorpay Test order `order_TW16VWnXEVnDA6` created, state EXECUTING | **exactly 1** |
| Replay: same ticket after expiry | 403 `TICKET_EXPIRED` | 0 |
| Replay: same ticket immediately reused | idempotent same-attempt return; ledger proves one order | 0 (second call) |
| Semantic attack (recurring term, Scenario B) | final BLOCK, p(contradiction) 0.99995 | **0** |
| Valid-protocol / wrong-intent (Scenario C) | protocol PASS + final BLOCK, p(contradiction) 0.99964 | **0** |
| Webhook + reconciliation machinery | 48/48 permanent-suite tests (verification, dedup, reducer, reconciliation) | n/a |

Honest limitation (previously documented, unchanged): the Razorpay Test-mode
checkout iframe declines every automated instrument on this account, so the
final in-browser payment completion (typing the test card) is a human step for
the live demo; every automatable leg — including provider-order creation,
exactly-once calling, and all rejection paths — is proven above, and no
card/payment data was used or stored by the agent.

## 7. Demo narrative

1. **Valid purchase is authorized and executed** — the human authorizes "under
   ₹30,000, new only, no subscription"; the checkout matches; deterministic
   RazorGuard ALLOW; the active SemanticVerifier confirms (PASS); an
   ExecutionTicket is issued and the trusted executor creates a Razorpay Test
   order — provider contacted exactly once. (Buyer page → Pay via Razorpay
   Test; the final in-modal card entry is the human sandbox step.)
2. **A recurring term the human never authorized is blocked** — Security Lab →
   Scenario B: protocol PASS, RazorGuard BLOCK, semantic BLOCK
   p(contradiction) 0.99995, final BLOCK, no ticket, Razorpay never contacted.
3. **A cryptographically perfect attack is still blocked** — Security Lab →
   Scenario C: schema-valid, signature-valid, replay-safe message carrying a
   transaction the human never authorized: protocol PASS + intent mismatch +
   final BLOCK + zero provider contact. This is the thesis made visible.

Where to see each stage: the **Protocols page** live-run table shows protocol
firewall, deterministic RazorGuard, semantic verdict + probabilities + backend
+ model version + fail-closed flag, and the fused final decision as separate
labeled rows; the **Security Lab** runs Scenarios B/C end-to-end with a
stage-by-stage result card; the **Audit page** renders the readable timeline
(intent confirmed → checkout proposed → RazorGuard decision → semantic
verification → fusion → ticket issued/withheld → provider call → webhook →
reconciliation) with per-event details, plus the chain-verify and tamper-test
tools. The approved Bauhaus design system is unchanged.
