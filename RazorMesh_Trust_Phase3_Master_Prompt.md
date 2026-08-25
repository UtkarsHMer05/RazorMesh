# RazorMesh Trust — Phase 3 Autonomous AI/ML Master Prompt
## Qwen Intent Compiler + AgentPay-IR + DeBERTa NLI + Conservative RazorGuard Fusion
### 50 Gated Milestones — Exactly One Milestone at a Time

**Date:** 2026-08-25  
**Active phase:** Phase 3 only  
**Previous phase:** Phase 2 — Razorpay Test Mode integration — reported 50/50 PASS  
**Primary objective:** add meaningful AI/ML without weakening the deterministic trust and payment boundary already proven in Phases 1–2.

---

# 0. NON-NEGOTIABLE OPERATING CONTRACT

You are the autonomous principal engineer for Phase 3 of RazorMesh Trust.

You must work as a senior backend engineer, AI/ML engineer, NLP/NLI researcher, dataset engineer, security engineer, evaluation engineer, frontend engineer, QA engineer, reproducibility owner, and documentation owner.

Do not "add AI quickly." Build a measurable and explainable trust layer.

Core rule:

> **The AI proposes. RazorGuard authorizes. The trusted executor executes.**

The AI layer may interpret language and generate semantic evidence. It may never:
- call Razorpay or PaymentProvider directly;
- create payment authority;
- bypass RazorGuard;
- weaken a deterministic BLOCK or CHALLENGE;
- silently convert uncertainty into ALLOW;
- replace execution-ticket, replay, context-binding, reservation, webhook, or reconciliation controls;
- expose any secret to the browser;
- fabricate model or benchmark metrics.

Phase 3 uses two AI components:

1. **Intent Compiler** — Qwen 3.8 Max Free through TokenRouter using its OpenAI-compatible Chat Completions endpoint.
2. **Semantic Verifier** — DeBERTa-v3-base NLI, selected by evidence from two public NLI baselines and fine-tuned on AgentPay-IR only if fine-tuning improves the held-out human-reviewed evaluation.

The implementation must remain provider/model-abstracted.

---

# 1. PHASE-2 BASELINE MUST BE RE-PROVEN

The human reports that Phase 2 ended with all 50 milestones PASS, real Razorpay Test Mode success/failure evidence, exactly-once settlement, provider-unknown recovery, webhook/callback signature validation, concurrency tests, Security Lab, tamper-evident audit, clean audits, and 353/353 pytest at final close.

Treat those as reported facts, not permission to skip validation.

Before modifying AI, data, backend, frontend, or payment logic:
- inspect Git;
- read Phase-1/2 completion artifacts;
- rerun the complete current backend and frontend quality/security gates;
- verify Razorpay Test Mode guard and payment-security invariants using safe/read-only/mock methods;
- repair any regression first.

Phase 3 must not start on a broken Phase-2 foundation.

---

# 2. READ EXISTING GOVERNANCE BEFORE CODE

Read repository documents in the precedence defined by `AGENTS.md`, including at least:

`AGENTS.md`, `RULES.md`, `PRD.md`, `PHASES.md`, `SECURITY.md`, `ARCHITECTURE.md`, `DESIGN.md`, `DECISIONS.md`, milestone files, `TESTING.md`, `VERSION_MANIFEST.md`, `RESEARCH.md`, Phase-1/2 status files, `MEMORY.md`, `AI_WORKFLOW.md`, and Phase-2 completion/evidence reports.

Do not erase prior history.

If a later explicit human decision conflicts materially with this prompt, stop and report the conflict rather than silently changing scope/security.

---

# 3. PHASE-3 MODEL ARCHITECTURE

## Intent Compiler

Primary:
`qwen/qwen3.8-max-free`

Provider:
TokenRouter

Base URL:
`https://api.tokenrouter.com/v1`

Current documented API family:
OpenAI-compatible `POST /v1/chat/completions`

Purpose:

```text
trusted human natural-language authorization
        ↓
Qwen Intent Compiler
        ↓
strict IntentDraft
        ↓
schema/domain validation
        ↓
human review + confirmation
        ↓
IntentContract authority
```

Qwen never creates authority by itself.

Do not fine-tune Qwen in Phase 3.

## Semantic Verifier

Benchmark both before training:

A. `MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli`  
B. `cross-encoder/nli-deberta-v3-base`

NLI labels:
- entailment
- neutral
- contradiction

Select the better domain baseline using frozen evaluation criteria. Fine-tune only that baseline.

## Final authority

The semantic model is allowed to make the final decision stricter, never looser.

Required fusion invariant:

```text
hard BLOCK      + anything           → BLOCK
hard CHALLENGE  + semantic BLOCK     → BLOCK
hard CHALLENGE  + otherwise          → CHALLENGE
hard ALLOW      + semantic BLOCK     → BLOCK
hard ALLOW      + semantic CHALLENGE → CHALLENGE
hard ALLOW      + semantic PASS      → ALLOW
```

No probability combination may turn hard BLOCK/CHALLENGE into ALLOW.

---

# 4. RESEARCH BASIS TO RECORD AND LIVE-VERIFY

Use current authoritative pages/papers and record dates/findings in `RESEARCH.md`.

- PlanGuard: https://arxiv.org/abs/2604.10134  
  Principle: context isolation; hard constraints first; semantic verifier second.
- AgentVisor: https://arxiv.org/abs/2604.24118  
  Principle: treat the agent as untrusted; keep privileged execution in a separate trusted boundary.
- Policy-Invisible Violations: https://arxiv.org/abs/2604.12177  
  Principle: enforcement needs policy-relevant world state; human-reviewed labels matter.
- Zero-Trust Runtime Verification for Agentic Payments: https://arxiv.org/abs/2602.06345  
  Principle: model quality does not replace runtime context binding/replay/consume-once enforcement.
- Protocol-Level Attacks on Agentic Commerce: https://arxiv.org/abs/2607.21824  
  Principle: structural failures are model-independent; AI must complement structural controls.

Current model/provider sources to re-check:
- TokenRouter Qwen free model: https://www.tokenrouter.com/models/qwen/qwen3.8-max-free/
- MoritzLaurer DeBERTa: https://huggingface.co/MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli
- Cross-encoder DeBERTa: https://huggingface.co/cross-encoder/nli-deberta-v3-base

Never trust version numbers from chat memory. Resolve current stable/supported/security-compatible packages live and update `VERSION_MANIFEST.md`.

---

# 5. PRIVATE TOKENROUTER BOOTSTRAP

A local-only file named:

`PHASE3_PRIVATE_BOOTSTRAP_LOCAL_ONLY.md`

contains the human's temporary test TokenRouter credential.

Before reading its values:
1. verify it is not tracked;
2. add its exact filename to `.git/info/exclude` if needed;
3. verify root `.env` is ignored;
4. never print the value;
5. merge its three variables into root `.env`;
6. preserve all Phase-1/2/Razorpay variables;
7. update `.env.example` with BLANK placeholders only;
8. verify TokenRouter through a safe authentication/model probe;
9. after successful probe delete the private bootstrap file;
10. prove it never entered tracked files/history/logs.

Expected keys:
`TOKENROUTER_API_KEY`, `TOKENROUTER_BASE_URL`, `PLANNER_MODEL`.

Do not create `NEXT_PUBLIC_TOKENROUTER_API_KEY`.

---

# 6. AGENTPAY-IR DATASET

Create **AgentPay-IR — Agentic Payment Intent–Reality**.

It is synthetic + human-reviewed research data. Never imply it is Razorpay proprietary data.

Fixed NLI orientation:

- **Premise:** current trusted/sanitized commerce evidence.
- **Hypothesis:** one normalized statement derived from confirmed human authorization.
- **Label:** entailment / neutral / contradiction.

Examples:

Premise: `The product condition is manufacturer refurbished.`  
Hypothesis: `The purchased product is new.`  
Label: `contradiction`

Premise: `The purchase includes a free trial that renews for INR 499 each month.`  
Hypothesis: `The purchase has no recurring commitment.`  
Label: `contradiction`

Premise: `Seller: SuperElectronics Online.`  
Hypothesis: `The seller is an authorized Sony retailer.`  
Label: `neutral`

Never reverse pair orientation between training and inference.

Primary semantic families:
- product condition;
- brand/product identity;
- seller/merchant identity;
- seller authorization ambiguity;
- bundle semantics;
- recurring subscription;
- trial-to-paid renewal;
- membership insertion;
- euphemistic recurring commitment;
- semantic shipping/fee obligations;
- delivery timing when explicitly constrained;
- return/refund restriction when explicitly constrained;
- warranty when explicitly constrained;
- category/variant mismatch;
- merchant aliases;
- product aliases;
- misleading negation/double negation;
- prompt-injection-like merchant text;
- ambiguous evidence;
- safe semantic lookalikes.

Do not waste NLI capacity duplicating simple exact amount/currency arithmetic already handled deterministically.

Every row must have provenance metadata:
`example_id`, `pair_id`, `family`, `premise`, `hypothesis`, `label`, `source_type`, `generator`, `generator_model`, `template_family`, `difficulty`, `safe_lookalike_id`, entity-family fields, adversarial flag, human-review status, split, dataset version, content hash.

---

# 7. DATASET GENERATION AND SPLITS

Target only as much data as remains high quality. Approximate goals:
- 1.5k–3k deterministic/template-grounded examples;
- 7k–12k Qwen candidate/paraphrase examples;
- 2k–4k hard/adversarial examples;
- 300–500 human-reviewed gold examples;
- roughly 10k–18k final usable examples after filtering.

Pipeline:

```text
taxonomy
→ deterministic seed
→ Qwen candidates/paraphrases
→ schema validation
→ label-consistency checks
→ rejection logging
→ exact/near dedup
→ leakage-safe grouping
→ train/val/test split
→ human-reviewed gold subset
```

Random row split is forbidden.

Group split by template/generator-parent/entity/safe-lookalike families. Pair siblings may not cross train/test.

Write automated leakage tests.

Qwen-generated label is provisional, never automatically gold truth.

---

# 8. GOLD HUMAN REVIEW

A human-reviewed held-out subset is required for credible claims.

Create an easy review artifact, preferably:
- CSV; and
- a local HTML review tool if useful.

Target 300 minimum, 500 preferred if time allows.

Stratify labels, major families, difficulty, safe lookalikes, adversarial-looking text, and ambiguity.

At the gate, stop and give the human exact review/save path. Do not require thousands of labels.

Final model selection must reference human-reviewed gold results.

---

# 9. BASELINE MODEL SELECTION

Evaluate both DeBERTa candidates on identical frozen data.

Metrics:
- accuracy;
- macro precision/recall/F1;
- per-class precision/recall/F1;
- contradiction recall;
- neutral recall;
- entailment precision;
- confusion matrix;
- calibration error;
- Brier score or equivalent;
- family breakdown;
- safe-lookalike false positive rate;
- latency and memory.

Prioritize security/utility, not raw accuracy:
1. contradiction recall;
2. neutral handling;
3. safe-lookalike FPR;
4. macro F1;
5. calibration;
6. resource cost.

Freeze the selected baseline in `DECISIONS.md`.

---

# 10. TRAINING

Do not train from scratch.

Fine-tune the selected baseline in Google Colab.

The notebook must be self-contained and reproducible:
- install exact dependencies;
- verify GPU;
- verify dataset SHA-256 and split manifest;
- set seeds;
- load baseline revision;
- preserve label mapping;
- tokenize premise/hypothesis pairs consistently;
- use bounded hyperparameter comparison;
- evaluate during training;
- early-stop;
- save best checkpoint;
- save tokenizer/config;
- evaluate frozen gold test once appropriately;
- save metrics/confusion/calibration artifacts;
- save dependency/runtime manifest;
- export `razorguard_nli_artifact.zip`;
- generate hashes.

Start with max sequence length around 256 unless data proves 512 is needed.

Use FP16 on supported Colab GPU.

Use gradient accumulation if needed.

No endless hyperparameter search.

Fine-tuned model is selected only if held-out evidence shows meaningful security/utility improvement. Otherwise retain the better zero-shot baseline and document that training did not justify replacement.

---

# 11. SEMANTIC POLICY

Do not use argmax blindly.

Calibrate thresholds on validation data.

Conceptual policy:

```text
strong contradiction → semantic BLOCK
neutral / ambiguous / low confidence → semantic CHALLENGE
strong entailment → semantic PASS
```

Freeze thresholds with model/hash/version.

Do not tune thresholds after looking repeatedly at final gold-test labels.

If inference/model unavailable:
fail to CHALLENGE or another documented fail-closed state, never silent ALLOW.

---

# 12. INTENT COMPILER

Intent Compiler input = trusted user authorization text only.

Do not feed merchant pages/product descriptions into it.

It creates a versioned `IntentDraft`, separating:
- hard structured constraints;
- semantic constraints;
- ambiguities;
- unspecified fields.

It must not invent constraints.

If the user says only `Buy headphones under ₹5,000`, do not silently invent Sony/new/no-subscription unless a documented visible default exists.

Use strict parse + Pydantic/domain validation.

TokenRouter currently documents OpenAI-compatible Chat Completions, but do not assume strict server-side JSON Schema support. Probe it.

Safe fallback:
`Qwen → JSON extraction → Pydantic → one bounded repair → fail closed`.

Evaluate compiler separately:
schema validity, field precision/recall, numeric extraction, unsafe omission, hallucinated constraints, over-constraint, ambiguity handling, repair rate, latency, provider failure rate.

---

# 13. CONTEXT ISOLATION

Qwen Intent Compiler sees:
- trusted human instruction;
- schema/system instructions.

It must not see:
- merchant prompt-injection text;
- arbitrary untrusted product text;
- Razorpay secrets;
- TokenRouter key;
- execution signing keys;
- webhook secret.

Implement deterministic `SemanticEvidenceBuilder`.

Hypotheses originate from confirmed human authorization only.

Premises originate from current sanitized commerce evidence with provenance.

The semantic verifier is pure inference:
- no provider client;
- no payment tool;
- no direct DB mutation.

---

# 14. MODEL ARTIFACTS AND LOCAL INFERENCE

Do not commit huge model weights blindly.

Commit manifests/hashes/metrics/config/license/source references.

Prefer artifacts directory with ignored weights as needed.

Test local inference first:
1. CPU;
2. MPS if stable;
3. ONNX;
4. quantized ONNX if it preserves quality.

Measure cold start, warm p50/p95, memory, batch behavior, accuracy drift.

Do not add Modal unless measured local inference is unacceptable.

If Modal becomes genuinely necessary, stop at a conditional human gate and explain expected benefit/cost before asking for account credentials.

---

# 15. HUMAN GATES

Only genuine gates:

### Gate 1 — Gold review
Agent creates review pack → human labels/reviews 300–500 stratified examples → reply `gold review complete`.

### Gate 2 — Colab training
Agent creates notebook + bundle → human opens in Colab → selects GPU → uploads bundle if needed → Run all → waits → downloads `razorguard_nli_artifact.zip` → places it at agent-specified path → replies `training artifact ready`.

### Gate 3 — Conditional compute
Only if free Colab/local inference cannot complete requirements.

### Gate 4 — Phase 4 approval
After M50.

No TokenRouter human gate unless the already-supplied test credential fails and account action is genuinely needed.

---

# 16. GIT AND MILESTONE DISCIPLINE

The human authorizes local milestone commits after PASS.

Never push.

Exactly one milestone at a time.

For each milestone:

```text
read governance
→ verify previous PASS
→ map requirements/invariants
→ inspect implementation
→ research if needed
→ define tests
→ implement ONLY current milestone
→ format
→ lint
→ typecheck
→ unit/integration/security/data/ML/frontend tests as applicable
→ Phase-1/2 regression subset
→ inspect actual output
→ update docs/status/memory
→ PASS?
    no: repair/retest
    yes: local commit
→ next milestone
```

Do not batch three milestones together.

Do not claim future milestones PASS because current work partially touched them.

After five serious failed repairs for one root cause, stop with a blocker report.

---

# 17. PHASE-3 SECURITY INVARIANTS

P3-S01 TokenRouter secret backend-only.  
P3-S02 Qwen sees only trusted human intent.  
P3-S03 AI draft is not authority before human confirmation.  
P3-S04 Merchant/untrusted text cannot mutate confirmed IntentContract.  
P3-S05 Semantic hypotheses derive only from confirmed authorization.  
P3-S06 Semantic verifier has no payment/provider privilege.  
P3-S07 Semantic model can never weaken hard RazorGuard decision.  
P3-S08 Inference failure never silently ALLOWs.  
P3-S09 Gold labels never leak into training/threshold tuning.  
P3-S10 Fine-tuned model selected only by held-out evidence.  
P3-S11 Split leakage prevented/tested.  
P3-S12 Qwen dataset labels are not automatic truth.  
P3-S13 Model/hash/threshold version audit-visible.  
P3-S14 TokenRouter outage cannot bypass human confirmation.  
P3-S15 Phase-1/2 runtime payment guarantees unchanged.  
P3-S16 AI cannot call Razorpay.  
P3-S17 Untrusted content cannot enter privileged compiler context.  
P3-S18 NLI-only never production payment authority.  
P3-S19 Semantic false positives measured/disclosed.  
P3-S20 No fabricated metrics.

---

# 18. REQUIRED DOCUMENTS

Create/preserve:
- `PHASE3_STATUS.md`
- `PHASE3_MILESTONES.md`
- `docs/PHASE3_BASELINE.md`
- `docs/AGENTPAY_IR_DATASET_CARD.md`
- `docs/PHASE3_INTENT_COMPILER_EVAL.md`
- `docs/PHASE3_NLI_BASELINE_EVAL.md`
- `docs/PHASE3_NLI_FINETUNE_EVAL.md`
- `docs/PHASE3_ABLATION_REPORT.md`
- `docs/PHASE3_PERFORMANCE.json`
- `docs/PHASE3_COMPLETION_REPORT.md`

Update governance whenever affected:
`PRD.md`, `PHASES.md`, `ARCHITECTURE.md`, `SECURITY.md`, `DECISIONS.md`, `TESTING.md`, `VERSION_MANIFEST.md`, `RESEARCH.md`, `MEMORY.md`, `DESIGN.md`.

Status entries must include requirements, invariants, implementation, files, research, exact validation, model/data artifacts+hashes, external API use, human gate, regression, decisions, limitations, commit, next milestone.

Never include secrets.

---


# 19. THE 50 PHASE-3 MILESTONES


## M01 — Repository, governance, and secret-safety inspection

Inspect the entire repository, Git state, branches, Phase-2 completion artifacts, modified/untracked files and current governance. Verify `.env` is ignored, the private Phase-3 bootstrap is not tracked, no TokenRouter secret is in frontend or tracked text, and no unrelated user work is at risk. Create `PHASE3_STATUS.md` skeleton only after understanding repository conventions. Acceptance: repository state understood, prior history preserved, secret safety proven.

### Mandatory milestone gate
For this milestone, before PASS:
1. inspect `git status`;
2. define/confirm acceptance tests;
3. implement only this milestone;
4. format/lint;
5. strict typecheck;
6. run narrow unit tests;
7. run integration/security/data/ML/frontend tests relevant to this milestone;
8. run the required Phase-1/2 regression subset;
9. inspect actual outputs/artifacts rather than assuming success;
10. update PHASE3_STATUS + MEMORY and all affected governance/research/version docs;
11. verify docs match code;
12. only then mark PASS and create one local milestone commit;
13. never push.

If any step fails, repair and rerun this same milestone. Do not begin the next milestone.



## M02 — Full Phase-1/2 backend regression

Run the current complete backend quality/security suite: Ruff/format, strict mypy, full pytest, Hypothesis/stateful tests, concurrency, execution-ticket/replay, provider, callback/webhook signature, reconciliation, audit, dependency/security checks. Understand any test-count drift instead of forcing historical counts. Repair any regression before continuing.

### Mandatory milestone gate
For this milestone, before PASS:
1. inspect `git status`;
2. define/confirm acceptance tests;
3. implement only this milestone;
4. format/lint;
5. strict typecheck;
6. run narrow unit tests;
7. run integration/security/data/ML/frontend tests relevant to this milestone;
8. run the required Phase-1/2 regression subset;
9. inspect actual outputs/artifacts rather than assuming success;
10. update PHASE3_STATUS + MEMORY and all affected governance/research/version docs;
11. verify docs match code;
12. only then mark PASS and create one local milestone commit;
13. never push.

If any step fails, repair and rerun this same milestone. Do not begin the next milestone.



## M03 — Full Phase-1/2 frontend/E2E regression

Run frontend lint, TS typecheck, production build, unit/component tests, Playwright, accessibility/secret scans already established. Verify buyer/merchant/security-lab/audit baseline. No AI changes until green.

### Mandatory milestone gate
For this milestone, before PASS:
1. inspect `git status`;
2. define/confirm acceptance tests;
3. implement only this milestone;
4. format/lint;
5. strict typecheck;
6. run narrow unit tests;
7. run integration/security/data/ML/frontend tests relevant to this milestone;
8. run the required Phase-1/2 regression subset;
9. inspect actual outputs/artifacts rather than assuming success;
10. update PHASE3_STATUS + MEMORY and all affected governance/research/version docs;
11. verify docs match code;
12. only then mark PASS and create one local milestone commit;
13. never push.

If any step fails, repair and rerun this same milestone. Do not begin the next milestone.



## M04 — Phase-2 real-provider integrity revalidation

Without unnecessary new payments, revalidate Test Mode guard, mock-vs-real provider boundary, live-key rejection, webhook fixture verification, duplicate/out-of-order semantics, provider-unknown recovery, reservation invariants, audit chain and a safe read-only Razorpay authentication diagnostic if available. Acceptance: Phase-2 payment security intact.

### Mandatory milestone gate
For this milestone, before PASS:
1. inspect `git status`;
2. define/confirm acceptance tests;
3. implement only this milestone;
4. format/lint;
5. strict typecheck;
6. run narrow unit tests;
7. run integration/security/data/ML/frontend tests relevant to this milestone;
8. run the required Phase-1/2 regression subset;
9. inspect actual outputs/artifacts rather than assuming success;
10. update PHASE3_STATUS + MEMORY and all affected governance/research/version docs;
11. verify docs match code;
12. only then mark PASS and create one local milestone commit;
13. never push.

If any step fails, repair and rerun this same milestone. Do not begin the next milestone.



## M05 — Freeze Phase-3 baseline

Create `docs/PHASE3_BASELINE.md` with HEAD, tests, runtimes, migration head, current deterministic benchmark, Phase-2 references and explicit statement that no Phase-3 AI is active yet. Update MEMORY to Phase 3 only after M01–M04 PASS.

### Mandatory milestone gate
For this milestone, before PASS:
1. inspect `git status`;
2. define/confirm acceptance tests;
3. implement only this milestone;
4. format/lint;
5. strict typecheck;
6. run narrow unit tests;
7. run integration/security/data/ML/frontend tests relevant to this milestone;
8. run the required Phase-1/2 regression subset;
9. inspect actual outputs/artifacts rather than assuming success;
10. update PHASE3_STATUS + MEMORY and all affected governance/research/version docs;
11. verify docs match code;
12. only then mark PASS and create one local milestone commit;
13. never push.

If any step fails, repair and rerun this same milestone. Do not begin the next milestone.



## M06 — Live AI/ML research and version manifest

Verify current TokenRouter model/API docs, both DeBERTa model cards/licenses/revisions, current PyTorch/Transformers/Datasets/Accelerate/ONNX candidates, Colab guidance and security advisories. Record authoritative sources/date/impact in RESEARCH and VERSION_MANIFEST. Do not install stale remembered versions.

### Mandatory milestone gate
For this milestone, before PASS:
1. inspect `git status`;
2. define/confirm acceptance tests;
3. implement only this milestone;
4. format/lint;
5. strict typecheck;
6. run narrow unit tests;
7. run integration/security/data/ML/frontend tests relevant to this milestone;
8. run the required Phase-1/2 regression subset;
9. inspect actual outputs/artifacts rather than assuming success;
10. update PHASE3_STATUS + MEMORY and all affected governance/research/version docs;
11. verify docs match code;
12. only then mark PASS and create one local milestone commit;
13. never push.

If any step fails, repair and rerun this same milestone. Do not begin the next milestone.



## M07 — Private TokenRouter credential injection

Ensure `PHASE3_PRIVATE_BOOTSTRAP_LOCAL_ONLY.md` is locally ignored, merge its TOKENROUTER_API_KEY/BASE_URL/PLANNER_MODEL into ignored root `.env` without printing them, preserve all Phase-1/2 values, and add blank placeholders/comments to `.env.example`. Do not delete private file until M10 successful auth probe. No secret in Git/logs.

### Mandatory milestone gate
For this milestone, before PASS:
1. inspect `git status`;
2. define/confirm acceptance tests;
3. implement only this milestone;
4. format/lint;
5. strict typecheck;
6. run narrow unit tests;
7. run integration/security/data/ML/frontend tests relevant to this milestone;
8. run the required Phase-1/2 regression subset;
9. inspect actual outputs/artifacts rather than assuming success;
10. update PHASE3_STATUS + MEMORY and all affected governance/research/version docs;
11. verify docs match code;
12. only then mark PASS and create one local milestone commit;
13. never push.

If any step fails, repair and rerun this same milestone. Do not begin the next milestone.



## M08 — Phase-3 governance transition

Mark Phase 2 complete/Phase 3 active in PHASES, extend PRD/ARCHITECTURE/SECURITY/TESTING/DECISIONS/MEMORY, create PHASE3_MILESTONES and status. Record model architecture, conservative fusion, human-gold requirement, Colab training, local-inference-first and no-Qwen-finetune decisions.

### Mandatory milestone gate
For this milestone, before PASS:
1. inspect `git status`;
2. define/confirm acceptance tests;
3. implement only this milestone;
4. format/lint;
5. strict typecheck;
6. run narrow unit tests;
7. run integration/security/data/ML/frontend tests relevant to this milestone;
8. run the required Phase-1/2 regression subset;
9. inspect actual outputs/artifacts rather than assuming success;
10. update PHASE3_STATUS + MEMORY and all affected governance/research/version docs;
11. verify docs match code;
12. only then mark PASS and create one local milestone commit;
13. never push.

If any step fails, repair and rerun this same milestone. Do not begin the next milestone.



## M09 — TokenRouter client abstraction

Implement backend-only IntentCompiler provider client with explicit timeout, structured errors, safe request correlation, dependency injection, model/base URL from typed config, no secret logs, and deterministic fixture/fake for tests. No IntentContract authority yet.

### Mandatory milestone gate
For this milestone, before PASS:
1. inspect `git status`;
2. define/confirm acceptance tests;
3. implement only this milestone;
4. format/lint;
5. strict typecheck;
6. run narrow unit tests;
7. run integration/security/data/ML/frontend tests relevant to this milestone;
8. run the required Phase-1/2 regression subset;
9. inspect actual outputs/artifacts rather than assuming success;
10. update PHASE3_STATUS + MEMORY and all affected governance/research/version docs;
11. verify docs match code;
12. only then mark PASS and create one local milestone commit;
13. never push.

If any step fails, repair and rerun this same milestone. Do not begin the next milestone.



## M10 — TokenRouter authentication and capability probe

Using the real temporary test key, probe qwen/qwen3.8-max-free Chat Completions, JSON instruction compliance, response_format/schema behavior actually supported by TokenRouter, latency, failure/rate-limit shapes. Document reality. After safe auth success, delete private bootstrap and prove it was never tracked. Acceptance: known provider contract.

### Mandatory milestone gate
For this milestone, before PASS:
1. inspect `git status`;
2. define/confirm acceptance tests;
3. implement only this milestone;
4. format/lint;
5. strict typecheck;
6. run narrow unit tests;
7. run integration/security/data/ML/frontend tests relevant to this milestone;
8. run the required Phase-1/2 regression subset;
9. inspect actual outputs/artifacts rather than assuming success;
10. update PHASE3_STATUS + MEMORY and all affected governance/research/version docs;
11. verify docs match code;
12. only then mark PASS and create one local milestone commit;
13. never push.

If any step fails, repair and rerun this same milestone. Do not begin the next milestone.



## M11 — IntentDraft schema

Design versioned Pydantic/domain `IntentDraft` separating hard constraints, semantic constraints, ambiguities and unspecified fields. Enforce integer minor-unit money, explicit currency, no invented defaults, bounded text/list sizes and schema version. Add property/negative tests.

### Mandatory milestone gate
For this milestone, before PASS:
1. inspect `git status`;
2. define/confirm acceptance tests;
3. implement only this milestone;
4. format/lint;
5. strict typecheck;
6. run narrow unit tests;
7. run integration/security/data/ML/frontend tests relevant to this milestone;
8. run the required Phase-1/2 regression subset;
9. inspect actual outputs/artifacts rather than assuming success;
10. update PHASE3_STATUS + MEMORY and all affected governance/research/version docs;
11. verify docs match code;
12. only then mark PASS and create one local milestone commit;
13. never push.

If any step fails, repair and rerun this same milestone. Do not begin the next milestone.



## M12 — Qwen compiler prompt and isolation contract

Write/version/hash the compiler system prompt. Input trusted user text only. Rules: do not invent constraints; separate hard vs semantic; surface ambiguities; normalize money; preserve negation; no merchant text. Add context-isolation tests proving untrusted product/merchant content cannot enter compiler path.

### Mandatory milestone gate
For this milestone, before PASS:
1. inspect `git status`;
2. define/confirm acceptance tests;
3. implement only this milestone;
4. format/lint;
5. strict typecheck;
6. run narrow unit tests;
7. run integration/security/data/ML/frontend tests relevant to this milestone;
8. run the required Phase-1/2 regression subset;
9. inspect actual outputs/artifacts rather than assuming success;
10. update PHASE3_STATUS + MEMORY and all affected governance/research/version docs;
11. verify docs match code;
12. only then mark PASS and create one local milestone commit;
13. never push.

If any step fails, repair and rerun this same milestone. Do not begin the next milestone.



## M13 — Strict output validation and bounded repair

Implement Qwen output → strict JSON extraction → Pydantic/domain validation → one bounded repair call → fail closed/clarify. If TokenRouter forwards strict response format, still validate locally. Test invalid JSON/types/floats/extra keys/missing currency/oversized output/malicious prose.

### Mandatory milestone gate
For this milestone, before PASS:
1. inspect `git status`;
2. define/confirm acceptance tests;
3. implement only this milestone;
4. format/lint;
5. strict typecheck;
6. run narrow unit tests;
7. run integration/security/data/ML/frontend tests relevant to this milestone;
8. run the required Phase-1/2 regression subset;
9. inspect actual outputs/artifacts rather than assuming success;
10. update PHASE3_STATUS + MEMORY and all affected governance/research/version docs;
11. verify docs match code;
12. only then mark PASS and create one local milestone commit;
13. never push.

If any step fails, repair and rerun this same milestone. Do not begin the next milestone.



## M14 — Intent compiler golden evaluation set

Create an independent deterministic/manual-truth compiler evaluation dataset with several hundred diverse intents: budgets, currencies, quantity, brand, condition, merchant restrictions, recurring/trial, negation, ambiguity, multi-constraint, underspecified cases. Expected truth must not be Qwen self-label.

### Mandatory milestone gate
For this milestone, before PASS:
1. inspect `git status`;
2. define/confirm acceptance tests;
3. implement only this milestone;
4. format/lint;
5. strict typecheck;
6. run narrow unit tests;
7. run integration/security/data/ML/frontend tests relevant to this milestone;
8. run the required Phase-1/2 regression subset;
9. inspect actual outputs/artifacts rather than assuming success;
10. update PHASE3_STATUS + MEMORY and all affected governance/research/version docs;
11. verify docs match code;
12. only then mark PASS and create one local milestone commit;
13. never push.

If any step fails, repair and rerun this same milestone. Do not begin the next milestone.



## M15 — Real Qwen compiler evaluation

Run the real compiler on the golden set. Measure schema validity, field precision/recall, numeric correctness, unsafe omission, hallucinated/over constraints, ambiguity handling, repair/failure rate and latency. Improve prompt/schema within this milestone if needed. Write `docs/PHASE3_INTENT_COMPILER_EVAL.md`.

### Mandatory milestone gate
For this milestone, before PASS:
1. inspect `git status`;
2. define/confirm acceptance tests;
3. implement only this milestone;
4. format/lint;
5. strict typecheck;
6. run narrow unit tests;
7. run integration/security/data/ML/frontend tests relevant to this milestone;
8. run the required Phase-1/2 regression subset;
9. inspect actual outputs/artifacts rather than assuming success;
10. update PHASE3_STATUS + MEMORY and all affected governance/research/version docs;
11. verify docs match code;
12. only then mark PASS and create one local milestone commit;
13. never push.

If any step fails, repair and rerun this same milestone. Do not begin the next milestone.



## M16 — Human confirmation domain flow

Add durable draft states DRAFT/NEEDS_CLARIFICATION/CONFIRMED/REJECTED. Only CONFIRMED creates or supersedes authorization generation. Test direct bypass, stale draft, edits, replay, confirmation idempotency and audit.

### Mandatory milestone gate
For this milestone, before PASS:
1. inspect `git status`;
2. define/confirm acceptance tests;
3. implement only this milestone;
4. format/lint;
5. strict typecheck;
6. run narrow unit tests;
7. run integration/security/data/ML/frontend tests relevant to this milestone;
8. run the required Phase-1/2 regression subset;
9. inspect actual outputs/artifacts rather than assuming success;
10. update PHASE3_STATUS + MEMORY and all affected governance/research/version docs;
11. verify docs match code;
12. only then mark PASS and create one local milestone commit;
13. never push.

If any step fails, repair and rerun this same milestone. Do not begin the next milestone.



## M17 — Human confirmation UI

Add natural-language authorization UI: compile → structured summary + ambiguities + unspecified fields → edit/confirm. Backend is source of truth. No model/API secret in browser. Accessible/responsive and fully tested.

### Mandatory milestone gate
For this milestone, before PASS:
1. inspect `git status`;
2. define/confirm acceptance tests;
3. implement only this milestone;
4. format/lint;
5. strict typecheck;
6. run narrow unit tests;
7. run integration/security/data/ML/frontend tests relevant to this milestone;
8. run the required Phase-1/2 regression subset;
9. inspect actual outputs/artifacts rather than assuming success;
10. update PHASE3_STATUS + MEMORY and all affected governance/research/version docs;
11. verify docs match code;
12. only then mark PASS and create one local milestone commit;
13. never push.

If any step fails, repair and rerun this same milestone. Do not begin the next milestone.



## M18 — AgentPay-IR taxonomy and dataset schema

Create agentpay-ir-v0.1 schema, three-label orientation, provenance metadata and validators. Encode semantic families and safe lookalike structure. No bulk generation before schema tests PASS.

### Mandatory milestone gate
For this milestone, before PASS:
1. inspect `git status`;
2. define/confirm acceptance tests;
3. implement only this milestone;
4. format/lint;
5. strict typecheck;
6. run narrow unit tests;
7. run integration/security/data/ML/frontend tests relevant to this milestone;
8. run the required Phase-1/2 regression subset;
9. inspect actual outputs/artifacts rather than assuming success;
10. update PHASE3_STATUS + MEMORY and all affected governance/research/version docs;
11. verify docs match code;
12. only then mark PASS and create one local milestone commit;
13. never push.

If any step fails, repair and rerun this same milestone. Do not begin the next milestone.



## M19 — Deterministic seed dataset

Generate 1.5k–3k high-confidence template-grounded entailment/neutral/contradiction examples with explicit logic, balanced families and safe lookalikes. Verify IDs/hashes/orientation and provenance.

### Mandatory milestone gate
For this milestone, before PASS:
1. inspect `git status`;
2. define/confirm acceptance tests;
3. implement only this milestone;
4. format/lint;
5. strict typecheck;
6. run narrow unit tests;
7. run integration/security/data/ML/frontend tests relevant to this milestone;
8. run the required Phase-1/2 regression subset;
9. inspect actual outputs/artifacts rather than assuming success;
10. update PHASE3_STATUS + MEMORY and all affected governance/research/version docs;
11. verify docs match code;
12. only then mark PASS and create one local milestone commit;
13. never push.

If any step fails, repair and rerun this same milestone. Do not begin the next milestone.



## M20 — Qwen dataset candidate generator

Build rate-limited, restartable Qwen candidate/paraphrase generator for hard language, ambiguity, safe lookalikes and prompt-injection-like merchant text. Treat generated labels as provisional. Persist batch provenance/model/prompt version and failures. No secret in dataset.

### Mandatory milestone gate
For this milestone, before PASS:
1. inspect `git status`;
2. define/confirm acceptance tests;
3. implement only this milestone;
4. format/lint;
5. strict typecheck;
6. run narrow unit tests;
7. run integration/security/data/ML/frontend tests relevant to this milestone;
8. run the required Phase-1/2 regression subset;
9. inspect actual outputs/artifacts rather than assuming success;
10. update PHASE3_STATUS + MEMORY and all affected governance/research/version docs;
11. verify docs match code;
12. only then mark PASS and create one local milestone commit;
13. never push.

If any step fails, repair and rerun this same milestone. Do not begin the next milestone.



## M21 — Candidate validation

Validate schema, text limits, label-consistency heuristics, malformed money, payment misinformation, duplicated IDs, secret leakage and generation artifacts. Reject bad rows with reason codes and produce quality report.

### Mandatory milestone gate
For this milestone, before PASS:
1. inspect `git status`;
2. define/confirm acceptance tests;
3. implement only this milestone;
4. format/lint;
5. strict typecheck;
6. run narrow unit tests;
7. run integration/security/data/ML/frontend tests relevant to this milestone;
8. run the required Phase-1/2 regression subset;
9. inspect actual outputs/artifacts rather than assuming success;
10. update PHASE3_STATUS + MEMORY and all affected governance/research/version docs;
11. verify docs match code;
12. only then mark PASS and create one local milestone commit;
13. never push.

If any step fails, repair and rerun this same milestone. Do not begin the next milestone.



## M22 — Deduplication and near-duplicate detection

Implement exact normalized hashes plus a justified near-duplicate method. Keep safe/unsafe paired relations intact. Produce duplicate clusters/rejection report; tests must catch intentional duplicate contamination.

### Mandatory milestone gate
For this milestone, before PASS:
1. inspect `git status`;
2. define/confirm acceptance tests;
3. implement only this milestone;
4. format/lint;
5. strict typecheck;
6. run narrow unit tests;
7. run integration/security/data/ML/frontend tests relevant to this milestone;
8. run the required Phase-1/2 regression subset;
9. inspect actual outputs/artifacts rather than assuming success;
10. update PHASE3_STATUS + MEMORY and all affected governance/research/version docs;
11. verify docs match code;
12. only then mark PASS and create one local milestone commit;
13. never push.

If any step fails, repair and rerun this same milestone. Do not begin the next milestone.



## M23 — Leakage-safe split builder

Create group-based train/validation/test splits by template/generator parent/entity/safe-lookalike family. Pair siblings cannot cross split. Write leakage tests that intentionally fail on contaminated examples.

### Mandatory milestone gate
For this milestone, before PASS:
1. inspect `git status`;
2. define/confirm acceptance tests;
3. implement only this milestone;
4. format/lint;
5. strict typecheck;
6. run narrow unit tests;
7. run integration/security/data/ML/frontend tests relevant to this milestone;
8. run the required Phase-1/2 regression subset;
9. inspect actual outputs/artifacts rather than assuming success;
10. update PHASE3_STATUS + MEMORY and all affected governance/research/version docs;
11. verify docs match code;
12. only then mark PASS and create one local milestone commit;
13. never push.

If any step fails, repair and rerun this same milestone. Do not begin the next milestone.



## M24 — Adversarial/hard dataset expansion

Add 2k–4k difficult semantic cases: euphemistic recurring fee, double negation, seller ambiguity, aliasing, disguised condition, bundle obligations, no-charge-today renewal, prompt-injection-like text and benign lookalikes. Defensive only.

### Mandatory milestone gate
For this milestone, before PASS:
1. inspect `git status`;
2. define/confirm acceptance tests;
3. implement only this milestone;
4. format/lint;
5. strict typecheck;
6. run narrow unit tests;
7. run integration/security/data/ML/frontend tests relevant to this milestone;
8. run the required Phase-1/2 regression subset;
9. inspect actual outputs/artifacts rather than assuming success;
10. update PHASE3_STATUS + MEMORY and all affected governance/research/version docs;
11. verify docs match code;
12. only then mark PASS and create one local milestone commit;
13. never push.

If any step fails, repair and rerun this same milestone. Do not begin the next milestone.



## M25 — Gold review pack generation

Select 300–500 stratified held-out examples across labels/families/difficulty. Generate CSV and optionally local HTML reviewer. Avoid unnecessarily showing proposed labels if it biases review. Write exact human instructions and STOP.

### Mandatory milestone gate
For this milestone, before PASS:
1. inspect `git status`;
2. define/confirm acceptance tests;
3. implement only this milestone;
4. format/lint;
5. strict typecheck;
6. run narrow unit tests;
7. run integration/security/data/ML/frontend tests relevant to this milestone;
8. run the required Phase-1/2 regression subset;
9. inspect actual outputs/artifacts rather than assuming success;
10. update PHASE3_STATUS + MEMORY and all affected governance/research/version docs;
11. verify docs match code;
12. only then mark PASS and create one local milestone commit;
13. never push.

If any step fails, repair and rerun this same milestone. Do not begin the next milestone.



## M26 — HUMAN GATE 1 — gold-set review

Stop. Ask human to review/correct entailment/neutral/contradiction, mark bad/ambiguous rows, save to exact path and reply `gold review complete`. On return validate completeness and compute agreement/correction statistics before proceeding.

### Mandatory milestone gate
For this milestone, before PASS:
1. inspect `git status`;
2. define/confirm acceptance tests;
3. implement only this milestone;
4. format/lint;
5. strict typecheck;
6. run narrow unit tests;
7. run integration/security/data/ML/frontend tests relevant to this milestone;
8. run the required Phase-1/2 regression subset;
9. inspect actual outputs/artifacts rather than assuming success;
10. update PHASE3_STATUS + MEMORY and all affected governance/research/version docs;
11. verify docs match code;
12. only then mark PASS and create one local milestone commit;
13. never push.

If any step fails, repair and rerun this same milestone. Do not begin the next milestone.



## M27 — Finalize AgentPay-IR v1

Freeze train/validation/test/gold splits after review. Generate dataset card, split manifest, hashes, label/source/family statistics, limitations and leakage report. Gold test becomes immutable for final evaluation.

### Mandatory milestone gate
For this milestone, before PASS:
1. inspect `git status`;
2. define/confirm acceptance tests;
3. implement only this milestone;
4. format/lint;
5. strict typecheck;
6. run narrow unit tests;
7. run integration/security/data/ML/frontend tests relevant to this milestone;
8. run the required Phase-1/2 regression subset;
9. inspect actual outputs/artifacts rather than assuming success;
10. update PHASE3_STATUS + MEMORY and all affected governance/research/version docs;
11. verify docs match code;
12. only then mark PASS and create one local milestone commit;
13. never push.

If any step fails, repair and rerun this same milestone. Do not begin the next milestone.



## M28 — DeBERTa baseline A evaluation

Integrate MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli with explicit label mapping. Evaluate frozen domain/gold data without training; measure quality/calibration/latency/resource. No payment integration.

### Mandatory milestone gate
For this milestone, before PASS:
1. inspect `git status`;
2. define/confirm acceptance tests;
3. implement only this milestone;
4. format/lint;
5. strict typecheck;
6. run narrow unit tests;
7. run integration/security/data/ML/frontend tests relevant to this milestone;
8. run the required Phase-1/2 regression subset;
9. inspect actual outputs/artifacts rather than assuming success;
10. update PHASE3_STATUS + MEMORY and all affected governance/research/version docs;
11. verify docs match code;
12. only then mark PASS and create one local milestone commit;
13. never push.

If any step fails, repair and rerun this same milestone. Do not begin the next milestone.



## M29 — DeBERTa baseline B evaluation

Integrate cross-encoder/nli-deberta-v3-base with its explicit label mapping and run the identical harness. Ensure no evaluation-code divergence.

### Mandatory milestone gate
For this milestone, before PASS:
1. inspect `git status`;
2. define/confirm acceptance tests;
3. implement only this milestone;
4. format/lint;
5. strict typecheck;
6. run narrow unit tests;
7. run integration/security/data/ML/frontend tests relevant to this milestone;
8. run the required Phase-1/2 regression subset;
9. inspect actual outputs/artifacts rather than assuming success;
10. update PHASE3_STATUS + MEMORY and all affected governance/research/version docs;
11. verify docs match code;
12. only then mark PASS and create one local milestone commit;
13. never push.

If any step fails, repair and rerun this same milestone. Do not begin the next milestone.



## M30 — Baseline model selection

Compare A/B using contradiction recall, neutral recall, safe-lookalike FPR, macro F1, calibration and resource cost. Write `docs/PHASE3_NLI_BASELINE_EVAL.md`, record selected baseline/revision in DECISIONS. Do not select by reputation.

### Mandatory milestone gate
For this milestone, before PASS:
1. inspect `git status`;
2. define/confirm acceptance tests;
3. implement only this milestone;
4. format/lint;
5. strict typecheck;
6. run narrow unit tests;
7. run integration/security/data/ML/frontend tests relevant to this milestone;
8. run the required Phase-1/2 regression subset;
9. inspect actual outputs/artifacts rather than assuming success;
10. update PHASE3_STATUS + MEMORY and all affected governance/research/version docs;
11. verify docs match code;
12. only then mark PASS and create one local milestone commit;
13. never push.

If any step fails, repair and rerun this same milestone. Do not begin the next milestone.



## M31 — Reproducible training bundle

Create training/phase3 with frozen dataset archive/hash, selected baseline ID/revision, label map, metrics, seed, training config, dependency manifest and artifact-import verifier. No notebook yet.

### Mandatory milestone gate
For this milestone, before PASS:
1. inspect `git status`;
2. define/confirm acceptance tests;
3. implement only this milestone;
4. format/lint;
5. strict typecheck;
6. run narrow unit tests;
7. run integration/security/data/ML/frontend tests relevant to this milestone;
8. run the required Phase-1/2 regression subset;
9. inspect actual outputs/artifacts rather than assuming success;
10. update PHASE3_STATUS + MEMORY and all affected governance/research/version docs;
11. verify docs match code;
12. only then mark PASS and create one local milestone commit;
13. never push.

If any step fails, repair and rerun this same milestone. Do not begin the next milestone.



## M32 — Self-contained Colab notebook

Create `notebooks/RazorGuard_NLI_Phase3_Training.ipynb`: GPU check, exact deps, dataset/hash verification, baseline/tokenizer load, bounded LR/config sweep, FP16 where supported, gradient accumulation, early stopping, best checkpoint, validation/gold evaluation, confusion/calibration outputs, env manifest, zip export. Dry-run logic on tiny local sample.

### Mandatory milestone gate
For this milestone, before PASS:
1. inspect `git status`;
2. define/confirm acceptance tests;
3. implement only this milestone;
4. format/lint;
5. strict typecheck;
6. run narrow unit tests;
7. run integration/security/data/ML/frontend tests relevant to this milestone;
8. run the required Phase-1/2 regression subset;
9. inspect actual outputs/artifacts rather than assuming success;
10. update PHASE3_STATUS + MEMORY and all affected governance/research/version docs;
11. verify docs match code;
12. only then mark PASS and create one local milestone commit;
13. never push.

If any step fails, repair and rerun this same milestone. Do not begin the next milestone.



## M33 — Colab preflight bundle

Package notebook + frozen data inputs/manifests/hashes/instructions into `artifacts/phase3_colab_training_bundle.zip`. Verify bundle integrity and that no API/payment secret is included. STOP.

### Mandatory milestone gate
For this milestone, before PASS:
1. inspect `git status`;
2. define/confirm acceptance tests;
3. implement only this milestone;
4. format/lint;
5. strict typecheck;
6. run narrow unit tests;
7. run integration/security/data/ML/frontend tests relevant to this milestone;
8. run the required Phase-1/2 regression subset;
9. inspect actual outputs/artifacts rather than assuming success;
10. update PHASE3_STATUS + MEMORY and all affected governance/research/version docs;
11. verify docs match code;
12. only then mark PASS and create one local milestone commit;
13. never push.

If any step fails, repair and rerun this same milestone. Do not begin the next milestone.



## M34 — HUMAN GATE 2 — Google Colab training

Stop and guide human: open notebook in Colab, choose GPU, upload bundle if requested, Runtime→Run all, wait for final success, download `razorguard_nli_artifact.zip`, place at `artifacts/models/incoming/razorguard_nli_artifact.zip`, reply `training artifact ready`. If OOM, offer one bounded batch/accumulation adjustment; do not default to Modal.

### Mandatory milestone gate
For this milestone, before PASS:
1. inspect `git status`;
2. define/confirm acceptance tests;
3. implement only this milestone;
4. format/lint;
5. strict typecheck;
6. run narrow unit tests;
7. run integration/security/data/ML/frontend tests relevant to this milestone;
8. run the required Phase-1/2 regression subset;
9. inspect actual outputs/artifacts rather than assuming success;
10. update PHASE3_STATUS + MEMORY and all affected governance/research/version docs;
11. verify docs match code;
12. only then mark PASS and create one local milestone commit;
13. never push.

If any step fails, repair and rerun this same milestone. Do not begin the next milestone.



## M35 — Training artifact verification

Validate archive hash, dataset hash, selected baseline, label mapping, model/tokenizer/config, metrics, environment manifest and corruption. Import locally only after full verification.

### Mandatory milestone gate
For this milestone, before PASS:
1. inspect `git status`;
2. define/confirm acceptance tests;
3. implement only this milestone;
4. format/lint;
5. strict typecheck;
6. run narrow unit tests;
7. run integration/security/data/ML/frontend tests relevant to this milestone;
8. run the required Phase-1/2 regression subset;
9. inspect actual outputs/artifacts rather than assuming success;
10. update PHASE3_STATUS + MEMORY and all affected governance/research/version docs;
11. verify docs match code;
12. only then mark PASS and create one local milestone commit;
13. never push.

If any step fails, repair and rerun this same milestone. Do not begin the next milestone.



## M36 — Fine-tuned vs baseline evaluation

Run the exact frozen harness against selected baseline and fine-tuned artifact. Produce `docs/PHASE3_NLI_FINETUNE_EVAL.md`. Keep fine-tuned model only if it materially improves security/utility without unacceptable safe false positives/calibration regression; otherwise retain baseline and document honestly.

### Mandatory milestone gate
For this milestone, before PASS:
1. inspect `git status`;
2. define/confirm acceptance tests;
3. implement only this milestone;
4. format/lint;
5. strict typecheck;
6. run narrow unit tests;
7. run integration/security/data/ML/frontend tests relevant to this milestone;
8. run the required Phase-1/2 regression subset;
9. inspect actual outputs/artifacts rather than assuming success;
10. update PHASE3_STATUS + MEMORY and all affected governance/research/version docs;
11. verify docs match code;
12. only then mark PASS and create one local milestone commit;
13. never push.

If any step fails, repair and rerun this same milestone. Do not begin the next milestone.



## M37 — Threshold calibration

Using validation only, calibrate contradiction BLOCK threshold, ambiguity/neutral CHALLENGE threshold, entailment PASS threshold and optional confidence/entropy margins. Freeze model+threshold policy manifest. Evaluate once on frozen gold test.

### Mandatory milestone gate
For this milestone, before PASS:
1. inspect `git status`;
2. define/confirm acceptance tests;
3. implement only this milestone;
4. format/lint;
5. strict typecheck;
6. run narrow unit tests;
7. run integration/security/data/ML/frontend tests relevant to this milestone;
8. run the required Phase-1/2 regression subset;
9. inspect actual outputs/artifacts rather than assuming success;
10. update PHASE3_STATUS + MEMORY and all affected governance/research/version docs;
11. verify docs match code;
12. only then mark PASS and create one local milestone commit;
13. never push.

If any step fails, repair and rerun this same milestone. Do not begin the next milestone.



## M38 — Production DeBERTa SemanticVerifier

Implement DebertaNLISemanticVerifier: lazy load, explicit device selection, batch inference, bounded inputs, provenance/model hash in result, calibrated semantic action, no DB mutation/payment capability. Model unavailable/inference error → CHALLENGE/fail-closed, never ALLOW.

### Mandatory milestone gate
For this milestone, before PASS:
1. inspect `git status`;
2. define/confirm acceptance tests;
3. implement only this milestone;
4. format/lint;
5. strict typecheck;
6. run narrow unit tests;
7. run integration/security/data/ML/frontend tests relevant to this milestone;
8. run the required Phase-1/2 regression subset;
9. inspect actual outputs/artifacts rather than assuming success;
10. update PHASE3_STATUS + MEMORY and all affected governance/research/version docs;
11. verify docs match code;
12. only then mark PASS and create one local milestone commit;
13. never push.

If any step fails, repair and rerun this same milestone. Do not begin the next milestone.



## M39 — SemanticEvidenceBuilder

Implement deterministic evidence-pair construction. Hypotheses only from confirmed authorization. Premises from current sanitized structured/untrusted-tagged evidence with provenance. Missing evidence yields neutral/challenge semantics. Test injection cannot create new hypotheses.

### Mandatory milestone gate
For this milestone, before PASS:
1. inspect `git status`;
2. define/confirm acceptance tests;
3. implement only this milestone;
4. format/lint;
5. strict typecheck;
6. run narrow unit tests;
7. run integration/security/data/ML/frontend tests relevant to this milestone;
8. run the required Phase-1/2 regression subset;
9. inspect actual outputs/artifacts rather than assuming success;
10. update PHASE3_STATUS + MEMORY and all affected governance/research/version docs;
11. verify docs match code;
12. only then mark PASS and create one local milestone commit;
13. never push.

If any step fails, repair and rerun this same milestone. Do not begin the next milestone.



## M40 — Conservative policy fusion

Implement and exhaustively test fusion matrix. Add property test proving no semantic output/probability can weaken deterministic BLOCK/CHALLENGE. This is release-blocking.

### Mandatory milestone gate
For this milestone, before PASS:
1. inspect `git status`;
2. define/confirm acceptance tests;
3. implement only this milestone;
4. format/lint;
5. strict typecheck;
6. run narrow unit tests;
7. run integration/security/data/ML/frontend tests relevant to this milestone;
8. run the required Phase-1/2 regression subset;
9. inspect actual outputs/artifacts rather than assuming success;
10. update PHASE3_STATUS + MEMORY and all affected governance/research/version docs;
11. verify docs match code;
12. only then mark PASS and create one local milestone commit;
13. never push.

If any step fails, repair and rerun this same milestone. Do not begin the next milestone.



## M41 — End-to-end semantic attack scenarios

Expand Security Lab with disguised subscription, refurbished-vs-new, seller alias/ambiguity, hidden renewal, bundle obligation, double negation, prompt injection and safe lookalikes. Show hard rule, NLI pair/probabilities, semantic action and final fused decision.

### Mandatory milestone gate
For this milestone, before PASS:
1. inspect `git status`;
2. define/confirm acceptance tests;
3. implement only this milestone;
4. format/lint;
5. strict typecheck;
6. run narrow unit tests;
7. run integration/security/data/ML/frontend tests relevant to this milestone;
8. run the required Phase-1/2 regression subset;
9. inspect actual outputs/artifacts rather than assuming success;
10. update PHASE3_STATUS + MEMORY and all affected governance/research/version docs;
11. verify docs match code;
12. only then mark PASS and create one local milestone commit;
13. never push.

If any step fails, repair and rerun this same milestone. Do not begin the next milestone.



## M42 — Prompt-injection context-isolation tests

Prove Qwen compiler never sees merchant text; merchant text cannot mutate IntentContract; hypotheses derive from confirmed user authority; semantic verifier cannot invoke tools; hard checks execute before semantic stage. Use PlanGuard/AgentVisor-inspired defensive scenarios.

### Mandatory milestone gate
For this milestone, before PASS:
1. inspect `git status`;
2. define/confirm acceptance tests;
3. implement only this milestone;
4. format/lint;
5. strict typecheck;
6. run narrow unit tests;
7. run integration/security/data/ML/frontend tests relevant to this milestone;
8. run the required Phase-1/2 regression subset;
9. inspect actual outputs/artifacts rather than assuming success;
10. update PHASE3_STATUS + MEMORY and all affected governance/research/version docs;
11. verify docs match code;
12. only then mark PASS and create one local milestone commit;
13. never push.

If any step fails, repair and rerun this same milestone. Do not begin the next milestone.



## M43 — Phase-3 UI integration

Integrate compiler confirmation + semantic explanations into Buyer/Security Lab/Audit. Show model version/hash, premise/hypothesis, probabilities, thresholds, hard decision, semantic decision, final decision. Accessible/responsive, no secret leakage.

### Mandatory milestone gate
For this milestone, before PASS:
1. inspect `git status`;
2. define/confirm acceptance tests;
3. implement only this milestone;
4. format/lint;
5. strict typecheck;
6. run narrow unit tests;
7. run integration/security/data/ML/frontend tests relevant to this milestone;
8. run the required Phase-1/2 regression subset;
9. inspect actual outputs/artifacts rather than assuming success;
10. update PHASE3_STATUS + MEMORY and all affected governance/research/version docs;
11. verify docs match code;
12. only then mark PASS and create one local milestone commit;
13. never push.

If any step fails, repair and rerun this same milestone. Do not begin the next milestone.



## M44 — AI audit evidence

Add append-oriented events such as INTENT_COMPILED, INTENT_CONFIRMED, SEMANTIC_VERIFICATION_RUN, POLICY_FUSION_DECIDED. Store model/prompt/schema/threshold versions and hashes, not API secrets or excessive sensitive text. Preserve tamper-evident chain.

### Mandatory milestone gate
For this milestone, before PASS:
1. inspect `git status`;
2. define/confirm acceptance tests;
3. implement only this milestone;
4. format/lint;
5. strict typecheck;
6. run narrow unit tests;
7. run integration/security/data/ML/frontend tests relevant to this milestone;
8. run the required Phase-1/2 regression subset;
9. inspect actual outputs/artifacts rather than assuming success;
10. update PHASE3_STATUS + MEMORY and all affected governance/research/version docs;
11. verify docs match code;
12. only then mark PASS and create one local milestone commit;
13. never push.

If any step fails, repair and rerun this same milestone. Do not begin the next milestone.



## M45 — End-to-end Phase-3 benchmark

Combine deterministic and semantic held-out cases. Measure unsafe execution, safe completion, challenge rate, false block, contradiction recall, semantic family metrics, compiler correction/omission metrics, and latency. Ensure no train/test contamination.

### Mandatory milestone gate
For this milestone, before PASS:
1. inspect `git status`;
2. define/confirm acceptance tests;
3. implement only this milestone;
4. format/lint;
5. strict typecheck;
6. run narrow unit tests;
7. run integration/security/data/ML/frontend tests relevant to this milestone;
8. run the required Phase-1/2 regression subset;
9. inspect actual outputs/artifacts rather than assuming success;
10. update PHASE3_STATUS + MEMORY and all affected governance/research/version docs;
11. verify docs match code;
12. only then mark PASS and create one local milestone commit;
13. never push.

If any step fails, repair and rerun this same milestone. Do not begin the next milestone.



## M46 — Ablation study

Run A deterministic only, B NLI-only evaluation-only, C deterministic+zero-shot NLI, D deterministic+fine-tuned NLI if selected, E full Qwen+human-confirmation+deterministic+selected NLI. Produce `docs/PHASE3_ABLATION_REPORT.md`. NLI-only never production authority.

### Mandatory milestone gate
For this milestone, before PASS:
1. inspect `git status`;
2. define/confirm acceptance tests;
3. implement only this milestone;
4. format/lint;
5. strict typecheck;
6. run narrow unit tests;
7. run integration/security/data/ML/frontend tests relevant to this milestone;
8. run the required Phase-1/2 regression subset;
9. inspect actual outputs/artifacts rather than assuming success;
10. update PHASE3_STATUS + MEMORY and all affected governance/research/version docs;
11. verify docs match code;
12. only then mark PASS and create one local milestone commit;
13. never push.

If any step fails, repair and rerun this same milestone. Do not begin the next milestone.



## M47 — Local inference optimization / Modal decision

Benchmark CPU, MPS if stable, ONNX and optional quantized ONNX only if justified. Record cold/warm p50/p95, memory, quality drift. If local is acceptable, no Modal. If not, STOP at conditional compute human gate before introducing cloud cost/credentials.

### Mandatory milestone gate
For this milestone, before PASS:
1. inspect `git status`;
2. define/confirm acceptance tests;
3. implement only this milestone;
4. format/lint;
5. strict typecheck;
6. run narrow unit tests;
7. run integration/security/data/ML/frontend tests relevant to this milestone;
8. run the required Phase-1/2 regression subset;
9. inspect actual outputs/artifacts rather than assuming success;
10. update PHASE3_STATUS + MEMORY and all affected governance/research/version docs;
11. verify docs match code;
12. only then mark PASS and create one local milestone commit;
13. never push.

If any step fails, repair and rerun this same milestone. Do not begin the next milestone.



## M48 — Full Phase-3 security/quality gate

Run complete backend/frontend/payment/AI/data gates: Ruff, strict mypy, full pytest/Hypothesis/concurrency, Phase-2 payment regressions, lint/type/build/Vitest/Playwright/a11y, dataset schema/leakage/hash checks, model artifact/hash, compiler eval, threshold/fusion invariants, dependency audits, secret scans, no TokenRouter key in frontend/build/docs, private bootstrap deleted. Any critical issue blocks.

### Mandatory milestone gate
For this milestone, before PASS:
1. inspect `git status`;
2. define/confirm acceptance tests;
3. implement only this milestone;
4. format/lint;
5. strict typecheck;
6. run narrow unit tests;
7. run integration/security/data/ML/frontend tests relevant to this milestone;
8. run the required Phase-1/2 regression subset;
9. inspect actual outputs/artifacts rather than assuming success;
10. update PHASE3_STATUS + MEMORY and all affected governance/research/version docs;
11. verify docs match code;
12. only then mark PASS and create one local milestone commit;
13. never push.

If any step fails, repair and rerun this same milestone. Do not begin the next milestone.



## M49 — Clean-room Phase-3 acceptance

From disposable local state prove setup/migrations/seed/model import/backend/frontend/mock provider/safe Razorpay validation/TokenRouter compiler/human-confirmation flow/SemanticVerifier/fusion/Security Lab/benchmark/audit. Avoid unnecessary real checkout. Document reproduction.

### Mandatory milestone gate
For this milestone, before PASS:
1. inspect `git status`;
2. define/confirm acceptance tests;
3. implement only this milestone;
4. format/lint;
5. strict typecheck;
6. run narrow unit tests;
7. run integration/security/data/ML/frontend tests relevant to this milestone;
8. run the required Phase-1/2 regression subset;
9. inspect actual outputs/artifacts rather than assuming success;
10. update PHASE3_STATUS + MEMORY and all affected governance/research/version docs;
11. verify docs match code;
12. only then mark PASS and create one local milestone commit;
13. never push.

If any step fails, repair and rerun this same milestone. Do not begin the next milestone.



## M50 — Phase-3 completion report and STOP

Create `docs/PHASE3_COMPLETION_REPORT.md` covering baseline revalidation, TokenRouter/Qwen compiler, AgentPay-IR, human gold review, baseline comparison, training, final model decision, thresholds, fusion, context isolation, benchmark/ablation/performance/security, limitations and human gates. Update governance, mark Phase 3 complete and Phase 4 awaiting human approval. Do not start Phase 4.

### Mandatory milestone gate
For this milestone, before PASS:
1. inspect `git status`;
2. define/confirm acceptance tests;
3. implement only this milestone;
4. format/lint;
5. strict typecheck;
6. run narrow unit tests;
7. run integration/security/data/ML/frontend tests relevant to this milestone;
8. run the required Phase-1/2 regression subset;
9. inspect actual outputs/artifacts rather than assuming success;
10. update PHASE3_STATUS + MEMORY and all affected governance/research/version docs;
11. verify docs match code;
12. only then mark PASS and create one local milestone commit;
13. never push.

If any step fails, repair and rerun this same milestone. Do not begin the next milestone.


# 20. PHASE-3 END-TO-END FLOW

```text
HUMAN
  ↓
natural-language authorization
  ↓
QWEN 3.8 MAX FREE / TOKENROUTER
  ↓
IntentDraft
  ↓
strict validation
  ↓
HUMAN CONFIRMATION
  ↓
IntentContract generation
  ↓
checkout/current evidence
  ↓
deterministic hard RazorGuard
  ↓
SemanticEvidenceBuilder
  ↓
selected DeBERTa NLI model
  ↓
calibrated semantic PASS/CHALLENGE/BLOCK
  ↓
conservative fusion
  ↓
ALLOW / CHALLENGE / BLOCK
  ↓ if ALLOW
existing Phase-2 reservation
  ↓
execution ticket
  ↓
ExecutionAttempt
  ↓
Razorpay Test Mode
  ↓
verified callback/webhooks/reconciliation
  ↓
audit evidence
```

AI stops before privileged payment execution.

---

# 21. REQUIRED UX EXPLANATION

Human confirmation must show exactly what Qwen inferred and what was unspecified.

Semantic verification should show, where appropriate:

```text
Human constraint:
"The product must be new."

Current evidence:
"Condition: Certified Refurbished"

RazorGuard-NLI:
Contradiction 0.xx
Neutral       0.xx
Entailment    0.xx

Semantic action:
BLOCK or CHALLENGE

Hard rules:
PASS

Final:
BLOCK or CHALLENGE
```

For ambiguity, challenge rather than invent certainty.

---

# 22. FAILURE POLICY

TokenRouter unavailable:
- do not silently switch provider;
- do not construct partial authority;
- offer deterministic/manual structured input if product flow supports it;
- show controlled unavailable state.

Invalid Qwen schema:
- one bounded repair;
- then fail closed / ask user to rephrase.

Semantic model unavailable:
- CHALLENGE/fail-closed;
- never silent ALLOW.

Missing evidence:
- neutral/unknown;
- challenge where policy requires evidence.

Colab OOM:
- one bounded batch/gradient-accumulation adjustment;
- regenerate notebook if required;
- only then consider conditional compute gate.

---

# 23. PHASE-4 PREPARATION ONLY

At M50 document, but do not implement:

```text
external AI agent
  ↓
MCP / UCP / AP2 / ACP adapter
  ↓
canonical commerce request
  ↓
Phase-3 trust layer
  ↓
Phase-2 trusted Razorpay execution
```

Do not claim protocol compliance.

---

# 24. FINAL ACCEPTANCE MATRIX

All must be true:

- Phase-1 backend regression PASS
- Phase-2 backend regression PASS
- Phase-2 frontend/E2E regression PASS
- Razorpay structural security intact
- TokenRouter secret backend-only
- TokenRouter/Qwen auth and capability probe PASS
- Intent compiler strict validation PASS
- Intent compiler evaluation complete
- Human confirmation required/proven
- AgentPay-IR frozen
- split leakage checks PASS
- human-reviewed gold set complete
- DeBERTa baseline A evaluated
- DeBERTa baseline B evaluated
- baseline selected by evidence
- Colab notebook reproducible
- training artifact verified
- fine-tune-vs-baseline decision evidence complete
- thresholds calibrated without test leakage
- production SemanticVerifier PASS
- SemanticEvidenceBuilder PASS
- hard policy cannot be weakened
- context-isolation attack tests PASS
- semantic Security Lab PASS
- end-to-end benchmark complete
- ablation study complete
- no secret in frontend/build/docs
- clean-room acceptance PASS
- Phase 4 not implemented

If any required item fails, Phase 3 is incomplete.

---

# 25. INITIAL RESPONSE AND START

When this prompt is received:
- do not repeat all 50 milestones;
- state that Phase 3 is understood;
- state that you will first revalidate Phase 1/2;
- state that secrets will never be printed;
- state that the local private bootstrap will be handled safely;
- state that you will execute exactly one milestone at a time;
- state that you will stop only at the defined human gates;
- begin M01 immediately.

Allowed final wording only after M50:

> **Phase-3 AI/ML trust layer complete.**

Then STOP and request explicit human approval before Phase 4.
