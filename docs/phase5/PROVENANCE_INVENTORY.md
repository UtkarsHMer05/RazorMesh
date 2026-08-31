# Phase-5 Provenance Inventory (Deep Engine Correction G002)

Classification of every judge-visible Phase-5 display state, per the master
prompt's six categories:

```
REAL_BACKEND              the real backend performed the action; UI visualizes its evidence
DERIVED_FROM_REAL_EVIDENCE UI state computed only from backend-returned evidence
READ_ONLY_REPLAY          replay rendered from recorded/pure-engine results, no side effects
INPUT_PRESET              control configures inputs only; backend decides outcomes
TEST_STUB                 explicit simulation; must be labeled as such
STATIC_COPY               static explanatory text; must never be presented as engine output
```

| Surface | Display state | Class | Notes / correction gate |
|---|---|---|---|
| Buyer | compile draft + constraint cards | REAL_BACKEND | real AI compiler via /buyer/compile |
| Buyer | search inspected/eligible/rejected counts | REAL_BACKEND | /agent/search computes from catalog rows |
| Buyer | decision pill ALLOW/BLOCK/CHALLENGE | REAL_BACKEND | RazorGuard decision from real pipeline |
| Buyer | semantic probabilities | REAL_BACKEND | live DeBERTa verifier |
| Buyer | ticket/provider states | REAL_BACKEND | audit events |
| Merchant | product list / checkout creation | REAL_BACKEND | durable checkout rows |
| Merchant | mutation before/after diff | DERIVED (with gap) | authorized side derived from CURRENT product row, not an immutable snapshot → G012 |
| Merchant | condition downgrade | REAL but leaks | mutates the SHARED catalog Product row → G013 |
| Merchant | revert | DERIVED (wrong) | forces condition="new", quantity=1, fees=0 — not true pre-mutation state → G014 |
| Merchant | trace evidence list | DERIVED_FROM_REAL_EVIDENCE | trace events |
| Merchant | new checkout trace binding | DERIVED (gap) | merchant page mints its own trace instead of adopting the current global live trace → G015 |
| Protocols | protocol/mutation catalogs | INPUT_PRESET | correct role |
| Protocols | firewall verdict + reasons | REAL_BACKEND | evaluate_envelope |
| Protocols | commitment head | REAL_BACKEND | commitment_hash(IR) |
| Protocols | consistency MATCH/MISMATCH (single run) | REAL_BACKEND | compare_ir_to_envelope |
| Protocols | schema_version check | PAINTED (gap) | status derived from mutation name, not an engine verdict → G006/G011 |
| Protocols | identity_signature check | PAINTED (gap) | FAIL painted because mutation=="corrupt_signature"; no artifact is corrupted, no verifier runs → G007 |
| Protocols | replay_idempotency check | PARTIAL (gap) | first-run real; FAIL branch painted → G006 |
| Protocols | amount mutation | REAL | IR total actually changes |
| Protocols | quantity mutation | PROXY (gap) | total×2 with quantity still 1 → G009 |
| Protocols | recurring mutation | PROXY (gap) | mutation missing from MUTATIONS action path — recurring never set on IR → G008 |
| Protocols | downgrade mutation | REAL | envelope version actually downgraded |
| Protocols | cross-protocol lanes | REAL for per-lane compare | compare_ir_to_envelope per lane |
| Protocols | cross-protocol envelope_consistency | PAINTED (gap) | equal_under_commitment(base_ir, base_ir) — compare-base-to-base → G010 |
| Security Lab | mission card B/C run | REAL_BACKEND | D-056 live orchestrator endpoints |
| Security Lab | price-drift/replay/forged cards | MISLABELED (gap) | all three call the FULL generic suite → G016 |
| Security Lab | attack movie Human/Agent/Merchant stages | STATIC (gap) | hardcoded "DONE" narrative constants; only protocol→provider stages come from evidence → G017 |
| Security Lab | campaign counters | REAL_BACKEND | run_benchmark() verbatim, cached |
| Security Lab | case explorer + case replay | REAL_BACKEND / READ_ONLY_REPLAY | single-scenario pure re-run |
| Mission Control | pipeline node states | DERIVED_FROM_REAL_EVIDENCE | trace events only |
| Mission Control | hidden-membership / protocol-thesis buttons | REAL actions | POST demo endpoints, bind trace |
| Mission Control | start safe mission / open audit / replay scenario | NAVIGATION (gap) | links only while deck implies actions; missing price/quantity/merchant/execute/revert actions → G019 |
| Mission Control | evidence sidebar | DERIVED (gap) | trace summary only; NO authorization-vs-current transaction diff → G020 |
| Mission Control | playback replay trace | DERIVED_FROM_REAL_EVIDENCE | re-renders fetched events (read-only) — real, but speed set changes interval only |
| Audit | timeline rows | DERIVED_FROM_REAL_EVIDENCE | projected audit events |
| Audit | auth-vs-current diff | DERIVED (incomplete) | total + subscription_terms only; misses merchant/product/condition/quantity/unit-price/fees/shipping/recurring → G021 |
| Audit | "Replay this trace" | STATIC_COPY (gap) | explanatory <details> text only, no playback → G022 |
| Audit | chain verify | REAL_BACKEND (global only) | no per-trace chain visualization → G023 |
| Governance | active/challenger cards + metrics | REAL_BACKEND | committed D-055 facts, test-enforced |
| Governance | shadow check | TEST_STUB MISLABELED (gap) | runs DeterministicKeywordVerifier next to "AgentPay-IR v2" framing — a judge can read the stub AS the challenger → G003/G005 |
| Governance | evidence drawer | REAL_BACKEND | committed frozen evaluation JSON (redacted) |
| All pages | trace badge | DERIVED_FROM_REAL_EVIDENCE | backend-minted RM- ids only |
| Buyer | payment FSM states | REAL_BACKEND | mock provider + status endpoints |

**Summary of gaps** (each mapped to its correction gate): keyword-stub shadow (G003–G005),
painted protocol checks + proxy mutations + base/base cross-compare (G006–G011),
mutable merchant baseline + shared-row mutations + wrong revert + disconnected trace
(G012–G015), suite-for-one-card missions + hardcoded movie DONE (G016–G018),
link-only deck + missing diff (G019–G020), shallow forensic diff + text-only replay +
global-only chain (G021–G023), benchmark wording (G024–G026).

No judge-visible state has unknown provenance after this table.
