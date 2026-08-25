# PHASE3_MILESTONES.md — Phase-3 Gated Plan (AI/ML Trust Layer)

## Rule

Exactly one milestone active at a time. Every milestone follows the mandatory
gate in the Phase-3 master prompt (§16/§19) and updates `PHASE3_STATUS.md` +
`MEMORY.md` before the next. Local commit only after PASS. Never push.
Human gates: M26 (gold review), M34 (Colab training), conditional compute gate
(only if genuinely required), Phase-4 approval after M50.

Source: human-approved `RazorMesh_Trust_Phase3_Master_Prompt.md` (2026-08-25).

| # | Milestone | Summary |
|---|---|---|
| M01 | Repository/governance/secret-safety inspection | Git+governance read; bootstrap excluded pre-read; baseline 375 green |
| M02 | Full Phase-1/2 backend regression | Ruff/mypy strict/pytest/Hypothesis/concurrency/security batteries |
| M03 | Full Phase-1/2 frontend/E2E regression | lint/tsc/vitest/build/Playwright + secret scans |
| M04 | Phase-2 real-provider integrity revalidation | Guard/live-rejection/webhook/dedup/reservation/audit + read-only diagnostic |
| M05 | Freeze Phase-3 baseline | docs/PHASE3_BASELINE.md; no AI active yet |
| M06 | Live AI/ML research + version manifest | TokenRouter/DeBERTa/ML stack live-verified → RESEARCH/VERSION_MANIFEST |
| M07 | Private credential injection | Merge TOKENROUTER_* into .env w/o exposure; placeholders; deletion deferred to post-M10 |
| M08 | Governance transition | PHASES/PRD/SECURITY/TESTING/DECISIONS D-038..D-040; milestones file |
| M09 | TokenRouter client abstraction | Backend-only client, timeout, typed errors, DI, fixtures; no authority |
| M10 | Auth + capability probe | Real probe: model id, JSON compliance, response_format, latency; then DELETE private file + prove never tracked |
| M11 | IntentDraft schema | Versioned Pydantic domain schema; money/currency/no-invention/bounds; property tests |
| M12 | Compiler prompt & isolation contract | Versioned+hashed system prompt; isolation tests |
| M13 | Strict validation + bounded repair | JSON extract→validate→one repair→fail closed; adversarial outputs |
| M14 | Compiler golden eval set | Several hundred manual-truth intents; not Qwen self-labeled |
| M15 | Real compiler evaluation | Metrics + docs/PHASE3_INTENT_COMPILER_EVAL.md |
| M16 | Human confirmation flow | DRAFT/NEEDS_CLARIFICATION/CONFIRMED/REJECTED durable states + tests |
| M17 | Human confirmation UI | NL authorization UI; no secrets in browser |
| M18 | AgentPay-IR taxonomy/schema | agentpay-ir-v0.1 validators; provenance metadata |
| M19 | Deterministic seed dataset | 1.5k–3k template-grounded examples |
| M20 | Qwen candidate generator | Rate-limited restartable; labels provisional; provenance persisted |
| M21 | Candidate validation | Schema/label-consistency/rejection reasons/quality report |
| M22 | Dedup + near-duplicate detection | Exact hashes + justified method; contamination tests |
| M23 | Leakage-safe split builder | Group splits; leakage tests fail on contaminated fixtures |
| M24 | Adversarial/hard expansion | 2k–4k hard semantic cases, defensive only |
| M25 | Gold review pack generation | 300–500 stratified CSV(+HTML); exact instructions; STOP |
| M26 | HUMAN GATE 1 — gold review | Human reviews/saves; validate completeness + agreement stats |
| M27 | Finalize AgentPay-IR v1 | Frozen splits/manifest/hashes/card/leakage report |
| M28 | DeBERTa baseline A eval | MoritzLaurer zero-shot on frozen harness |
| M29 | DeBERTa baseline B eval | cross-encoder identical harness |
| M30 | Baseline selection | Security-first criteria; docs/PHASE3_NLI_BASELINE_EVAL.md; DECISIONS |
| M31 | Reproducible training bundle | training/phase3 frozen inputs+manifests+import verifier |
| M32 | Self-contained Colab notebook | notebooks/RazorGuard_NLI_Phase3_Training.ipynb; local dry-run logic |
| M33 | Colab preflight bundle | artifacts/phase3_colab_training_bundle.zip verified; STOP |
| M34 | HUMAN GATE 2 — Colab training | Human runs notebook; artifact placed at artifacts/models/incoming/ |
| M35 | Training artifact verification | Hash/manifest/corruption checks before import |
| M36 | Fine-tuned vs baseline evaluation | docs/PHASE3_NLI_FINETUNE_EVAL.md; keep only if materially better |
| M37 | Threshold calibration | Validation-only calibration; frozen policy manifest; one gold eval |
| M38 | Production SemanticVerifier | DebertaNLISemanticVerifier; lazy load; fail-closed CHALLENGE |
| M39 | SemanticEvidenceBuilder | Deterministic pairs; injection cannot create hypotheses |
| M40 | Conservative policy fusion | Matrix + property test; release-blocking |
| M41 | End-to-end semantic attack scenarios | Security Lab expansion w/ evidence trail |
| M42 | Prompt-injection context-isolation tests | PlanGuard/AgentVisor-inspired defenses proven |
| M43 | Phase-3 UI integration | Model version/hash, probabilities, thresholds, fused decision shown |
| M44 | AI audit evidence events | INTENT_COMPILED/CONFIRMED, SEMANTIC_VERIFICATION_RUN, POLICY_FUSION_DECIDED |
| M45 | End-to-end Phase-3 benchmark | Deterministic+semantic held-out; contamination-free |
| M46 | Ablation study A–E | docs/PHASE3_ABLATION_REPORT.md; NLI-only never authority |
| M47 | Local inference optimization / Modal decision | CPU/MPS/ONNX benchmarks; STOP at gate only if inadequate |
| M48 | Full Phase-3 security/quality gate | Everything incl. dataset/model/secret gates |
| M49 | Clean-room Phase-3 acceptance | Disposable-state full-flow proof |
| M50 | Completion report & STOP | docs/PHASE3_COMPLETION_REPORT.md; Phase-4 awaiting approval |
