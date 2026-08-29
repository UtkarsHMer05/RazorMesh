# AgentPay-IR v2 — TRANSFORMATION_REPORT (G073) + MORNING_HANDOFF

**Generated:** 2026-08-29 · Mode: `OVERNIGHT_AUTONOMOUS_PREP` · Builder: `scripts/rzp_build_agentpay_ir_v2_corpus.py` (seed 42) · Freezer: `scripts/rzp_freeze_agentpay_ir_v2.py`

> **SUPERSEDED IN PART (2026-08-29, PRE-REVIEW FINAL CORRECTION).** §1–§2 remain
> the accurate corpus/leakage provenance record. The review-pack, OOD, bundle and
> handoff facts below were corrected afterward — the SINGLE current handoff is
> `docs/agentpay_ir_v2/STATUS.md`. Current facts: review pack **V3**
> (`REVIEW_PACK_V3.jsonl`, 635 cards, `rc2_*` ids, 301 gold / 334 supervised,
> group-level roles, sha256 `c88b7817…`); fresh OOD expanded + refrozen to
> **665 rows** (sha256 `8948a8e3…`); PRE-REVIEW bundle sha256 `6292deb6…`
> (byte-deterministic build); the notebook pins `EXPECTED_BUNDLE_SHA256`
> externally and installs from `requirements-frozen.txt`. The V3 pack spans 21
> OBSERVED strata (not 25); the `currency`/`delivery_constraint` families are
> intentionally held out into the untouched OOD rather than human-review/training.
> The 700-card V2 pack,
> the 400/401-row OOD figures, and the older bundle hashes in the sections below
> are historical.

## 1. Corpus

| split | rows | contradiction | entailment | neutral | families | split_groups |
|---|---:|---:|---:|---:|---:|---:|
| train | 13,843 | 3,609 | 6,817 | 3,417 | 34 | 6,819 |
| val | 2,312 | 613 | 1,120 | 579 | 28 | 1,116 |
| test | 2,261 | 567 | 1,149 | 545 | 26 | 1,150 |

- **Composition (train, honest):** real_human_nli 6,254 (ContractNLI, CC BY 4.0) + real_commerce 6,936 (ESCI, Apache-2.0) = **95.3% real/human-derived**; deterministic_derived 653 (RazorMesh provenance-normalized internal security/domain seed) = **4.7% targeted deterministic internal**; synthetic_adversarial 0% (cap ≤10%). **CORRECTED 2026-08-29 (PVB correction #15): the earlier "100% real/human-derived" claim was wrong** — deterministic-derived internal rows are not real/human data.

> **STATUS (PVB correction #16): the corpus splits and the current Colab bundle are PRE-REVIEW artifacts.** The final AgentPay-IR v2 freeze happens only after human review via `scripts/rzp_finalize_review_v2.py` (supervised labels integrated, gold kept out, leakage re-run, final hashes frozen, final bundle rebuilt).
- **Deterministic label rules (G070):** ContractNLI official span/choice labels (Entailment/Contradiction direct; NotMentioned→neutral via cross-clause evidence, ≤6/doc). ESCI: explicit attribute semantics only (brand token vs. listed brand; listed color vs. requested; condition tokens in title; model-token identity). E/S/C/I relevance labels were NEVER auto-mapped to NLI. All ambiguous ESCI rows → review pack (700 candidates).
- **Orientation:** canonical everywhere, machine-enforced; every record's `content_sha256` covers orientation. 1 frozen_v2 seed row excluded (premise carried "the authorized model" — untrusted-authority leak; recorded).

## 2. Leakage gate (release-blocking): **PASS**

- Zero shared `split_group` across train/val/test (grouping unit: ContractNLI=document, ESCI=product, internal=generator parent).
- Zero identical/normalized (premise,hypothesis) pairs across splits (global pre-split dedup removed 1,626 exact + 57 normalized duplicates).
- Fresh OOD v2 (400 rows) shares zero hashes and zero groups with any split; withheld families (`currency`, `delivery_constraint`) + withheld ContractNLI entities (hash-bucketed) never entered the corpus.

## 3. Review pack + OOD freeze

- `review_candidates.jsonl`: 700 frozen candidates (ambiguous real ESCI rows). Hidden `review_role` manifest frozen (seed 42): **300 gold / 400 supervised** — assigned BEFORE any human label; roles hidden by the review UI until after independent choice. Gold rows can never enter training/validation/selection/calibration.
- `eval/fresh_ood_v2.jsonl`: 400 rows, hash-frozen in `eval/fresh_ood_v2_FROZEN.json`; never used for training/validation/selection/calibration. The historical 129-row OOD remains a comparator only.

## 4. Training handoff (Colab)

- Base model: `cross-encoder/nli-deberta-v3-base` **pinned @ revision `6c749ce3425cd33b46d187e45b92bbf96ee12ec7`** (docs/agentpay_ir_v2/MODEL_SOURCE_MANIFEST.json).
- Bundle: `artifacts/agentpay_ir_v2_colab_training_bundle.zip` — **PRE-REVIEW bundle**, current sha256 `ff5d0c9f9f41f7949d7eb9e7dccf915dd10828bcdbddd73337349dc797ba1dfb` (record this value OUTSIDE the archive; the notebook prints the archive sha for comparison and verifies the per-file manifest, which is non-self-referential). Contains train+val+schema+label map+config+hashes ONLY; **excludes frozen test, human-gold roles, untouched OOD** (physical separation). Colab pins now MATCH the API semantic runtime (transformers 5.15.1 / torch 2.13.0 / accelerate 1.14.0) so the artifact round-trips with identical serialization semantics.
- Notebook: `notebooks/RazorGuard_NLI_AgentPayIR_v2_Training.ipynb` — asserts GPU, verifies the per-file manifest + prints the archive sha (externally compared), downloads the exact pinned revision, seeds (42), trains candidates A (2 epochs) and B (3 epochs), **selects on validation only with the FROZEN safety rule: minimize unsafe C→E, then maximize macro-F1, then maximize contradiction recall** (neutral recall + safe false-block reported per candidate), and packages `agentpay-ir-v2-finetuned.zip` including a full `model_manifest.json` (training config, dataset manifest hash, base revision, dependency versions, candidate results, selected candidate, seed, per-file artifact hashes).
- Local smoke proof: `scripts/rzp_smoke_train_v2.py` — 64 rows, 1 epoch, CPU; result recorded in `OVERNIGHT_VERIFICATION_LEDGER.md` (training code path executes end-to-end).

## 5. Runtime activation (after training)

`SEMANTIC_VERIFIER_BACKEND=deberta_v2` is scaffolded behind `MODEL_DIR_V2 = artifacts/models/incoming/agentpay-ir-v2-finetuned/` — INACTIVE while the artifact is absent (missing artifact fails CLOSED to CHALLENGE; never a keyword substitution; pinned by tests). After the human places the returned zip and its manifest hash is verified, activation is a settings change plus a recorded hash check.

---

# OVERNIGHT_AUTONOMOUS_PREP_COMPLETE / AWAITING_HUMAN_REVIEW_AND_COLAB
> **SUPERSEDED (2026-08-29): the current workflow lives in STATUS.md** (V3 pack at
> http://localhost:3000/reviewer, 635 cards; export → rzp_finalize_review_v2.py →
> final bundle → Colab). Kept verbatim as history:

1. Open the review pack: `data/agentpay_ir_v2/corpus/review_candidates.jsonl` (700 cards; reviewer UI task for the morning — the role manifest must stay hidden).
2. Review the frozen cards (contradiction / entailment / neutral / ambiguous).
3. Tell agent: "review complete".
4. Agent ingests decisions, freezes supervised/gold roles, rebuilds the final training-only bundle.
5. Upload `artifacts/agentpay_ir_v2_colab_training_bundle.zip` to `notebooks/RazorGuard_NLI_AgentPayIR_v2_Training.ipynb` in Colab (T4/L4).
6. Run the notebook top-to-bottom.
7. Download `agentpay-ir-v2-finetuned.zip`.
8. Place it in `artifacts/models/incoming/`.
9. Tell agent: "v2 artifact uploaded" → the agent resumes `POST_COLAB_RESUME` (candidate comparison, validation-only calibration, one-shot test/gold/OOD evaluation, runtime wiring, full Phase-1→4 regression, final same-lineage Razorpay Test payment).
