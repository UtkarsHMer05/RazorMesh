# Phase-3 independent re-audit — 2026-08-27

Status: **INCOMPLETE / release blocked.** This audit supersedes the blanket
50/50 acceptance claim, not the preserved historical measurements. No push,
new Phase-4 implementation, retraining, or real payment was performed.

## Scope and reproducibility

Inspected checkout: `a31c1e3` plus existing uncommitted changes. The owner
requested three `gpt-5.6-sol` low-reasoning audit agents: backend, data/ML,
and UI. Their initial audits were read-only. The Phase-3 master prompt was
read completely; existing governance and the redesign evidence were inspected.
`RazorMesh_UI_Redesign_Master_Prompt.md` was not present; the available final
Bauhaus specification and implementation are the incumbent visual reference.

Unrelated work was present and changed during the audit:

- `data/phase3/dataset/seed/manifest.json`
- `services/api/src/razormesh_api/protocol/agentpay_x.py`
- `services/api/tests/phase4/test_agentpay_x.py`

These edits were not reverted or included in this audit's intended change set.
The inherited seed determinism test invokes the builder against the repository
and regenerates the already-dirty manifest timestamp; dataset bytes remain
identical. The timestamp is left unstaged rather than inventing/restoring an
unknown pre-audit value. That test should use a disposable output directory at
its own data gate. Existing
Phase-4 commits were preserved. No statement that Phase 4 was never implemented
can be made about this checkout.

Secret preflight: root `.env` is ignored by `.gitignore:6`; the exact private
bootstrap path is excluded by `.git/info/exclude:49`; `git ls-files` and
`git log --all -- PHASE3_PRIVATE_BOOTSTRAP_LOCAL_ONLY.md` return no entries.
The private bootstrap was already removed at historical M10; no value was read
or printed and no credential reinjection was necessary.

## Reproduced findings and owning gates

| Gate | Finding | Required repair / proof |
|---|---|---|
| M15 | Old evaluator labels wrong-but-present money/currency/quantity as omissions. Stored results omit the actual compiler payload, so zero recorded mismatches does not establish zero numeric substitutions. Report also claims brand precision 1.0 despite an invented brand. | Correct taxonomy/denominators; disclose unrecoverable historical metrics; preserve raw evidence and capture sufficient synthetic payload evidence in future runs. Do not manufacture a historical rescore. |
| M16 | Confirmation drops merchant names, semantic restrictions, and product scope. Adding those restrictions yields the same executable contract/hash. | Persist/hash/enforce every confirmed restriction, or refuse unsupported authority; test confirmation through checkout. |
| M17 | UI generates UUID-hex principal/agent IDs, but backend requires Crockford ULIDs. ID conversion occurs after compiler invocation. | Backend-issued stable IDs or validated domain IDs before any provider call; real route-boundary regression. |
| M17 | Confirmed AI intent is local to the panel; checkout only receives fixture intent IDs. | Wire confirmed intent/generation into the buyer journey; invalidate stale tickets/checkout state when authority changes. |
| M19 | Seed determinism test regenerates repository artifacts rather than using its temporary directory; manifest timestamp changes during regression. | Redirect generator output to temporary paths and assert both data and manifest determinism without modifying user artifacts. |
| M25–M27, M36–M37 | The 79 reviewed non-training cards include 43 validation cards used by selection/calibration. | Correct split-role semantics and freeze a genuinely new human-reviewed evaluation set. No retrospective untouched claim. |
| M30 | Baseline selection substitutes neutral precision for directly measured safe-lookalike FPR, defers calibration, and does not supply the originally required baseline-evaluation report. | Re-run original comparison criteria on appropriately separated data; preserve provisional vs final selection distinctions. |
| M31–M35 | Historical distributed ZIPs contain an empty dependency file while the later directory/manifest has a populated file. | Preserve training-used archive provenance; create and verify a separately versioned repaired bundle. Directory verification is not ZIP verification. |
| M37 | Entailment threshold sweep optimizes only BLOCK outcomes; all entailment thresholds tie and the first value wins. | Calibrate PASS and uncertainty handling explicitly on validation only, before new final evaluation. |
| M38 | Model/policy hash agreement is not checked; label-map fallback can mask missing labels; NaN probability input can produce PASS. | Validate artifact/labels/finite normalized probabilities, bounded inputs and explicit device/batch behavior; provenance in verdicts. |
| M39 | Evidence builder always invents a new-only condition hypothesis. | Derive every hypothesis from explicit confirmed constraints; test unspecified and used/refurbished authorizations. |
| M40–M44 | Production checkout only executes money/catalog/policy rules; no production call to evidence builder/verifier/fusion/audit helpers. | Integrate semantic stage before final decision/ticket; prove BLOCK/CHALLENGE/unavailable inference has zero ticket/provider effects. Pure fusion tests alone are insufficient. |
| M43 | Semantic UI state is permanently null; buyer/lab/audit omit required real semantic evidence. | Render backend model/hash/pairs/probabilities/thresholds and hard/semantic/final decisions. |
| M45 | Executable runner counts entailment→BLOCK as unsafe allow, not contradiction→ALLOW. | Fix classification and test all label/action combinations; do not just patch Markdown terminology. |
| M45–M46 | Runner uses simulated hard ALLOW and NLI scores, not actual trust/executor/provider flow. Required A–E variants and ablation report are missing. | Real-pipeline benchmark with expected labels isolated from decisions, actual effects, safe completion, uncertainty, family and compiler metrics. |
| M47 | Required performance artifact is absent; limited timing does not establish the full original resource/quality gate. | Record measured cold/warm percentiles, memory, device/batch scope and justified optimization choices. |
| M48–M50 | Frontend was excluded from prior rerun; M49 merely reused historical evidence; M50 still contains contradictory coverage and completion claims. | Rerun full quality/security and disposable-state acceptance after fixes; regenerate M50 only after all required gates genuinely pass. |

### Reviewed-data facts

ID intersection with the frozen dataset (not inferred from report labels):

| Actual role | Split size | Reviewed example IDs | Frozen labels matching human labels |
|---|---:|---:|---:|
| `human_reviewed_training` | 723 | 241 | 236 |
| `human_reviewed_validation` | 171 | 43 | 42 |
| `human_reviewed_test_previously_examined` | 127 | 36 | 35 |

All 320 examples were reviewed, but those are not 320 untouched final-test
examples. Training used frozen dataset labels; reviewed ID overlap does not
prove human corrections replaced those labels. Seven frozen labels differ from
the human decisions. The 43 validation examples influenced checkpoint selection
and threshold calibration through the validation split. D-046 also explicitly
cited the combined 79-card results during final model selection. D-050's
contrary transparency-only assertion is unsupported and must not be repeated.
Even the 36 test-only examples have been inspected; they are not a new blind
acceptance set for subsequent adjustments.

The 129-row OOD matrix is agent-curated template truth, not human review. It
has already been evaluated. Its report incorrectly credits neutral→PASS:
10/43 neutral cases PASS, four contradiction cases PASS, 30 neutral cases
BLOCK, and seven entailment cases BLOCK. The first two categories are unsafe
or insufficient-evidence **semantic passes**, not measured payment executions;
the latter two are conservative over-blocks. A new independent human-reviewed
set is required before final acceptance; do not relabel these observed rows
as an untouched test after using their outcomes to change the model/policy.

### UI-specific findings

Preserve the current Bauhaus identity; these are functional repairs, not a new
redesign. The Impeccable audit found:

- Audit input uses fixed `22rem` width. At 390×844, document scroll width is
  427px; the input extends to x=427. Bound its width to its container.
- Buyer treats an empty product list as perpetual loading even after fetch
  failure. Separate pending/error/empty states and provide retry.
- Stubbed checkout E2E intercepts all backend requests. Its green result is
  component-flow evidence, not proof of live FastAPI integration.

Positive evidence: existing styling is coherent; the detector returned no
findings on the inspected buyer/lab/audit/navigation components. The critical
failures are data/authority wiring, not a reason to replace the visual system.
This was a bounded functional/responsive audit, not a complete WCAG certification
or performance profile; no unsupported 20-point visual score is assigned.

## Validation actually run

- Main: `services/api/.venv/bin/pytest -q` from `services/api` — **FAIL during
  collection**, concurrent Phase-4 `agentpay_x.py` imports `_IRAuthorization`
  from a module that does not export it. No test pass is inferred from this run.
- Main: `.venv/bin/ruff check src tests` — **FAIL**, 23 reported findings in
  the changing Phase-4 files at inspection time, including undefined names.
  The chained type/format checks did not run after this failure.
- Main: `.venv/bin/pytest --ignore=tests/phase4 -q` — **exit 0**. This is scoped
  Phase-1/2/3 regression evidence, not the full-worktree gate.
- Backend audit: 61 compiler/confirmation/evidence/policy/lab/isolation tests
  passed, while pure reproductions demonstrated dropped restrictions and
  invented hypotheses. Existing green tests miss the release-blocking paths.
- UI audit: Vitest 14/14; scoped Phase-3 ESLint and fresh TypeScript check pass;
  smoke/stubbed checkout E2E 10/10. Full ESLint fails on existing
  `apps/web/src/app/protocols/page.tsx:139` (effect state update).
- Browser: buyer desktop/mobile and audit mobile inspected without compiler,
  payment, or provider writes.
- `python3 scripts/security_check.py` — **PASS**, zero secret findings,
  clean Python dependency audit and frontend production dependency audit.

## M15 repair checkpoint

The evaluator now distinguishes missing values from wrong-present numeric,
currency and quantity substitutions. The summarizer reports exact recoverable
field counts and unknown metrics explicitly; historical brand precision is
54/55 (0.9818), not 1.0. Future runs use a separate versioned append-only
directory with validated synthetic payloads and golden/prompt/model/schema
provenance. Resume rejects incompatible evidence and coverage requires the
exact expected case-ID set. Historical result JSONL and golden data are preserved.

Initial main-agent verification: `.venv/bin/pytest tests/test_compiler_eval.py
-o addopts='' -q` — **20 passed**. Follow-up adds two negative tests for changed
golden provenance and versioned records without payloads; the summarizer rejects
both rather than attributing them to the current truth. Scoped strict mypy,
Ruff check and all four changed Python files' format checks pass. The offline
summary still contains 307 historical cases, explicitly not rescored. This is
not a fresh real 307-case measurement. M15 remains IN_PROGRESS; no closure
commit is justified.

Final targeted regression after that follow-up: compiler evaluation, compilation
service, prompt isolation, buyer draft routes, confirmation flow and inherited
buyer routes — **65 passed in 10.46s**. Command from `services/api`:
`.venv/bin/pytest tests/test_compiler_eval.py tests/test_intent_compilation_service.py
tests/test_compiler_prompt_isolation.py tests/test_buyer_drafts_api.py
tests/test_confirmation_flow.py tests/test_buyer_api.py -o addopts='' -q`.

## Next actions

Resolve shared-worktree concurrency before final whole-repository gates.
Repair M15 evidence first, then confirmation authority and UI, one milestone
at a time. Preserve the historical frozen training data/model/thresholds until
their own gate is reopened. Obtain genuinely independent human review before
restoring final ML claims. Full completion, a new closure commit, and Phase-4
approval are not justified by this audit.
