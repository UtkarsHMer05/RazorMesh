# Phase-3 Intent Compiler Evaluation (P3-M15)

## Current evidence — payload-backed v2 run

The owner completed a new, separate 307-case run in
`data/phase3/compiler_eval/v2/`. This audit performed **offline inspection and
summary regeneration only**, with no new provider calls or changes to raw
results, golden truth, or the compiler prompt. Measurement coverage is complete;
this report does not declare a perfect compiler or full Phase-3 acceptance.

All 307 unique case IDs match the frozen golden set. Every row's provenance
matches `run_manifest.json` (model `qwen/qwen3.8-max-free`, compiler prompt v2,
evaluator v2, schema v1, temperature 0, output budget 4000). Raw results SHA-256:
`a9800259c7aa397db547d358d55356a74dc9c2f0435a4aa789cd93b68297e9ab`.
The golden SHA remains `9164f04c8714d711cae1a9ecba0db35853947bfec0683af9428bd4f6c86c79b7`.

| Measure | v2 result |
|---|---:|
| Coverage | 307/307 unique final cases |
| Valid payloads | 304/307 (99.02%) |
| Whole-output failures | 3/307, all SCHEMA_INVALID_AFTER_REPAIR |
| Cases needing bounded repair | **27/307 (8.79%)** |
| Repair outcomes | 24 valid; 3 failed; success 24/27 (88.89%) |
| Exact golden-case matches | 242/307 (78.83%) |
| Amount substitutions in valid outputs | 35, all exactly one minor unit lower |
| Amount / currency omissions in valid outputs | 14 / 14 |
| Currency / quantity substitutions | 0 / 0 |
| Detected invented-constraint cases | 22/307 (7.17%) |
| Ambiguity-count probes satisfied | 6/6 |
| Valid-output latency p50 / p95 / max / mean | 20.7s / 64.8s / 141.4s / 26.8s |

The original v2 summary counted only the 24 successful repairs and divided by
304 valid outcomes. That excluded the three failed repairs. The corrected
repair rate counts every repaired case over all 307 evaluated cases.
The preserved run has no COMPILER_UNAVAILABLE outcomes; this is a statement
about these 307 recorded service outcomes, not general provider reliability.

### Bound interpretation is not silently changed

All 35 amount substitutions occur with “under”, “below”, or “less than” wording.
The frozen golden values equal the named amounts; the model instead emitted
one minor unit less. For example, F1-009 says “below ₹1,499”: expected 149900,
actual 149899. This is an observable strict-versus-inclusive interpretation
difference, not a missing amount and not an increased budget. **All 35 remain
exact-match failures against unchanged truth.** No claim that either wording
interpretation has been human-approved is made. Any requirement clarification
and new truth/prompt version must be explicit and preserve this run.

### Field denominators and whole-output failures

Precision counts correct/present annotated fields; recall below uses **all
cases**, so a complete output failure reduces recall without being mislabeled
as an omission in a valid payload.

| Field | Correct / expected | Present | Precision | All-case recall |
|---|---:|---:|---:|---:|
| Amount | 236/288 | 271 | 0.8708 | 0.8194 |
| Currency | 271/288 | 271 | 1.0 | 0.9410 |
| Quantity | 33/36 | 33 | 1.0 | 0.9167 |
| Brand members | 52/54 | 53 | 0.9811 | 0.9630 |
| Merchant members | 13/13 | 13 | 1.0 | 1.0 |
| Recurring-forbidden expectations | 21/25 | 21 | 1.0 | 0.8400 |
| Semantic substring probes | 50/53 | unknown | unknown | 0.9434 |
| Unspecified-field probes | 0/0 | unknown | unknown | n/a |

Whole-output failures are F10-002, F10-004, and F3-018. Their missing output
accounts for three amount/currency/quantity expectations, two brand members,
two recurring expectations, and two semantic probes. Among **valid outputs**,
there are additionally two recurring omissions and one missing semantic probe;
the 14 amount omissions also omit currency. Invented constraints detected:
20 condition, one warranty, and one extra brand. Error categories overlap.

The machine-readable summary separately reports `valid_output_omissions`,
`whole_output_failures`, `valid_output_field_metrics`, and direction/case-level
`scalar_mismatch_details`. Amount recall conditional on a valid output is
236/285 (0.8281), not the all-case 236/288 (0.8194).

Semantic truth remains partial substring probes: exhaustive semantic precision
and over-constraint rates remain unknown. The 22 detected inventions are a
lower-bound over-constraint signal. Ambiguity presence is not proof of question
quality or later human-confirmation behavior. Hard-rule/NLI enforcement cannot
independently reconstruct dropped or invented human constraints.

Offline reproduction of **v2 only**:

```bash
services/api/.venv/bin/python scripts/rzp_summarize_compiler_eval.py --results data/phase3/compiler_eval/v2/results.jsonl --output data/phase3/compiler_eval/v2/summary.json
services/api/.venv/bin/pytest services/api/tests/test_compiler_eval.py
```

The historical v1 evidence below is preserved, not blended into v2 metrics.
Its unknown numeric precision cannot be retroactively recovered using new
outputs. Milestone acceptance is coordinated separately from this measurement.

---

## Historical v1 evidence and prior correction (preserved)

Status: **307-case measurement coverage complete; metric-evidence gate OPEN.**
Audit correction: 2026-08-27. No new provider calls, golden changes, or raw
result changes were made for this correction. This is not an offline rescore.

## Evidence and scope

The real `IntentCompilationService` / TokenRouter compiler ran against
`qwen/qwen3.8-max-free`, prompt `razormesh-intent-compiler-v2`, temperature 0,
output-token budget 4000. Golden SHA-256:
`9164f04c8714d711cae1a9ecba0db35853947bfec0683af9428bd4f6c86c79b7`.
The golden set contains 307 template-authored cases across 25 categories;
it is not Qwen self-labeling or evidence of independent human review.

D-041 permitted an initial stratified 90-case sample. D-051 records completion
of all 307 cases. The preserved `data/phase3/compiler_eval/results.jsonl`
contains 307 verdict-only rows, **not the validated compiler payloads**.
The runner calls the compilation service directly; it does not persist drafts
through the durable confirmation flow. No compiler-response archive was found
among the compiler evaluation artifacts. Request IDs alone cannot recover text.

The original evaluator classified any unequal amount, currency, or quantity
as an `omission`, including wrong-but-present substitutions. Consequently,
the old **zero numeric mismatches**, **money precision 1.0**, and **all amount
errors fail closed because they are missing** claims are withdrawn. Exact
omission versus substitution counts are **unknown** without original payloads
or a separately authorized new measurement run. The v2 evaluator now separates
these outcomes; future runner rows retain evaluator version and validated
synthetic payload for offline verification. Existing rows remain unchanged.
New runs default to `data/phase3/compiler_eval/v2/`, retain every service-call
outcome without compaction, and require matching prompt/model/schema/golden
provenance to resume. The historical output directory is explicitly refused.

## Recoverable full-set results (N=307)

| Measure | Result |
|---|---:|
| Final case coverage | 307/307 |
| Legacy schema-valid outcomes | 307/307 |
| Cases needing bounded repair | 11/307 (3.58%); 11 became valid |
| Legacy case verdict pass | 239/307 (77.85%) |
| Easy / medium / hard pass | 177/234; 40/43; 22/30 |
| Amount absent **or unequal** | 51/307 (16.61%) |
| Currency absent **or unequal** | 14/307 (4.56%) |
| Exact numeric omission / substitution split | unknown |
| Numeric extraction precision | unknown |
| Detected invented-constraint cases | 24/307 (7.82%) |
| Ambiguity-count probes satisfied | 6/6 |
| Latency p50 / p95 / max / mean | 29.4s / 122.7s / 241.2s / 42.2s |

“Ambiguity satisfied” means the payload had at least the required number of
ambiguity entries. The recorded status was OK, not NEEDS_CLARIFICATION; these
rows do not establish ambiguity quality or the later UI state transition.
Provider failure rate over **all attempts** is unknown: the resumable runner
kept the last row per case and compacted history. Zero excluded noise rows in
the final file is not proof that the provider never failed.

## Field precision and recall

Denominators count normalized entity members, scalar expectations, or explicit
semantic substring probes as indicated. Recall is expected-value match, not
proof of absence/presence classification. No payload-present denominator is
invented where the historical records do not preserve it.

| Field | Correct / expected | Present denominator | Precision | Recall |
|---|---:|---:|---:|---:|
| Amount | 237/288 | unknown | unknown | 0.8229 |
| Currency | 274/288 | unknown | unknown | 0.9514 |
| Quantity | 36/36 | unknown | unknown | 1.0 |
| Brand members | 54/54 | 55 | 0.9818 | 1.0 |
| Merchant members | 13/13 | 13 | 1.0 | 1.0 |
| Recurring-forbidden expectations | 24/25 | unknown | unknown | 0.96 |
| Semantic substring probes | 52/53 | unknown | unknown | 0.9811 |
| Unspecified-field probes | 0/0 | unknown | unknown | n/a |

Brand and merchant set differences preserve individual missing/extra values,
allowing their present denominators to be reconstructed. Semantic truth is
partial substring inclusion/exclusion, not an exhaustive constraint inventory;
therefore full semantic precision and total over-constraint rate are unknown.
The 24 detected invention cases are a measured lower-bound over-constraint
signal, not exhaustive coverage of every possible invented constraint.

## Full-set failure taxonomy (68 failed legacy verdicts)

Categories overlap; do not sum them as distinct cases.

- 51 amount absent-or-unequal classifications; 14 currency absent-or-unequal
  classifications. The prior 11-case amount taxonomy described only the sample.
- 22 detected condition inventions, one warranty invention, one extra brand:
  24 distinct cases. Prior six-condition and 6.7% figures were sample-only.
- One missing semantic `apple` probe (F22-001), paired with extra brand
  `iphone`; one recurring-forbidden miss (F9-002, “I refuse trials of any kind”).
- F13-000 extracted a warranty constraint from injection-like human text.
  This is a compiler interpretation defect. Downstream NLI compares confirmed
  constraints with commerce evidence; it does **not** establish that the
  compiler faithfully represented the original human text.

Human confirmation remains the authority boundary. Missing or hallucinated
constraints cannot be declared harmless solely because hard rules and semantic
fusion exist: those layers operate on what was confirmed, not an independent
reconstruction of the original instruction.

## Preserved measurement history

- F1 currency truth was corrected before measurement: phrases explicitly named
  rupees, so expected currency became INR rather than UNSPECIFIED.
- F13-002 requested monthly subscription but old truth wrongly required
  `recurring_forbidden=true`. Truth was corrected and that case remeasured;
  the discarded stale row remains in `discarded_stale_truth_rows.jsonl`.
  Golden hash changed from `eef70c9c…` to the current `9164f04c…`.
- Prompt v1 produced empty/truncated responses at budget 4000; v2 compressed the
  instructions. This was a within-M15 prompt change, not a frozen unseen test.
- A budget-2000 run produced four hard-case schema failures. Those original
  rows remain in `discarded_budget2000_rows.jsonl`; budget returned to 4000
  and cases were remeasured (F10-001 and F10-003 then passed). The present report
  does not erase those failures or infer a provider-wide success rate from them.

## Reproduction and remaining gate

Offline summary only, with no network or raw-result mutation:

```bash
services/api/.venv/bin/python scripts/rzp_summarize_compiler_eval.py
services/api/.venv/bin/pytest services/api/tests/test_compiler_eval.py
```

Artifacts: `data/phase3/compiler_eval/summary.json`, preserved `results.jsonl`,
the two preserved discarded-row files, and the unchanged golden set/manifest.
The summary reports `rescored=false` and explicit nulls for unsupported metrics.
For a separately authorized v2 run, the runner accepts `--output-dir`; summarize
its file using `--results <versioned-dir>/results.jsonl --output
<versioned-dir>/summary.json`. Payload-backed rows are actually rescored and
receive scalar/set present denominators and exact omission/substitution counts.
Scalar precision is scoped to explicitly annotated expectations (plus the
money-absence sentinel), not fields for which truth is unspecified. Partial
semantic/unspecified probes still cannot establish exhaustive precision.
Completion requires exactly the expected case-ID set; unknown IDs are rejected.

To close the missing metric evidence, recover original validated outputs or
run a separately versioned live evaluation that retains payloads. Do not
overwrite the prior result history or silently treat it as v2-scored. The golden
set also lacks positive currency-unspecified probes; that remains a coverage
limitation. **This correction alone does not mark the full M15 gate PASS.**
