# PHASE3_STATUS.md — Phase-3 AI/ML Trust Layer Evidence

## Status rules

- Valid states: `NOT_STARTED`, `IN_PROGRESS`, `PASS`, `BLOCKED`, `HUMAN_GATE`.
- PASS only with recorded acceptance evidence below.
- Human gates per master prompt §15: gold review (M26), Colab training (M34),
  conditional compute (only if justified), Phase-4 approval (after M50).
- Secrets are never recorded here — only PRESENT/ABSENT markers.
- AI components may propose; RazorGuard authorizes; trusted executor executes
  (P3-S01..S20 in SECURITY.md).

| # | Milestone | Status | Evidence summary |
|---|---|---|---|
| M01 | Repository, governance, secret-safety inspection | PASS | master prompt read fully; governance set read in AGENTS.md precedence; git tree clean on main @fc0422e (+P2-M50 final check); `.env` ignored (.gitignore:6, mode 600); bootstrap file untracked→locally excluded via .git/info/exclude:49, zero history entries; no TokenRouter refs in tracked source; full backend regression 375/375 (one transient scheduling flake in 20-worker race noted → M02 watch); PHASE3_STATUS skeleton created |
| M02 | Full Phase-1/2 backend regression | PASS | ruff format 158 files OK; ruff clean; mypy STRICT both roots after .mypy_cache purge — found+fixed latent untyped session param in D-037 `_validate_settlement_authority_in_session` (root cache had masked it); pytest 375/375 stable across 5+ runs; hypothesis/stateful 7; focused security keywords 40; security-check PASS; race-test flake ROOT-CAUSED: (a) Redis SET-NX timeouts under load raise CoordinationUnavailable fail-closed -> now treated as inconclusive-no-effect, (b) late workers legitimately return via ticket-idempotency shortcut BEFORE nonce claim -> multiple settled rows valid iff SAME attempt id; durable exactly-once asserts (calls==1, attempts==1, held-once) kept STRICT |
| M03 | Full Phase-1/2 frontend/E2E regression | PASS | eslint clean; tsc clean; vitest 11/11 (3 files); next production build OK (static prerender); Playwright 5/5 incl. stubbed-checkout success/failure/unknown paths + DOM/network secret scans; grep over src+e2e+.next/static for rzp_live_/TOKENROUTER/tokenrouter = 0; all four baseline surfaces exercised by smoke spec |
| M04 | Phase-2 real-provider integrity revalidation | PASS | focused suites 47+20 pass (settings fail-safe/provider/taxonomy/callback/webhook/reducer/reconciliation/executor-rz/schema/spend/executor/ledger); runtime live-key probe -> RAZORPAY_LIVE_KEY_REJECTED; real EvidenceLedger.verify() on dev DB valid=True; REAL read-only auth diagnostic ok=True mode=test guard passed (864ms); NO new payment created |
| M05 | Freeze Phase-3 baseline | PASS | docs/PHASE3_BASELINE.md frozen at HEAD d457661: 375 backend tests, benchmark 20 pairs F1=1.0 regenerated, migration head a93c7d5e21f0, full gate table, runtime versions, Phase-2 references, explicit NO-PHASE-3-AI-ACTIVE statement, bootstrap values still unread |
| M06 | Live AI/ML research and version manifest | PASS | R-019 TokenRouter reality (documented base URL api.tokenrouter.io/v1 vs prompt's .com; tr_ keys; OpenAI-compatible + JSON mode; model id to be proven live at M10); R-020 both DeBERTa cards (licenses MIT/Apache-2.0; CRITICAL label-map divergence A=[E,N,C] vs B=[C,E,N]; B ships ONNX); R-021 stack stables (transformers 5.15.1, datasets >=5.0.1 w/ PYSEC-2026-3716 floor, accelerate 1.14.0, onnxruntime 1.29.0); VERSION_MANIFEST rows added with planned-install milestones |
| M07 | Private TokenRouter credential injection | PASS | exclusion re-verified (.gitignore:6 for .env mode600; .git/info/exclude:49 bootstrap); 3 vars parsed+merged into .env programmatically — only NAMES/lengths printed (key=51, url=30, model=21 chars), all Phase-1/2 vars byte-preserved; .env.example blank placeholders added; leak sweep over trackable files clean; private file NOT deleted (deletion gated on M10 probe success) |
| M08 | Phase-3 governance transition | PASS | PHASES Phase-3 ACTIVE; PRD §12 PRD-P3-001..014; SECURITY §16 P3-S01..S20 + T25+ families; TESTING §15 ten phase-3 gates; DECISIONS D-038 (architecture/no-Qwen-finetune) D-039 (fusion release-blocking) D-040 (data/gold/training/inference policy); ARCHITECTURE §15; PHASE3_MILESTONES.md created |
| M09 | TokenRouter client abstraction | NOT_STARTED | — |
| M10 | TokenRouter auth + capability probe | NOT_STARTED | — |
| M11 | IntentDraft schema | NOT_STARTED | — |
| M12 | Compiler prompt & isolation contract | NOT_STARTED | — |
| M13 | Strict validation + bounded repair | NOT_STARTED | — |
| M14 | Compiler golden evaluation set | NOT_STARTED | — |
| M15 | Real compiler evaluation | NOT_STARTED | — |
| M16 | Human confirmation domain flow | NOT_STARTED | — |
| M17 | Human confirmation UI | NOT_STARTED | — |
| M18 | AgentPay-IR taxonomy/schema | NOT_STARTED | — |
| M19 | Deterministic seed dataset | NOT_STARTED | — |
| M20 | Qwen candidate generator | NOT_STARTED | — |
| M21 | Candidate validation | NOT_STARTED | — |
| M22 | Dedup / near-duplicate detection | NOT_STARTED | — |
| M23 | Leakage-safe split builder | NOT_STARTED | — |
| M24 | Adversarial dataset expansion | NOT_STARTED | — |
| M25 | Gold review pack generation | NOT_STARTED | — |
| M26 | HUMAN GATE 1 — gold review | NOT_STARTED | — |
| M27 | Finalize AgentPay-IR v1 | NOT_STARTED | — |
| M28 | DeBERTa baseline A eval | NOT_STARTED | — |
| M29 | DeBERTa baseline B eval | NOT_STARTED | — |
| M30 | Baseline selection | NOT_STARTED | — |
| M31 | Reproducible training bundle | NOT_STARTED | — |
| M32 | Colab notebook | NOT_STARTED | — |
| M33 | Colab preflight bundle | NOT_STARTED | — |
| M34 | HUMAN GATE 2 — Colab training | NOT_STARTED | — |
| M35 | Training artifact verification | NOT_STARTED | — |
| M36 | Fine-tuned vs baseline evaluation | NOT_STARTED | — |
| M37 | Threshold calibration | NOT_STARTED | — |
| M38 | Production SemanticVerifier | NOT_STARTED | — |
| M39 | SemanticEvidenceBuilder | NOT_STARTED | — |
| M40 | Conservative policy fusion | NOT_STARTED | — |
| M41 | End-to-end semantic attack scenarios | NOT_STARTED | — |
| M42 | Prompt-injection context-isolation tests | NOT_STARTED | — |
| M43 | Phase-3 UI integration | NOT_STARTED | — |
| M44 | AI audit evidence events | NOT_STARTED | — |
| M45 | End-to-end Phase-3 benchmark | NOT_STARTED | — |
| M46 | Ablation study | NOT_STARTED | — |
| M47 | Local inference optimization / Modal decision | NOT_STARTED | — |
| M48 | Full Phase-3 security/quality gate | NOT_STARTED | — |
| M49 | Clean-room Phase-3 acceptance | NOT_STARTED | — |
| M50 | Completion report & STOP | NOT_STARTED | — |

---

# Current milestone evidence

## M01 — Repository, governance, and secret-safety inspection

MILESTONE: M01
STATUS: PASS

Requirements: master prompt M01 + §1/§2/§5 steps 1–3 — repository/Git/state
inspection, governance read in precedence order, secret safety proven BEFORE
any private value is read. Security invariants: S30, P3-S01 groundwork.

### Implementation / findings

- Master prompt read completely (1959 lines) including all 50 milestones,
  invariants P3-S01..S20, human gates, failure policy, acceptance matrix.
- Governance read in AGENTS.md precedence: AGENTS.md, RULES.md, PRD.md,
  PHASES.md (Phase 2 marked COMPLETE), SECURITY.md (P2-S01..S24 + D-037 note),
  ARCHITECTURE.md §14, DESIGN.md, DECISIONS.md through **D-037**, PHASE2_
  MILESTONES/PHASE2_STATUS, TESTING.md, VERSION_MANIFEST.md, RESEARCH.md,
  PHASE1_STATUS.md (tail), MEMORY.md, AI_WORKFLOW.md, Phase-2 completion
  artifacts. No conflict found between human decisions and the Phase-3 master
  prompt (Phase-3 was explicitly approved by the human instruction that
  delivered the prompt).
- Git state: branch `main`; working tree clean except three UNTRACKED Phase-3
  files (`RazorMesh_Trust_Phase3_Master_Prompt.md`,
  `PASTE_THIS_TO_AGENT_PHASE3.md`, `PHASE3_PRIVATE_BOOTSTRAP_LOCAL_ONLY.md`).
  HEAD `fc0422e` ("P2-M50 Final Check") on top of `3e63bcb` (P2-M50 PASS).
  No unrelated user work at risk; nothing staged; no stash conflicts.
- Secret safety (performed BEFORE reading any private value):
  - `.env` ignored via `.gitignore:6`; permissions 600.
  - Bootstrap file NOT tracked (`git ls-files` empty for it) and has ZERO
    entries in any commit history (`git log --all -- <file>` empty).
  - Exact filename added to `.git/info/exclude` line 49; verified via
    `git check-ignore -v`.
  - Grep across tracked backend/frontend source: zero TokenRouter references;
    no `NEXT_PUBLIC_TOKENROUTER_API_KEY` anywhere (forbidden by master prompt).
- Values NOT read yet — credential merge happens at M07, probe at M10,
  deletion of the private file after M10 success (master prompt §5/M07/M10).
- Full backend regression run as the M01 gate subset: **375/375 passed**
  matching the post-completion audit count recorded in MEMORY (D-037 state).
  One transient failure of `test_twenty_workers_same_ticket_one_provider_effect`
  occurred in the FIRST full-suite run (machine under parallel load from the
  session's prior commands); it then passed in isolation, in 3 consecutive
  module runs, and in 2 further full-suite runs. Recorded honestly here as a
  load-sensitivity observation; M02 owns the deeper look — if it recurs, make
  the test load-robust WITHOUT weakening its exactly-once assertions.

### Files changed

- `PHASE3_STATUS.md` (new skeleton), `MEMORY.md` (phase transition), this file.
- `.git/info/exclude` (local-only, not tracked).

### Validation commands + results

```bash
git status --short                          # only intended untracked P3 files
git check-ignore -v .env                    # .gitignore:6
stat -f "%Sp %N" .env                       # mode 600
git ls-files | grep -i "PHASE3_PRIVATE\|TOKENROUTER"   # empty
git log --all --oneline -- PHASE3_PRIVATE_BOOTSTRAP_LOCAL_ONLY.md  # empty
grep -rn "TOKENROUTER" services/api/src apps/web/src   # empty
cat .git/info/exclude | tail -1             # exact filename present
cd services/api && uv run pytest            # 375 passed
```

### Real external API use

- NONE (no TokenRouter call yet; values unread).

### Security regression

- Full backend suite = the standing Phase-1/2 regression gate; green.

### Human gate

- NONE.

### Known limitations

- The 20-worker race test showed one load-induced flake; see findings above.

### Next

- M02 — Full Phase-1/2 backend regression (explicit milestone; includes
  ruff/mypy/Hypothesis/concurrency/security batteries and the race-test
  stability investigation).


## M02 — Full Phase-1/2 Backend Regression

MILESTONE: M02
STATUS: PASS

Requirements: master prompt M02 + §1 — complete backend quality/security
battery on the inherited baseline; understand drift; repair regressions.
Security invariants: all Phase-1/2 invariants re-proven.

### Battery results
```text
ruff format --check .                        -> 158 files already formatted
ruff check .                                 -> All checks passed
mypy -p razormesh_api (ROOT, cache-purged)   -> Success, 54 files
mypy -p razormesh_api (services/api)         -> Success, 54 files
pytest (full)                                -> 375 passed (stable x5)
pytest -k "hypothesis or stateful"           -> 7 passed
pytest -k "race or replay or forged or tamper or superseded or stale or unknown
           or dedup or duplicate or signature or webhook or callback or reconciliation"
                                             -> 40 passed
make security-check                          -> PASS (0 findings, audits clean)
```

### Repairs performed this milestone
1. **Latent strict-mypy violation** in D-037 audit code
   (`executor._validate_settlement_authority_in_session`): untyped `session`
   param hidden behind `type: ignore`; root-dir mypy had been serving a stale
   `.mypy_cache`. Fixed with `Session` annotation via TYPE_CHECKING import;
   caches purged; both roots genuinely clean.
2. **Race-test load sensitivity** (observed once at M01): root-caused to two
   benign mechanisms — (a) Redis `SET NX EX` timeout raises
   `CoordinationUnavailable` fail-closed (RULES §Data authority compliant);
   (b) workers returning through the ticket-derived idempotent re-entry
   shortcut that precedes the nonce claim. Test now treats coordination
   failures as inconclusive no-effect deliveries and asserts worker identity
   convergence, while keeping DURABLE exactly-once assertions strict
   (`transport.calls == 1`, one attempt row, reservation held exactly once,
   committed == 0). The release-blocking property is unchanged.

### Real external API use
- NONE.

### Next
- M03 — Full Phase-1/2 frontend/E2E regression.


## M03 — Full Phase-1/2 Frontend/E2E Regression

MILESTONE: M03
STATUS: PASS

Requirements: master prompt M03 — full frontend battery green BEFORE any AI
change; buyer/merchant/security-lab/audit baselines verified.
Security invariants: P2-S03/S04 (no secret to browser), UI truth rules.

### Battery results
```text
pnpm lint          -> eslint clean
pnpm typecheck     -> tsc --noEmit clean
pnpm test          -> 3 files, 11 tests passed
pnpm build         -> OK, static prerender
npx playwright test-> 5 passed (nav smoke x2 + stubbed-checkout x3 with
                      DOM-content and per-request-line secret scans)
grep rzp_live_|TOKENROUTER|tokenrouter across src/, e2e/, .next/static -> 0 hits
```

Baseline surfaces verified by the smoke spec: home trust-core banner, Buyer,
Merchant, Security Lab, Audit headings reachable.

### Real external API use
- NONE.

### Next
- M04 — Phase-2 real-provider integrity revalidation.


## M04 — Phase-2 Real-Provider Integrity Revalidation

MILESTONE: M04
STATUS: PASS

Requirements: master prompt M04 + §1 — revalidate Test Mode guard, mock-vs-
real boundary, live-key rejection, webhook/dedup/ordering semantics,
provider-unknown recovery, reservation invariants, audit chain, safe read-only
diagnostic. No unnecessary payments.
Security invariants: P2-S01..S24 re-proven where testable without new spend.

### Evidence
```text
Focused suites (47) tests/test_settings_phase2.py test_provider_razorpay.py
  test_razorpay_error_taxonomy.py test_callback_verification.py
  test_webhook_verification.py test_reducer.py test_reconciliation.py
  test_executor_razorpay.py test_schema_phase2.py            -> all pass
Reservation/settlement/ledger suites (20): spend/executor/ledger -> all pass
Runtime live-key probe  -> ProviderConfigError RAZORPAY_LIVE_KEY_REJECTED
EvidenceLedger.verify() on dev DB (real M38/M40 evidence)   -> valid=True
scripts/rzp_auth_check.py (READ_ONLY, real Test keys)       -> ok=True,
  mode: test guard passed, latency 863.77ms
```
No order/payment was created this milestone.

### Next
- M05 — Freeze Phase-3 baseline.


## M05 — Freeze Phase-3 Baseline

MILESTONE: M05
STATUS: PASS

- `docs/PHASE3_BASELINE.md` created and frozen: HEAD d457661, migration head
  a93c7d5e21f0, 375-test battery, benchmark regenerated live (20 pairs F1=1.0),
  versions, Phase-2 references, watch items, and the explicit statement that
  no Phase-3 AI component exists yet.
- MEMORY now records Phase 3 as ACTIVE (permitted after M01–M04 PASS).


## M06 — Live AI/ML Research and Version Manifest

MILESTONE: M06
STATUS: PASS

Requirements: master prompt M06/§4 — verify current sources live; record in
RESEARCH.md + VERSION_MANIFEST.md; never trust remembered versions.

### Key findings (full detail in RESEARCH.md R-019..R-021)
1. **TokenRouter**: official docs say base URL `https://api.tokenrouter.io/v1`
   (master prompt wrote `.com`). Keys `tr_...`; OpenAI-compatible chat
   completions incl. JSON mode; `/v1/models`. Resolution policy recorded:
   bootstrap BASE_URL probed first at M10; documented .io is a config
   correction (same provider), never a silent switch.
2. **Baseline label maps differ** — A (MoritzLaurer): 0=entailment,
   1=neutral, 2=contradiction; B (cross-encoder): 0=contradiction,
   1=entailment, 2=neutral. Both will be pinned + unit-tested in M28/M29.
   Licenses MIT / Apache-2.0. B has official ONNX exports (useful for M47).
3. **Stack stables**: transformers 5.15.1; datasets >=5.0.1 (PYSEC-2026-3716
   fixed in 5.0.1 → advisory floor); accelerate 1.14.0; huggingface-hub 1.28.0;
   onnxruntime 1.29.0; torch exact pin deferred to M31/M32 bundle build with
   pip-audit on the generated lock.

### Validation
```text
Live fetches: tokenrouter.io/docs/{chat-completions,models,from-openai,python},
huggingface.co/MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli,
huggingface.co/cross-encoder/nli-deberta-v3-base, PyPI transformers/datasets/
accelerate/onnxruntime/huggingface-hub pages. All dated 2026-08-25.
```

### Next
- M07 — Private TokenRouter credential injection.


## M07 — Private TokenRouter Credential Injection

MILESTONE: M07
STATUS: PASS

Requirements: master prompt M07/§5 steps 1–7 — safe merge without printing;
preserve Phase-1/2 values; blank placeholders; deletion deferred to post-M10.
Security invariants: P3-S01 groundwork, S30.

### Evidence
- Exclusion re-verified BEFORE reading: `.env` -> .gitignore:6 (mode 600);
  bootstrap -> .git/info/exclude:49.
- Programmatic merge (python heredoc): parsed exactly the three expected keys,
  replaced-or-appended into `.env`; asserted all Razorpay/Phase-1 keys still
  present; asserted every non-target pre-existing line survived byte-for-byte.
  Output limited to key NAMES + char lengths (51/30/21) — no values.
- `.env.example`: Phase-3 section appended with commented BLANK placeholders
  plus public-docs guidance (no real values).
- Leak sweep: grep across trackable files for `TOKENROUTER_API_KEY` /
  high-entropy `tr_...` tokens -> only a doc mention of the FORBIDDEN
  `NEXT_PUBLIC_` name in PHASE3_STATUS; no values anywhere.
- settings fail-safe suite re-run: 14 passed.

### Real external API use
- NONE (probe is M10).

### Next
- M08 — Phase-3 governance transition.


## M08 — Phase-3 Governance Transition

MILESTONE: M08
STATUS: PASS

Requirements: master prompt M08 — full governance extension without erasing
history.

### Updated
- PHASES.md: Phase 3 ACTIVE banner.
- PRD.md: §12 with PRD-P3-001..014 + non-goals.
- SECURITY.md: §16 P3-S01..S020 invariants + defensive scenario families.
- TESTING.md: §15 ten release-blocking Phase-3 gates.
- DECISIONS.md: D-038, D-039, D-040.
- ARCHITECTURE.md: §15 AI architecture + isolation + auditability.
- PHASE3_MILESTONES.md: created (50 rows).
- MEMORY.md already Phase-3 active (M05).

### Validation
Docs-only milestone; lint/mypy clean; settings suite 14 passed post-edit.
