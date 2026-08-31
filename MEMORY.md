# MEMORY.md — Compact Working Memory

## Purpose

This is a **rolling handoff file**, not a source of product requirements.

It exists so an AI coding agent can resume work without reconstructing the entire repository history.

It MUST stay compact, current and evidence-based.

It may never override `AGENTS.md`, `RULES.md`, `PRD.md`, `PHASES.md`, `SECURITY.md`, `ARCHITECTURE.md`, `DESIGN.md` or accepted decisions.

---

# Update policy

Update after every milestone.

Do not append forever.

Rewrite/compact stale operational details while preserving current facts.

Target: generally under 200 lines.

Never claim something passed unless `PHASE1_STATUS.md` contains the corresponding evidence.

---

# Current snapshot

**Project:** RazorMesh Trust
**State (2026-08-31):** `PHASE-5 DEEP ENGINE CORRECTION COMPLETE` →
`PHASE5_DEEP_ENGINE_CORRECTION_PASS / VIDEO_TRUTHFUL_AND_INTERACTIVE / PRE_V2_ACTIVE / V2_REAL_SHADOW_NON_AUTHORITATIVE`

- **AgentPay-IR v2: EVALUATED / NOT ACTIVATED.** Trained on the final corpus
  (13,605/2,261/2,227 + 301 gold; 96 injection rows TRAIN-only; bundle
  `28ea606b…`), artifact verified (candidate A_2ep, weights `f9e0007c…`), then
  evaluated EXACTLY ONCE on frozen test/gold/OOD. Result:
  `M2_FROZEN_EVALUATION_FAIL / V2_NOT_ACTIVATED` — unsafe C→E worsened on
  human gold (2→7) and OOD (5→6), gold macro-F1 0.893→0.776. The frozen
  safety gate did its job; evidence in
  `docs/agentpay_ir_v2/FINAL_FROZEN_EVALUATION.{md,json}` (decisions
  D-055/D-056). One-shot consumed: NEVER rerun frozen evaluation; never tune
  from those results.
- **Active semantic runtime:** backend `deberta` · model `phase3-finetuned-v2`
  (PRE_V2) · policy `semantic-thresholds-v3`. The v4 policy file exists on
  disk (val-only calibration) but is NOT wired.
- **AgentPay-X:** 191-scenario adversarial policy benchmark — 37 safe @100%
  pass, 154 attacks @100% block (BLOCK+CHALLENGE), 0 false-allow/block, 0
  exactly-once violations; per-case `passed` count is 156/191 (documented
  firewall-granularity differences on 35 cases). Exactly-once/provider
  execution is proven by SEPARATE acceptance tests, not by this benchmark.
- **Razorpay Test acceptance (live):** SAFE chain → provider order created
  EXACTLY once; attack chains → 0 provider calls; replay → 0 additional
  provider calls (403 TICKET_EXPIRED / idempotent same-attempt). Browser
  checkout completion remains a HUMAN sandbox step — never claim a completed
  payment. `docs/submission/RAZORPAY_TEST_ACCEPTANCE.md`.
- **Gates (final regression):** backend 813 collected exit 0 (live DeBERTa in
  loop); ruff/mypy clean; tsc/eslint 0 errors; vitest 18/18; next build OK;
  security_check PASS 0 findings.
- **Phase-5 deep-engine correction (G001-G030):** COMPLETE 2026-08-31, all 30 gates
  PASS with per-gate evidence (docs/phase5/DEEP_ENGINE_CORRECTION_STATUS.md).
  Real v2 challenger shadow (hash-verified A_2ep) now runs NON-AUTHORITATIVE
  in the governance panel; protocol/merchant/security/mission-control/audit
  surfaces all engine-truthful now. New modules: challenger_shadow.py,
  security_missions.py + TransactionBaseline table (migration
  a1b2c3d4e5f6). Storyboard Scenario-B wording corrected to protocol-PASS →
  intent-BLOCK. Evidence: PROVENANCE_INVENTORY.md + docs/evidence/
  PROTOCOL_TRUTH_TABLE.md. D-057 records the decision.
- **Next:** video recording + submission only.
- Remote: the agent never pushes; the human owner pushes manually
  (see `docs/agentpay_ir_v2/REMOTE_STATE.md`).
- Demo: Buyer (SAFE→Razorpay Test order), Security Lab (Scenario B recurring
  term, Scenario C protocol-valid/intent-invalid — both BLOCK, provider never
  contacted), Protocols (per-stage verdicts + semantic probabilities), Audit
  (readable timeline, chain verify, tamper test).

## HISTORICAL (superseded phases — kept as evidence, not current actions)

**Phase 4 (2026-08-27, SUPERSEDED):** `AUTONOMOUS_50_OF_50_PASS /
AWAITING_FINAL_HUMAN_ACCEPTANCE` at the time; M49 gates then: pytest 718/718,
vitest 76 PASS, AgentPay-X canonical gate green. Its single final human gate (one prepared
Razorpay Test transaction) was later executed and superseded by the post-colab
acceptance above.

**AgentPay-IR v2 PRE-REVIEW FINAL CORRECTION (2026-08-29, SUPERSEDED):**
`PRE_REVIEW_FINALIZATION_PASS / SAFE_TO_BEGIN_HUMAN_LABELING` — V3 review pack
(635 cards `rc2_*`, 301 gold / 334 supervised, group-level roles, vitest+
Playwright leak tests), finalizer with group-level gold isolation, byte-
deterministic Colab bundle + external-hash notebook, OOD expanded 401→665,
PVB008 template robustness (prompt-injection 13/15 = recorded defect for v2
training), deberta_v2 honors semantic_model_path_v2, /reviewer gated by
RAZORMESH_REVIEWER_ENABLED=1, agent-control docs untracked+gitignored. Human
review then completed (AI-assisted, owner-accepted — provenance disclosed in
docs/agentpay_ir_v2/STATUS.md) and the final freeze was produced.

**Phase-3 correction (D-053, 2026-08-28, SUPERSEDED):** frozen_v2 corpus,
canonical orientation (premise=evidence, hypothesis=authorization), runtime
artifact `phase3-finetuned-v2` (sha `163864e0…`, label map 0=C/1=E/2=N), policy
`semantic-thresholds-v3` (tau 0.05/0.9, frozen_v2 val ONLY), backend `deberta`
production default; torch 2.13.0 + transformers 5.15.1 in the OPTIONAL uv group
`semantic`; no-torch envs fail CLOSED to CHALLENGE (never keyword fallback);
per-process singleton load + manifest-hash enforcement; keyword verifier only
as the labeled `deterministic_test_stub`; `make` targets use `--group semantic`.
Orientation diagnostic RETRAIN_REQUIRED=YES; perf: cold 0.61s, p50 51.9ms,
p95 65.1ms, RSS 792MiB.

**Phase-3 re-audit (2026-08-27, SUPERSEDED):** implementation/evidence defects
were found and repaired (M15); the prior-state numbers further below remain
historical evidence, not current claims.

# Environment facts (verified M01/M02)

- macOS 26.5, arm64, Apple M2, 8 GB RAM, 168 GiB free disk.
- Node v22.23.2 LTS installed + default via nvm (v20 EOL). npm 10.9.8, pnpm 10.18.2.
- uv 0.12.5 installed (~/.local/bin/uv). Python 3.13.15 is uv-managed and pinned in `services/api/.python-version`.
- Docker 29.7.2 + Compose v5.4.0; daemon launched on demand at M09 (approved).
- User's own non-Docker PostgreSQL occupies 127.0.0.1:5432 — DO NOT TOUCH. Our Docker PG binds 127.0.0.1:15432.
- Infra live: razormesh-postgres (18.6-alpine @127.0.0.1:15432, vol pgdata, PG18 mounts /var/lib/postgresql) + razormesh-redis (8.8.2-alpine @127.0.0.1:16379, no persistence by design — coordination only).
- Ports 3000/8000 free. All host bindings loopback-only.
- Repo: complete Phase-1 modular monolith on `main` (GitHub main kept in sync by
  the HUMAN outside the agent; the agent pushes only with explicit authorization.

# Version decisions (M02, full detail in VERSION_MANIFEST.md)

- fastapi 0.141.1 / pydantic 2.13.4 / sqlalchemy 2.0.52 / alembic 1.19.1 / psycopg[binary] 3.3.4
- redis-py 8.1.0 / cryptography 50.0.0 (Ed25519) / rfc8785 0.1.4 (JCS) / httpx 0.28.1 / httpx2 2.12.0
- pytest 9.1.1 + asyncio 1.4.0 + hypothesis 6.165.10 + ruff 0.16.4 + mypy 2.3.1
- next 16.3.2 / react 19.2.8 / typescript 5.9.3 / eslint 9.39.5 (dev-only compatibility exception)
- vitest 4.1.11 + RTL 16.3.2 + jsdom 26.1.0 compatibility pin + @playwright/test 1.62.1
- postgres:18.6-alpine, redis:8.8.2-alpine; Blade NOT selected (D-022) → fallback tokens

---

# Product in one sentence

RazorMesh Trust verifies that a proposed agentic-commerce transaction still matches the human's confirmed authorization before a trusted executor may perform a payment-like side effect.

---

# Core invariants to remember

- AI/buyer proposes; RazorGuard authorizes; trusted executor executes.
- No valid ticket → no provider execution.
- PostgreSQL durable authority; Redis coordination only.
- Money = integer minor units.
- ALLOW / CHALLENGE / BLOCK.
- Execution tickets are context-bound and single-use.
- Spend = authorized/reserved/committed.
- Unknown provider outcome is not blindly retried.
- Checkout is revalidated before execution.
- Audit is append-oriented and tamper-evident.
- Phase 1 uses a mock provider only; Phase 2 permits Razorpay Test Mode only.

---

# Proven state

- IDs: 12 typed ULIDs validated (M15)
- Money: minor-unit invariants, no float, Hypothesis properties (M16)
- Intent: frozen contract with generation/expiry/currency invariants (M17)
- Checkout: server recomputed totals, mixed-currency and tampering rejected (M18)
- Provenance: UNTRUSTED_CONTENT cannot satisfy authority gates (M19)
- DB: 9 tables, 3 Alembic revisions; execution-ticket uniqueness and spend-capacity constraints; latest downgrade/upgrade verified (M20 + final audit)
- DAL: repos + FOR UPDATE row lock, concurrency overspend guard (M21)
- Catalog: 5 merchants/50 products seeded idempotently+atomically; IDs must be ULIDs (M22)
- API: read-only /catalog endpoints, bounded pagination, typed-ID path params (M23)
- State machine: 7 statuses, exhaustive matrix tested, only AUTHORIZED executable (M24)
- Evidence ledger: JCS+SHA256 hash chain, advisory-lock appends, tamper detection (M25)
- Authz hashing: JCS canonical projections; untrusted text provably excluded (M26)
- Rule engine: PASS/FAIL/UNKNOWN rules + combinators; crash -> UNKNOWN fail-closed (M27)
- Money rules: 6 rules, inclusive boundaries, budget counts reserved+committed (M28)
- Catalog rules: allowlists + trusted ProductFacts; unknown fact -> UNKNOWN (M29)
- Policy rules: recurring/expiry hard fails; approval threshold -> APPROVAL_REQUIRED UNKNOWN (M30)
- SpendManager: atomic reserve/commit/release, row-locked, concurrency-proven (M31)
- Decision engine: state gate + FAIL->BLOCK + UNKNOWN->CHALLENGE else ALLOW (M32)
- Dev keys: Ed25519 at infra/keys/ (gitignored), ensure/load/sign/verify (M33)
- Tickets: signed JCS claims; verify sig->expiry->11 bindings fail-closed (M34)
- Nonce: Redis SET NX EX claim, 20-worker race proven 1 winner (M35)
- Executor: sole provider caller; verifies durable intent/checkout/current ALLOW before post-auth reservation; signed-ticket-derived idempotency; atomic settlement; unknown keeps reservation (M36 + D-027/D-028)
- Mock provider: 7 scripted modes incl. timeout-after-success + event replay (M37)
- Checkout service: server-authoritative item/tax/fee/shipping/currency/recurring projection; persisted constraints enforced; propose+authorize+ticket flow (M38)
- Revalidation: full intent constraints and checkout projection rebuild from DB at executor boundary; drift blocks, cosmetics don't (M39)
- Untrusted boundary: hostile text inert end-to-end; authority slots protected (M40)
- Semantic seam: Null + deterministic keyword verifier; UNDECIDED fail-closed (M41)
- Scenarios: 16 families schema-validated; expected labels isolated (M42 + final audit)
- Runner: all 16 isolated real-pipeline scenarios pass; no unrelated-data wipe (M43)
- Benchmark: 14 pairs TP14 FP0 TN14 FN0, unsafe-execution 0, synthetic GMV labelled (M44)
- Buyer API/UI: POST /buyer/* flow live-E2E verified; replay collapses idempotently (M45)
- Security Lab: /security-lab/run executes suite server-side with evidence tail (M46)
- Audit dashboard: timeline/verify/state plus non-mutating tamper simulation; event count/chain remain unchanged (M47 + D-029)
- Deep gate: 225 tests at 93.25% coverage, stateful/concurrency/security properties; security audits clean; frontend build/test/E2E green (M48 + final audit)
- Perf baseline: `docs/PHASE1_PERFORMANCE.json` regenerated on Python 3.13.15 and the 14-pair pipeline (M49)
- Acceptance: documented fresh-volume M50 run plus final live `scripts/acceptance.py` 10/10 PASS; security lab 16/16 and benchmark 14 pairs (M50 + final audit)

---

# Active blockers

None. The post-colab buildathon acceptance is complete; all gates green
(backend 813 exit 0, AgentPay-X canonical gate green, security scan PASS). Next
actions are
submission/release only; Phase 5 NOT STARTED.

Carried forward (historical observations, unchanged from prior audit):
- `services/api/scripts/*` and `services/api/training/phase3/*` ruff drifts.
- 4 pre-existing E2E failures in `e2e/gold-reviewer.spec.ts` (unchanged;
  2026-08-28 additionally repaired the stale checkout E2E locators for the
  auto-create fixture-intent UI: checkout.spec 3/3; the one-off
  `e2e/snapshot.spec.ts` capture utility (self-described, not a regression
  test) fails on mobile fullPage screenshot in this environment).
- Historical Phase-3 re-audit observations preserved above remain valid
  as prior-state evidence; they are not retroactively retracted by Phase 4.

Historical Phase-3 audit notes (kept intact per existing-file protection):
- Concurrent Phase-4 changes previously broke whole-worktree gates; resolved
  by ruff per-file-ignores for `protocol/*_proof.py`, `agentpay_x.py`,
  `untrusted_agent.py`, and `training/*`.
  - Confirmation discards merchant/semantic/product restrictions; confirmed AI
  authority is not connected to buyer checkout; browser IDs are invalid ULIDs
  (FIXED 2026-08-28: IntentDraftPanel now generates Crockford-base32 ULIDs via
  genUlid() instead of UUIDv4; product list dynamically filtered by confirmed
  draft's max_amount + product_summary constraints with budget-only fallback;
  e2e compile+confirm+checkout+pay verified with real TokenRouter API).
- Production checkout never ran the Phase-3 evidence/verifier/fusion stage
  in the prior state; M43 UI evidence was unreachable. (Phase 4 did not
  modify Phase-3 logic; this remains a prior-state observation.)
- 320 reviewed IDs = 241 train + 43 validation + 36 test. Validation
  influenced training selection/calibration; D-050's untouched-79 assertion
  is historically false. Independent human-reviewed evaluation remains a
  prerequisite for any final claim.
- M37 entailment calibration, M38 artifact/probability validation, M39
  invented condition, M45 real-pipeline/metric semantics and M46 ablations
  historically needed repair.
- Historical distributed training ZIPs disagree with repaired directory deps.

---

# Human-owned inputs

- No external API keys should be needed in Phase 1.
- Git push/remote changes require explicit human authorization.

---

# Active decisions

See `DECISIONS.md`. D-046 cited the examined 79-card subset during selection;
D-050's later claim that this subset was untouched by selection/calibration is
unsupported. D-051's full-307 coverage is real, but its unconditional M48/M50
closure and perfect numeric-precision claim are not established. Audit evidence
supersedes those current-acceptance claims; historical entries remain intact.
Duplicate D-047/D-048 IDs exist for later UI/Phase-4 entries; identify entries
by title as well as ID until the governance collision is separately reconciled.

---

# Known technical debt

- ESLint 9.39.5 is EOL but retained as a dev-only compatibility exception because the current Next 16.3.2 plugin stack crashes under ESLint 10.9.0. Re-test when upstream peers add v10 support.
- Benchmark safe controls are synthetic fixture twins; metrics must never be generalized beyond the recorded suite.
- Failed Razorpay payments conservatively retain reservation capacity while a late capture remains possible; Phase 2 has no automated terminal-release workflow because elapsed time alone is not provider truth.

---

# Next action

PRE-REVIEW FINAL CORRECTION PASS complete (2026-08-29). The ONE current handoff
workflow (docs/agentpay_ir_v2/STATUS.md is authoritative):

1. Human opens http://localhost:3000/reviewer (dev server with
   RAZORMESH_REVIEWER_ENABLED=1, already in .env) and labels ALL 635 cards of
   data/agentpay_ir_v2/review/REVIEW_PACK_V3.jsonl.
2. Human clicks "Export decisions JSON".
3. Run `services/api/.venv/bin/python scripts/rzp_finalize_review_v2.py --decisions
   <exported.json>` → validates/conflict-checks, group-level gold isolation,
   human-gold freeze (GOLD_FROZEN_V3.jsonl), corpus/final train/val/test, leakage
   gates, FINAL bundle + notebook rebuild.
4. Upload the FINAL artifacts/agentpay_ir_v2_colab_training_bundle.zip to
   notebooks/RazorGuard_NLI_AgentPayIR_v2_Training.ipynb (T4/L4), run top-to-bottom.
5. Place returned agentpay-ir-v2-finetuned.zip in artifacts/models/incoming/ and
   tell the agent "v2 artifact uploaded" → POST_COLAB_RESUME (validation-only
   calibration, one-shot test/gold/OOD eval, deberta_v2 wiring, full regression).

OVN047 payment completion remains BLOCKED_EXTERNAL (sandbox checkout). No push
authorization.

Historical Phase-3 re-audit queue remains preserved above as
prior-state evidence; it is not the current active queue.

Standing notes: `make test-db` must re-provision razormesh_test after
any `docker compose down -v` (migrate alone does NOT create it). The
fine-tuned model lives at `artifacts/models/incoming/phase3-finetuned/`
(zip sha256 54d0fa01…f1e24). Eval scripts: `rzp_eval_finetuned.py`
(M36), `rzp_calibrate_thresholds_finetuned.py` (M37),
`rzp_run_e2e_benchmark.py` (M45 — already swapped to the artifact).
Verifier at `services/api/src/razormesh_api/semantic_verifier.py` —
label_map read from `model_dir/label_map.json` (or policy manifest
fallback, or legacy C/E/N fallback). Policy manifest
`data/phase3/policy/semantic_thresholds.json` is v2 with
gold_validation_status=GOLD_VALIDATED (historical value; validity disputed by
this audit, not a current acceptance assertion).

---

# Resume protocol

On resume:

1. read `AGENTS.md`;
2. read current source-of-truth docs;
3. inspect `PHASE1_STATUS.md`;
4. verify the latest PASS gate if any;
5. continue the first NOT_STARTED/BLOCKED milestone only after understanding the blocker.
