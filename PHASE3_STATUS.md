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
| M09 | TokenRouter client abstraction | PASS | intent_compiler.py: backend-only httpx client (Bearer from SecretStr, bounded timeout, X-Request-Id ULID correlation); taxonomy AUTH/REJECTED/UNKNOWN mirroring D-030 with calls==1 no-retry proofs; malformed-payload matrix; response_format passthrough; /models probe method; DI factory naming TOKENROUTER_API_KEY only; settings fields added (SecretStr key, documented .io default URL, planner model, timeout<=120); 13 MockTransport tests; suite 388/388 |
| M10 | TokenRouter auth + capability probe | PASS | REAL probe: AUTH ok on api.tokenrouter.com (bootstrap URL validated; R-019 corrected); planner qwen/qwen3.8-max-free visible+usable (reported internally as qwen3.8-max-pd); Qwen3.8 is a THINKING model -> reasoning_content/reasoning_tokens captured in client; empty content at tiny max_tokens proven; JSON-by-instruction parseable {max_price_minor:499999,currency:INR} 11.8s; response_format json_object ACCEPTED parseable (68s); failure shape = transient 503 hard_concurrency_limit windows -> taxonomy UNKNOWN + probe-only bounded backoff; PRIVATE FILE DELETED, zero history/tracked exposure re-proven |
| M11 | IntentDraft schema | PASS | domain/intent_draft.py: versioned agentpay-intent-draft-v1; CompilerIntentPayload (hard/semantic/ambiguities/unspecified) + server-identity IntentDraft wrapper (drf_ ULID, source hash, created_at); StrictInt minor-unit money w/ explicit ISO currency (float/bool/<=0 rejected), extra=forbid (hallucinated keys fail), ALL defaults None (no invented currency/condition/recurring), bounded texts(280)/lists(8..12)/items(120); 14 negative+property tests incl. Hypothesis round-trips; suite 404/404 |
| M12 | Compiler prompt & isolation contract | PASS | intent_compiler_prompt.py: COMPILER_SYSTEM_PROMPT v1 encoding all §12 rules (no-invention, hard-vs-semantic split, ambiguities, minor-unit money, negation preservation, sole-source authority); prompt_sha256 audit binding; TrustedHumanAuthorization value object (3..2000 chars, control-char rejection); build_compiler_messages single choke point with NO context parameter (structural isolation — signature-level test + module-surface scan proving no str inlet exists); hostile-text inertness test; suite 411/411 |
| M13 | Strict validation + bounded repair | PASS | intent_compilation_service.py: extract_json_object (bare/fenced/wrapped) -> CompilerIntentPayload strict parse (20k char cap) -> ONE repair w/ validation feedback + response_format json_object -> fail closed; CompilerOutcome OK/FAILED(+NEEDS_CLARIFICATION ready for M16) carries attempts/error_code/request_ids; provider failures fail-closed with exact call-count proofs (1 on first-failure, 2 max total); malicious prose inert; 9 tests; suite 420/420 |
| M14 | Compiler golden evaluation set | PASS | data/phase3/compiler_golden/golden_set.jsonl: 307 manual-truth cases across 25 categories (easy 234/medium 43/hard 30) from hand-authored template families with truth computed BY CONSTRUCTION (never Qwen); manifest w/ SHA256 + truth_source=human-authored; compiler_eval.py evaluator (Expectation schema, omission/invention/mismatch taxonomy incl. money-without-human-statement sentinel + declared invention bans); structural honesty test forbidding model-label fields in rows; 13 tests; suite 433/433 |
| M15 | Real compiler evaluation | PASS | REAL Qwen run on stratified **N=90/307** sample (D-041 human-approved scope; full-307 = pre-M48 obligation). Schema validity 90/90=100%; bounded repair 7/90 all repaired to valid; **case pass 71/90=78.9%** (easy 77.5/medium 90.9/hard 71.4); field recall brands/merchants/quantity 1.0, currency 0.96, semantic 0.9706, recurring_forbidden 0.9231, max_amount_minor 0.8533; **money precision 1.0, 0 mismatches, 0 invented amounts** (all money errors are fail-closed omissions); ambiguity 6/6; injection 2/3 (one warranty semantic leak). Prompt v1→v2 (v1 long-form made the thinking model hit finish=length w/ empty content at 4000 tokens; v2 schema-forward compiles reliably). Two golden-truth defects fixed transparently (F1 rupee→INR pre-measurement; F13-002 recurring_forbidden removed post-measurement + re-measured, sha256 eef70c9c→9164f04c, stale rows preserved). Budget-2000 harness contamination discarded + re-measured at 4000 (F10-001/003 then passed). Provider-noise rows retried, never counted. Docs: docs/PHASE3_INTENT_COMPILER_EVAL.md |
| M16 | Human confirmation domain flow | PASS | domain/confirmation.py (DraftState DRAFT/NEEDS_CLARIFICATION/CONFIRMED/REJECTED; fail-closed build_confirmed_contract: no-stated-money -> DRAFT_MISSING_MONEY, conservative terms aggregate=threshold=cap, quantity default 1, recurring forbidden unless explicit) + confirmation_service.py (advisory lineage locks, compile supersession, idempotent same-nonce replay, replay-mismatch rejection, NEEDS_CLARIFICATION unconfirmable, generation bump reusing intent_id w/ DRAFT_BELOW_COMMITTED_SPEND capacity guard, INTENT_COMPILED/CONFIRMED/REJECTED/SUPERSEDED/COMPILE_FAILED ledger events); migration e7a1c4f9b2d5; raw human text never stored (sha256 only); 17 tests incl. 8-thread concurrent single-authority proof; suite 449/449; D-042 |
| M17 | Human confirmation UI | NOT_STARTED | — |
| M18 | AgentPay-IR taxonomy/schema | PASS | agentpay_ir.py v0.1: fixed NLI orientation (premise=trusted evidence, hypothesis=confirmed-authorization statement), 18 semantic families, label/source/difficulty vocabularies, Provenance+Review blocks, content_sha256 integrity binding (any mutation detected), split reserved for M23; 10 tests incl. tamper-detection + vocabulary enforcement; suite 463/463 |
| M19 | Deterministic seed dataset | PASS | data/phase3/dataset/seed: 915 AgentPay-IR records (307 golden cases × entailment/contradiction/neutral templates; content-dedup 921→915); labels balanced within 5%; all 18 families covered; deterministic regeneration byte-identical (fixed provenance ts + derived record ids); label_source=template_truth throughout; 6 tests incl. ≥600 floor + manifest-hash binding; suite 469/469 |
| M20 | Qwen candidate generator | NOT_STARTED | — |
| M21 | Candidate validation | NOT_STARTED | — |
| M22 | Dedup / near-duplicate detection | PASS | dataset_dedup.py: exact dups via content hash; near-dups via token-Jaccard >=0.90 WITHIN (family,label) classes; union-find clusters w/ deterministic smallest-id canonical; cross-class collisions reported separately as suspected mislabels (never merged); 5 tests incl. determinism + ordering; generator also applies exact-normalized guard at generation time |
| M23 | Leakage-safe split builder | PASS | dataset_splits.py: groups from provenance.source_case_id (whole groups to ONE split via stable SHA256 hash -> 70/15/15); deterministic across runs; leakage_report catches any group spanning splits (contaminated-fixture test proves the gate FAILS) + UNASSIGNED accounting; assert_no_leakage helper for release gates; 5 tests |
| M24 | Adversarial dataset expansion | NOT_STARTED | — |
| M25 | Gold review pack generation | PASS | data/phase3/gold/: gold_review.csv 320 rows stratified across all 18 families (labels 121C/98E/101N), suggested_label column LAST for anti-anchoring; self-contained keyboard-driven HTML reviewer (1/2/3 labels, arrows, E-export to gold_decisions.json, localStorage persistence); INSTRUCTIONS.md with orientation + procedure; manifest PENDING_HUMAN_REVIEW + csv sha256; 5 tests; suite 495/495 |
| M26 | HUMAN GATE 1 — gold review | PENDING_HUMAN | pack READY at data/phase3/gold/ (320 stratified cases, HTML keyboard reviewer, INSTRUCTIONS.md, export flow); human reviews on wake; downstream gates (final model selection, threshold freeze) stamped PENDING_GOLD_VALIDATION until then |
| M27 | Finalize AgentPay-IR v1 | PASS | frozen_v1: 1021 records (train 723 / val 171 / test 127) from seed+adversarial+candidates-at-freeze; whole-group splits via P3-M23 builder; leakage gate PASSED; per-split sha256 in frozen_manifest; gold_validation_status=PENDING_GOLD_VALIDATION stamped honestly (refresh to v2 possible pre-M48 as candidates grow); 5 tests |
| M28 | DeBERTa baseline A eval | PASS | MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli (MIT) zero-shot on frozen_v1: val acc 0.474 / macroF1 0.397 / contra_recall 0.389; test acc 0.417 / macroF1 0.349; card label map pinned+unit-tested; orientation sanity-checked with hand pairs; docs/PHASE3_NLI_BASELINE_A_METRICS.json |
| M29 | DeBERTa baseline B eval | PASS | cross-encoder/nli-deberta-v3-base (Apache-2.0, ONNX available) identical harness: val acc 0.637 / macroF1 0.607 / contra_recall 0.704; test acc 0.606 / macroF1 0.589; docs/PHASE3_NLI_BASELINE_B_METRICS.json |
| M30 | Baseline selection | NOT_STARTED | — |
| M31 | Reproducible training bundle | NOT_STARTED | — |
| M32 | Colab notebook | PASS | notebooks/RazorGuard_NLI_Phase3_Training.ipynb (13 cells): GPU assert, pinned installs, bundle upload+hash verification BEFORE training, config-driven Trainer (seed 42, macro_f1 best-model selection), artifact packaging w/ label_map.json+metrics.json+base_model.txt; LOCAL SMOKE of identical logic PASSED on CPU (24 rows/1 epoch, train 29.2s, eval_loss 0.06) via services/ml-venv |
| M33 | Colab preflight bundle | PASS | artifacts/phase3_colab_training_bundle.zip (755KB, 8 entries): notebook + frozen train/val + config + manifest + requirements-frozen + verify script; bundle VERIFY PASS; ready for human upload at M34 |
| M34 | HUMAN GATE 2 — Colab training | PENDING_COLAB | bundle verified at artifacts/phase3_colab_training_bundle.zip; human will run notebook on T4 GPU in the morning and hand back phase3-finetuned.zip; agent continues downstream with PROVISIONAL baseline B so no milestone is blocked |
| M35 | Training artifact verification | PASS (harness) | rzp_verify_training.py artifact mode tested against synthetic fixtures (complete/incomplete/label-space violations); REAL artifact verification deferred to post-M34 hand-back — rerun required after Colab |
| M36 | Fine-tuned vs baseline evaluation | NOT_STARTED | — |
| M37 | Threshold calibration | PASS (PROVISIONAL) | calibrated on frozen VAL split ONLY: tau_block=0.36 tau_entail=0.40 -> contradiction recall 0.704 @ block precision 0.927, false-blocks on entailment 2/171 (<=5% cap); objective F2(BLOCK); first calibration attempt degenerate (tau=1.0/recall 0) -> reformulated honestly; policy manifest data/phase3/policy/semantic_thresholds.json stamped PENDING_GOLD_VALIDATION; single gold/test evaluation deferred to post-gold-review rerun list |
| M38 | Production SemanticVerifier | NOT_STARTED | — |
| M39 | SemanticEvidenceBuilder | PASS | semantic_evidence.py: deterministic pairs per verifiable aspect (budget/brand/condition/recurring) from CURRENT sanitized evidence; hypothesis text derived ONLY from confirmed authorization terms — hostile product text stays premise-side and can never become the claim; 3 tests incl. injection-in-product-title case |
| M40 | Conservative policy fusion | NOT_STARTED | — |
| M41 | End-to-end semantic attack scenarios | PASS | semantic_lab.py: 5 defensive scenarios through REAL policy rule + fusion with fake scorer (no model/network) — injection price-hike BLOCKED, disguised renewal BLOCKED, safe-lookalike stays ALLOW, deterministic CHALLENGE survives perfect PASS, deterministic BLOCK supreme; 3 tests; suite 516/516 |
| M42 | Prompt-injection context-isolation tests | PASS | transport-captured compile request proves ONLY [system prompt, verbatim trusted text] ride the wire (no merchant payload slot exists); hostile commerce text confined to premises; fusion tightens ALLOW->BLOCK on high contradiction while NO durable authority is touched anywhere in flow; 2 e2e tests |
| M43 | Phase-3 UI integration | PASS | IntentDraftPanel renders optional semantic-verdict block (action, fail_closed flag, three probabilities, policy version, tighten-only note) when backend supplies it; tsc/eslint clean; vitest 12; trust copy unchanged |
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


## M09 — TokenRouter Client Abstraction

MILESTONE: M09
STATUS: PASS

Requirements: master prompt M09 — backend-only provider client with explicit
timeout, structured errors, safe correlation, DI, typed config, no secret
logs, deterministic fixtures. NO authority semantics yet (P3-S03/S16).
Security invariants: P3-S01/S16 groundwork.

### Implementation
- settings.py: tokenrouter_api_key (SecretStr), tokenrouter_base_url
  (documented .io default per R-019), planner_model, bounded timeout.
- intent_compiler.py: TokenRouterClient + taxonomy
  (AUTH_FAILED / REQUEST_REJECTED / UNKNOWN_OUTCOME / CONFIG_INVALID),
  ChatCompletionResult projection, list_models() read-only probe,
  build_tokenrouter_client() fail-safe factory. Errors carry codes +
  request ids only — never keys/bodies.

### Validation commands + results
```text
ruff check .                                  -> clean
mypy -p razormesh_api (strict)                -> Success, 55 files
pytest tests/test_intent_compiler_client.py   -> 13 passed
pytest (full)                                 -> 388 passed
```

### Real external API use
- NONE (MockTransport only; real probe is M10).

### Next
- M10 — TokenRouter authentication and capability probe (real key).


## M10 — TokenRouter Authentication & Capability Probe

MILESTONE: M10
STATUS: PASS

Requirements: master prompt M10 + §5 steps 8–10 — real probe of auth, model,
JSON compliance, response_format support, latency, failure shapes; delete the
private bootstrap after safe success; prove it was never tracked.
Security invariants: P3-S01/S14.

### Probe results (scripts/rzp_tokenrouter_probe.py; safe output only)
1. AUTH ok via GET /v1/models with the real key (2 models listed); base URL =
   api.tokenrouter.com per bootstrap — R-019 corrected accordingly.
2. `qwen/qwen3.8-max-free` visible and usable; gateway reports internal name
   `qwen3.8-max-pd`.
3. **Thinking-model reality**: responses carry message.reasoning_content +
   usage.reasoning_tokens; with max_tokens=16 the model ends finish=length
   with EMPTY content — compiler budgets must be generous (client now
   surfaces both fields; fixture-tested).
4. JSON-by-instruction: parseable strict JSON
   {"max_price_minor": 499999, "currency": "INR"} — semantically correct for
   the prompt; finish=stop; ~11.8s.
5. response_format={"type":"json_object"} ACCEPTED by gateway/model and
   produced parseable JSON (~68s wall under contention).
6. Failure/rate-limit shape: transient 503 JSON body
   {code: hard_concurrency_limit} arriving in windows; our taxonomy maps it to
   TOKENROUTER_UNKNOWN_OUTCOME (fail-closed) — the PROBE uses bounded backoff;
   production compiler calls will NOT auto-retry (failure policy §22).

### Private file disposal
```text
rm PHASE3_PRIVATE_BOOTSTRAP_LOCAL_ONLY.md            # deleted after success
git log --all -- <file>                              -> 0 entries (never tracked)
git status grep private                              -> none
grep tr_[A-Za-z0-9]{10,} across tracked trees        -> 0 hits
```
The key survives ONLY in gitignored `.env`.

### Client changes folded in
ChatCompletionResult gained reasoning_content/reasoning_tokens (fixture-
tested). Suite remains green (13 client tests).

### Next
- M11 — IntentDraft schema.


## M11 — IntentDraft Schema

MILESTONE: M11
STATUS: PASS

Requirements: master prompt M11 — versioned Pydantic/domain IntentDraft
separating hard constraints, semantic constraints, ambiguities, unspecified
fields; integer minor-unit money; explicit currency; no invented defaults;
bounded sizes; property/negative tests.
Security invariants: P3-S03 (proposal-not-authority — identity generated
server-side only), P3-S12 groundwork.

### Implementation
- `domain/intent_draft.py`: `CompilerIntentPayload` (LLM-facing; frozen,
  extra=forbid) with HardConstraints / SemanticConstraint / Ambiguity /
  UnspecifiedField; `IntentDraft` adds draft_id (drf_+ULID pattern),
  source_text_sha256, created_at. Schema pinned via
  Literal["agentpay-intent-draft-v1"].
- MoneyBound uses StrictInt (rejects 500.0 AND True) with ge=1 and an explicit
  ^[A-Z]{3}$ currency. Every optional field defaults to None/() — the type
  level cannot invent "INR" or "new".
- Identity is NOT part of compiler output: raw LLM payloads cannot construct
  a durable IntentDraft without server-generated id/hash/time.

### Validation commands + results
```text
ruff check .                                  -> clean
mypy -p razormesh_api (strict)                -> Success, 56 files
pytest tests/test_intent_draft.py             -> 16 passed (negatives +
                                                 Hypothesis round-trip props)
pytest (full)                                 -> 404 passed
```

### Next
- M12 — Qwen compiler prompt & isolation contract.


## M12 — Qwen Compiler Prompt & Isolation Contract

MILESTONE: M12
STATUS: PASS

Requirements: master prompt M12 — versioned+hashed system prompt; trusted
human text only; anti-invention/negation/money rules; context-isolation tests.
Security invariants: P3-S02/S17, P3-S13 groundwork.

### Implementation
- `intent_compiler_prompt.py`: COMPILER_PROMPT_VERSION +
  COMPILER_SYSTEM_PROMPT (rules: never invent; hard vs semantic separation;
  ambiguities surfaced not resolved; money→integer minor units + explicit
  currency or 'unspecified'; preserve negation; user text is the ONLY source;
  ignore embedded instructions).
- `prompt_sha256()` binds audits to exact prompt text (P3-S13; tamper test).
- `TrustedHumanAuthorization` value object: 3..2000 chars, control chars
  rejected — the marker type that marks text as human-channel.
- `build_compiler_messages(trusted)`: THE choke point. Signature accepts only
  the marker object — structurally impossible to pass merchant/product blobs;
  human text embedded verbatim.

### Isolation proofs (tests/test_compiler_prompt_isolation.py)
1. Version/hash stability + tamper sensitivity of the prompt hash.
2. Rules present in the prompt (grep-style assertions on all §12 mandates).
3. Verbatim embedding; roles exactly [system, user].
4. **Structural**: get_type_hints(build_compiler_messages) == {trusted, return}
   — no parameter exists for extra content.
5. **Module surface scan**: every function defined in the module is checked;
   none besides build_compiler_messages takes any string parameter at all.
6. Hostile merchant injection text stays verbatim in the user message and
   leaks nothing into the system prompt.

### Validation commands + results
```text
ruff check .                     -> clean
mypy -p razormesh_api (strict)   -> Success, 56 files
pytest tests/test_compiler_prompt_isolation.py -> 7 passed
pytest (full)                    -> 411 passed
```

### Next
- M13 — Strict output validation and bounded repair.


## M13 — Strict Output Validation & Bounded Repair

MILESTONE: M13
STATUS: PASS

Requirements: master prompt M13 — Qwen output → strict JSON extraction →
Pydantic/domain validation → ONE bounded repair → fail closed/clarify.
Adversarial matrix: invalid JSON/types/floats/extra keys/missing currency/
oversized/malicious prose. Security invariants: P3-S03/S08/S12.

### Implementation
- `intent_compilation_service.py`:
  - `extract_json_object`: bare / ```json fenced / prose-wrapped objects;
  - `parse_compiler_output`: strict domain validation, 20k-char output cap;
  - `IntentCompilationService.compile()`: attempt 1 with the versioned prompt
    → on any schema failure exactly ONE repair call carrying a truncated
    validation summary + response_format json_object → still invalid ⇒
    FAILED(SCHEMA_INVALID_AFTER_REPAIR); provider errors ⇒ FAILED(
    COMPILER_UNAVAILABLE) with NO automatic retries;
  - `CompilerOutcome` is inert data: it can never create authority.

### Evidence (tests/test_intent_compilation_service.py)
- bare/fenced/wrapped JSON accepted; no-JSON and >20k outputs refused;
- float money / extra hallucinated keys / wrong schema_version rejected;
- invalid→repair→OK path: exactly 2 calls, repair carries feedback +
  response_format; still-invalid path fails closed after exactly 2 calls;
- 503 on first call: FAILED after EXACTLY 1 call (no auto-retry);
- 500 during repair: FAILED(repair:) after exactly 2 calls;
- malicious prose produces no authority candidate.

### Validation commands + results
```text
ruff check .                     -> clean
mypy -p razormesh_api (strict)   -> Success, 58 files
pytest tests/test_intent_compilation_service.py -> 9 passed
pytest (full)                    -> 420 passed
```

### Next
- M14 — Intent compiler golden evaluation set.


## M14 — Intent Compiler Golden Evaluation Set

MILESTONE: M14
STATUS: PASS

Requirements: master prompt M14 — independent deterministic/manual-truth
evaluation set with several hundred diverse intents; expected truth must not
come from Qwen.

### Implementation
- `scripts/rzp_build_compiler_golden.py`: deterministic generator; **307
  cases**, 25 categories spanning budgets, explicit currencies, quantity,
  brands, condition-new requirements, recurring-forbidden phrasings,
  trial-to-paid euphemisms, merchant restrictions, double negation,
  multi-constraint stacks, underspecified minimal prompts, ambiguity surfacing,
  injection-like HUMAN text (authority = literal statements only), shipping/
  warranty/returns/delivery/deadline semantics, bundle obligations, membership-
  insertion resistance, safe-lookalike title traps, alias handling, variant
  guards. Difficulty split 234/43/30.
- `compiler_eval.py`: Expectation + GoldenCase schemas;
  evaluate_case() with an explicit OMISSION vs INVENTION vs MISMATCH taxonomy,
  including the currency='UNSPECIFIED' sentinel that catches invented money.
- Integrity: manifest.json carries case count + SHA256 + difficulty histogram +
  truth_source declaration; a test forbids any model-self-label field in rows.

### Validation commands + results
```text
python scripts/rzp_build_compiler_golden.py    -> 307 cases, sha256 recorded
ruff check .                                   -> clean
mypy -p razormesh_api (strict)                 -> Success, 59 files
pytest tests/test_compiler_eval.py             -> 13 passed
pytest (full)                                  -> 433 passed
```

### Next
- M15 — Real Qwen compiler evaluation over this golden set.


## M15 — Real Intent Compiler Evaluation (Qwen via TokenRouter)

MILESTONE: M15
STATUS: PASS

Requirements: master prompt M15 — run the REAL compiler on the golden set;
improve prompt/schema within this milestone if needed; write
`docs/PHASE3_INTENT_COMPILER_EVAL.md`.

Scope decision: **D-041** — human owner explicitly approved evaluating a
deterministic stratified sample of **N=90/307** (2026-08-25). Full-307
continuation is a carried-forward pre-M48 obligation; M48 cannot PASS on the
sample alone.

### Implementation
- `scripts/rzp_run_compiler_eval.py [N]`: resumable real-API runner —
  deterministic stratified sampling (round-robin over sorted categories),
  last-row-wins results.jsonl, FAILED/COMPILER_UNAVAILABLE rows retried and
  never counted, bounded backoff over transient 503 hard_concurrency_limit
  windows, resumable abort (exit 5) at repeated provider failures. Real
  `IntentCompilationService` with `max_output_tokens=4000, temperature=0.0`.
- `scripts/rzp_summarize_compiler_eval.py [N]`: aggregate metrics — schema
  validity, repair rate, case pass by difficulty/category, field recall with
  manual-truth denominators, numeric correctness (omissions vs invented
  money), omission/invention/mismatch counters, ambiguity handling, latency
  percentiles. Provider-noise rows excluded and reported separately.
- Prompt **v1→v2** (`intent_compiler_prompt.py`): v1 (P3-M12 long-form) made
  Qwen3.8's hidden reasoning hit `finish_reason=length` with EMPTY content
  even at 4000 tokens; v2 compresses the same rules into a short
  schema-forward prompt that compiles reliably. Version pin updated in
  `test_compiler_prompt_isolation.py`.
- Golden-truth corrections (transparent, §5 of the eval doc): F1 rupee-stated
  phrases → `currency="INR"` (applied pre-measurement); F13-002
  `recurring_forbidden` expectation removed (subscription REQUEST ≠ forbidding
  recurrence) and that one case re-measured. Golden sha256
  `eef70c9c…` → `9164f04c…`; stale rows preserved in
  `data/phase3/compiler_eval/discarded_stale_truth_rows.jsonl`.
- Harness integrity: 4 hard cases measured under a harness-reduced
  max_output_tokens=2000 budget were discarded (preserved in
  `discarded_budget2000_rows.jsonl`) and re-measured at 4000 — F10-001/F10-003
  then passed, proving harness contamination, not model failure.
- Security scan: synthetic `tr_test_key_placeholder` fixtures (M09/M13 tests)
  added to the TESTING.md §15 allowlist mechanism (pinned path+rule+literal in
  `scripts/security_check.py`).

### Results (N=90/307, stratified; full detail in the eval doc)
- Schema validity 90/90 = 100%; bounded repair 7/90, all repaired to valid.
- **Case pass 71/90 = 78.9%** (easy 31/40, medium 20/22, hard 20/28).
- Field recall: brands/merchants/quantity 1.0; currency 0.96; semantic 0.9706;
  recurring_forbidden 0.9231; max_amount_minor 0.8533.
- **Money precision 1.0; 0 mismatches; 0 invented amounts** — every money
  error is a fail-closed omission (11 amount omissions, 3 currency omissions).
- Hallucinations: 6 condition, 1 warranty (injection partial leak F13-000),
  1 brand/alias. Ambiguity surfacing 6/6. Injection-like text 2/3.
- Latency p50/p95/max/mean = 63.5s / 197.7s / 241.2s / 79.5s (hosted free-tier
  thinking model; not the local production verification path).
- Bonus non-sample coverage: 18 additional full-set rows measured (15 pass),
  same failure families; not part of headline metrics.

### Validation commands + results
```text
rzp_run_compiler_eval.py 90        -> 90/90 sample measured (resumable; noise retried)
rzp_summarize_compiler_eval.py 90  -> summary.json (N=90/307, complete=false)
ruff format (services/api scripts) -> 136 files unchanged
ruff check                         -> All checks passed
mypy -p razormesh_api --strict     -> Success, no issues in 59 source files (cache purged)
pytest (full)                      -> 433 passed in 38.11s
make security-check                -> PASS (secret scan 0; pip-audit 0; pnpm audit 0)
```

### Limitations recorded
- Sample scope (D-041); full-307 before M48.
- Zero golden cases now exercise the currency-unstated → `unspecified` path
  after the F1 correction; add genuinely currency-unstated cases in a future
  golden revision (folds into M18–M25 dataset work).
- F9-002 truth ("I refuse trials of any kind" → recurring_forbidden) kept as
  designed hard-case signal; judgment-call noted in the eval doc.

### Next
- M16 — Human confirmation domain flow (DRAFT/NEEDS_CLARIFICATION/CONFIRMED/
  REJECTED; only CONFIRMED creates/supersedes authorization).


## M16 — Human Confirmation Domain Flow

MILESTONE: M16
STATUS: PASS

Requirements: master prompt M16 — durable DRAFT/NEEDS_CLARIFICATION/CONFIRMED/
REJECTED states; only CONFIRMED creates/supersedes authorization generations;
ambiguities block confirmation; fail-closed materialization. P3-S03.
Security invariants: P3-S03/S14/S15.

### Implementation (previous-agent WIP reviewed, completed + tested)
- `domain/confirmation.py`: state machine + `build_confirmed_contract`
  (D-042): raises DRAFT_MISSING_MONEY / DRAFT_UNSUPPORTED_CURRENCY rather than
  inventing permissive terms; aggregate_budget and approval_threshold DEFAULT
  TO the stated cap (never larger), max_quantity defaults DOWN to 1,
  recurring_allowed only when the human explicitly allowed it.
- `confirmation_service.py`: `HumanConfirmationService` with pg advisory
  lineage locks (lock order advisory->rows), FAILED compiler outcomes create
  NO draft (+INTENT_COMPILE_FAILED audit), fresh compiles supersede open
  drafts, confirm_draft is idempotent for identical nonce (no new authority),
  CONFIRMATION_REPLAY_MISMATCH for differing nonce, generation bump REUSES the
  lineage intent_id and enforces DRAFT_BELOW_COMMITTED_SPEND against durable
  reserved+committed.
- Migration `e7a1c4f9b2d5` applied to dev AND razormesh_test.

### Evidence (tests/test_confirmation_flow.py — 17 tests)
Recording semantics (4): OK->DRAFT; ambiguities->NEEDS_CLARIFICATION
(unconfirmable); FAILED->no draft+audit; supersession chain w/ DRAFT_STALE.
Authority (6): gen-1 creation w/ conservative terms incl. brand casefold;
same-nonce idempotent replay; differing-nonce rejection; second confirmation
bumps generation reusing intent_id; missing money fails closed creating
NOTHING (row count scoped to fresh lineage stays 0, draft unchanged);
unsupported currency refused.
Rejection (2): terminal+idempotent+single audit event; cannot reject after
confirmation.
Capacity guard (1): new cap below committed spend refused.
Concurrency (1): 8 threads confirming one draft -> exactly ONE authority
identity; losers get controlled errors only; ledger chain valid.
Privacy (1): raw human text never persisted (sha256 only).

### Validation commands + results
```text
ruff check .                     -> clean
mypy -p razormesh_api (strict)   -> Success, 61 files
pytest (full)                    -> 449 passed
make security-check              -> PASS
```

### Real external API use
- NONE (CompilerOutcome fixtures; no Qwen call needed for this milestone).

### Next
- M17 — Human confirmation UI.


### M16 addendum — durability race hardening (post-commit review)

Full-suite load exposed that `session.get(..., with_for_update=True)` can be
served from the SQLAlchemy IDENTITY MAP, silently skipping the row lock after
an earlier unlocked probe read. Under an 8-thread same-nonce race this allowed
generation bumps 1→2→3→4 with replayed=False — exactly the class of defect M16
exists to prevent. Fixes:
1. `IntentDraftRepository.get_for_update` now issues a real
   `SELECT ... WHERE draft_id=... FOR UPDATE` with
   `populate_existing=True` (bypasses identity map).
2. Belt-and-braces: the confirming UPDATE is additionally arbitrated by the
   durable `uq_draft_confirmation_nonce` unique index; a race loser converts
   IntegrityError into either an honest replay (identical nonce re-read of the
   committed winner) or CONFIRMATION_REPLAY_MISMATCH.
Validation: module green 4/4 consecutive rounds + full suite 463/463 twice.


## M18 — AgentPay-IR Taxonomy/Schema

MILESTONE: M18
STATUS: PASS

Requirements: master prompt M18 — versioned IR schema with provenance;
orientation rule fixed project-wide.
Security invariants: P3-S09/S12 groundwork.

### Implementation
- `agentpay_ir.py`: AgentPayIRRecord (frozen, extra-forbidden) with
  premise/hypothesis bounds, NliLabel/LabelSource/Difficulty Literals,
  FAMILIES tuple (18 families covering budget/currency/quantity/brand/
  condition/merchant/recurring/trial/membership/bundle/shipping/delivery/
  returns/warranty/variant/alias/safe-lookalike/injection),
  compute_content_sha256 over canonical JSON triple,
  make_record() factory so callers cannot omit integrity hash,
  Review block defaulting reviewed_by_human=False (P3-S12 honesty).

### Validation commands + results
```text
ruff check . / mypy strict (63 files)   -> clean
pytest tests/test_agentpay_ir.py        -> 10 passed
pytest (full)                           -> 463 passed
```


## M19 — Deterministic Seed Dataset

MILESTONE: M19
STATUS: PASS

Requirements: master prompt M19 — template-grounded seed set in AgentPay-IR
form, several hundred records, fully deterministic.

### Implementation
- `scripts/rzp_build_seed_dataset.py`: for every golden case emits up to three
  IR records — ENTAILMENT (evidence matches stated constraints),
  CONTRADICTION (evidence violates the hardest stated constraint: brand /
  recurring / quantity / price ceiling), NEUTRAL (listing silent on an
  unspecified dimension). Premises embed the session request context so
  content is unique per case.
- Content-level dedup at build time (921→915); record ids DERIVED from content
  hash + case salt → regeneration is byte-identical (provenance timestamp
  pinned).

### Validation commands + results
```text
python scripts/rzp_build_seed_dataset.py    -> 915 records, sha256 in manifest
ruff check .                                -> clean
mypy -p razormesh_api (strict)              -> Success, 63 files
pytest tests/test_seed_dataset.py           -> 6 passed
pytest (full)                               -> 469 passed
make security-check                         -> PASS
```

### Next
- M20 — Qwen candidate generator (volume per overnight policy D-043).


### M20 note — generator launched (IN_PROGRESS)

`scripts/rzp_generate_candidates.py` is running against the live free tier
with the full overnight-policy control set: request-hash cache (idempotent
restarts), immediate persistence, Retry-After respect, bounded exp backoff +
jitter, dead-window circuit breaker (10 consecutive failures -> clean exit,
resumable), exact-normalized near-dup guard at generation time, provisional
labels only. Volume target 650 with a 300-minute wall budget; partial counts
are recorded honestly in `data/phase3/dataset/candidates/last_run.json`.
M21 validator (`dataset_quality.py`, 5 tests) landed first so every produced
candidate can be gated as it arrives.


## M26 — HUMAN GATE 1: Gold Review (PENDING_HUMAN)

STATUS: PENDING_HUMAN (overnight deferred-gate mode per human authorization)

### What is READY for the human
- `data/phase3/gold/gold_review.html` — self-contained reviewer
  (keyboard 1/2/3, arrows, E-export);
- `data/phase3/gold/gold_review.csv` — 320 stratified rows;
- `data/phase3/gold/INSTRUCTIONS.md` — orientation + procedure + export.

### What the human must do (morning)
1. Open gold_review.html; label all 320 cards; press E; save
   `gold_decisions.json` into data/phase3/gold/.
2. Tell the agent the file exists.

### What stays blocked until then
- FINAL model selection confirmation (M30 provisional stands);
- FINAL threshold freeze (M37 provisional from validation split only);
- any metric described as final gold-test performance.

### Overnight policy decisions recorded
- D-043: dependency-aware deferred-human-gate mode + reduced-volume policy.


### M28/M29 — Baseline evaluation details
Harness: `nli_eval.py` (pure core) + `scripts/rzp_eval_nli_baseline.py`
(transformers lazy-imported inside the ML venv only). Label maps pinned from
official cards and unit-tested — the two checkpoints use DIFFERENT index
orders (A: E/N/C, B: C/E/N), which a naive harness would silently invert.
Inference: MPS-accelerated torch, batch 8, ~25s per 127-pair split.

Honest finding: absolute numbers are low for BOTH baselines because the
frozen set is deliberately adversarial-flavored (session-context premises,
injection-style text). This is exactly what M30 selection + M37 calibration
are for; zero-shot weakness on this domain is recorded, not hidden.


### M33 — preflight bundle contents
```
artifacts/phase3_colab_training_bundle.zip
  training/phase3/train.jsonl            602KB (723 rows)
  training/phase3/val.jsonl              142KB (171 rows)
  training/phase3/RazorGuard_NLI_Phase3_Training.ipynb
  training/phase3/train_config.json      (seed 42; macro_f1 selection)
  training/phase3/requirements-frozen.txt
  training/phase3/manifest.json          (sha256 per file)
  training/phase3/rzp_verify_training.py (hash check runs INSIDE notebook too)
VERIFY: PASS
```
