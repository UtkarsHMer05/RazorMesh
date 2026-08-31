# FINAL VIDEO TRUTH FIX — Per-Gate Evidence Ledger

**Correction:** Post-Phase-5 Final Video Truth Fix (F001–F015), 2026-08-31.
**Baseline:** start HEAD `e934bfea14b6eeba316ac35b5e90b8ad7f58220f` (Phase-5
deep-engine correction, G001–G030 complete, clean tree).
**Scope discipline:** no rebuild, no redesign, no retrain, no frozen-eval rerun,
no threshold recalibration, v2 never activated, nothing weakened, nothing pushed.

---

## Gate summary

| Gate | Status | Main proof (evidence path under `docs/phase5/evidence/final-video-truth-fix/`) |
|---|---|---|
| F001 baseline freeze | PASS | `f001-baseline/` (git status+HEAD, health, governance status, 7 page screenshots, test-state record) |
| F002 NLI orientation | PASS | `f002-nli-orientation/` (pytest log 20/20, live canonical-pair response, governance summary) |
| F003 diff rendering | PASS | `f003-diff-rendering/` (vitest 10/10, backend diff with all 4 mutations, 3 page screenshots clean) |
| F004 protocol crypto | PASS | `f004-protocol-crypto/` (5 live runs jsonl, browser screenshot; 13 tests incl. causality) |
| F005 CWD independence | PASS | `f005-cwd-independence/` (live AI compile with backend CWD=services/api; 6 tests) |
| F006 single lineage | PASS | `f006-f008-mission-truth/` (protocol-thesis trace events; 6 tests; phase4 suite green) |
| F007 true labels | PASS | `f006-f008-mission-truth/mission-control-blocked.png` (every label matches action) |
| F008 13-node graph | PASS | `f006-f008-mission-truth/mission-control-firewall-live.png` (firewall=real PROTOCOL_PASS evidence; blocked trace stops at razorguard) |
| F009 chain semantics | PASS | `f009-f010-audit-truth/` (interleaved chain json + screenshot; never "LINK BROKEN" from interleaving) |
| F010 direct search | PASS | `f009-f010-audit-truth/` (checkout/order search works outside recent window; 6 tests) |
| F011 why semantic AI | PASS | `f011-why-semantic-ai/` (live API response + browser screenshot; real model pC≈0.9998) |
| F012 preflight | PASS | `f012-preflight/` (live 8-probe response + panel screenshot) |
| F013 README truth | PASS | README diff (commit `ce8361a`): precise AgentPay-X wording, current counts, all pages |
| F014 fresh-clone truth | PASS | 5 tests: settings-driven path (real env override), honest CHALLENGER_UNAVAILABLE, truthful `shadow_mode_available` |
| F015 rehearsal + regression | PASS | see below; rehearsal evidence in `f015-rehearsal/` |

---

## F001 — Freeze current state

- gate_id: F001
- status: PASS
- start_head: `e934bfe` (clean tree)
- end_head: `e934bfe` (no code change in this gate)
- files_changed: evidence only (`f001-baseline/*`)
- commands: `git status --short`, `git rev-parse HEAD`, `curl /health`,
  `curl /model-governance`, Playwright captures of all 7 pages,
  `pytest --collect-only` (945 tests), `npx vitest list` (25), `npx playwright test --list` (55)
- tests: baseline recorded, not executed (full gates run at F015)
- browser_actions: headless captures of buyer/mission-control/governance/
  protocols/security-lab/audit/merchant (all HTTP 200)
- real_engine_proof: active backend deberta/PRE_V2 `phase3-finetuned-v2`
  policy `semantic-thresholds-v3`; v2 `is_activated=False`,
  `can_authorize_payment=False`, shadow SHADOW—NON-AUTHORITATIVE available=True
- result: baseline frozen without deleting/overwriting owner work
- notes: servers were already running (:8000/:3000); Docker PG/Redis healthy

## F002 — Canonical NLI orientation in the real v2 shadow

- gate_id: F002
- status: PASS
- start_head: `e934bfe` · end_head: `603282b`
- files_changed: `model_governance.py` (canonical `shadow_verdict(commerce_evidence,
  authorization)`, orientation echo, truthful `shadow_mode_available`),
  `api/routes/model_governance.py` (explicit fields + legacy passthrough),
  `challenger_shadow.py` (settings-driven `_v2_dir()`),
  `apps/web/src/app/governance/page.tsx` (premise/hypothesis labels fixed),
  tests
- commands: `pytest tests/test_model_governance.py tests/test_challenger_shadow.py`
- tests: 20/20 exit 0 (incl. NEW `test_shadow_orientation_is_canonical_not_reversed`
  and `test_canonical_orientation_is_enforced_not_transposed` — the exact brief pair)
- browser_actions: (F015 rehearsal covers governance UI)
- real_engine_proof: live `POST /model-governance/shadow` with the brief's exact
  pair — premise "The current checkout contains a monthly recurring membership."
  hypothesis "This purchase must not include a recurring subscription." →
  ACTIVE PRE_V2 BLOCK pC=0.9999; challenger (real v2 artifact
  `f9e0007c…`, candidate A_2ep) BLOCK pC=0.9989; canonical orientation echoed;
  challenger non-authoritative
- result: BOTH lanes receive the same canonical orientation; reversing the pair
  produces different model outputs (proving the lanes are not transposed)
- notes: the previous default pair and UI labels were inverted
  (authorization-as-premise); frozen sets untouched, thresholds untouched

## F003 — Type-aware diff rendering

- gate_id: F003
- status: PASS
- start_head/end_head: `603282b` (part of the F001–F005 commit)
- files_changed: NEW `apps/web/src/lib/formatTransactionValue.ts` (+test),
  `mission-control/page.tsx`, `audit/AuditForensics.tsx`, `merchant/page.tsx`
- commands: `npx vitest run src/lib/formatTransactionValue.test.ts`, Playwright script
- tests: 10/10 (money, quantity, condition, merchant, currency, recurring
  string+object, null, booleans, objects, never-NaN garbage property)
- browser_actions: applied price_drift + quantity_increase + merchant_swap +
  hidden_membership to a real checkout, then scanned mission-control,
  audit-forensics, merchant for `₹NaN|NaN|[object Object]|undefined` → CLEAN;
  rendered rows verified (e.g. `quantity 1 2`, `unit_price_minor ₹1,899.00 →
  ₹2,399.00`, `subscription_terms None {frequency=monthly · recurring=Yes}`)
- real_engine_proof: diff rows come from the real
  `/mission-control/current-transaction` + `/forensics/trace/{id}` endpoints
- result: NO ₹NaN / NaN / [object Object] anywhere on the demo pages
- notes: pure money displays keep the original INR formatter; only diff
  rendering routes through formatTransactionValue

## F004 — Real protocol crypto

- gate_id: F004
- status: PASS
- start_head: `603282b` · end_head: `cfb7858`
- files_changed: `protocol_playground.py` (real-crypto lane
  `_run_ucp_real_crypto` / `_run_ap2_real_crypto` / `_run_packet_crypto`,
  truthful identity_signature engine label), `protocol/ap2_verifier.py`
  (InvalidSignature bug fix), `apps/web/src/app/protocols/ProtocolPlayground.tsx`
  (packet_crypto row + truthful label), NEW
  `tests/test_protocol_crypto_f004.py`, `tests/phase4/test_ap2_verifier.py`
- commands: `pytest tests/test_protocol_crypto_f004.py
  tests/test_protocol_playground.py tests/phase4/test_ap2_verifier.py
  tests/phase4/test_ucp_signatures.py`
- tests: 12 new causality tests + 1 tamper regression + existing suites green
- browser_actions: UCP safe → CRYPTOGRAPHIC SIGNATURE (REAL VERIFIER) PASS;
  UCP corrupt_signature → FAIL (real verifier `content_digest_mismatch`);
  MCP → honest "N/A — not implemented for this protocol"; no
  "CRYPTOGRAPHIC SIGNATURE VERIFIED" fake claim anywhere
- real_engine_proof: UCP = repo's RFC 9421 ES256/P-256 + RFC 9530 digest,
  signed then verified with `verify_ucp_request`; AP2 = repo's ES256 JWS with
  checkout-hash binding verified with `verify_ap2_merchant_jwt_es256`;
  verdicts derived from real verifiers over real (tampered) bytes — never the
  mutation name
- result: UCP/AP2 claims technically true; mcp/acp/a2a honestly labeled;
  **found + fixed a real production bug**: tampered AP2 JWT crashed the
  verifier with InvalidSignature instead of rejecting
- notes: causality proven both directions (corrupt bytes on safe label FAIL;
  re-sign PASS)

## F005 — Working-directory independence

- gate_id: F005
- status: PASS
- start_head/end_head: within `603282b`
- files_changed: `settings.py` (REPO_ROOT from source location; `_env_file_path`
  CWD-then-repo fallback; `repo_path()` helper; absolute key-path defaults),
  `keys.py` (relative key paths resolve against REPO_ROOT), `benchmark.py`,
  `api/routes/phase4_acceptance.py`, NEW `tests/test_cwd_independence.py`
- commands: pytest cwd tests (6/6); live: backend launched with CWD=
  `services/api` → real AI compile succeeded
- tests: 6 new (repo-root / services/api / /tmp probes; same keys from every
  CWD; absolute env overrides pass through; .env precedence)
- real_engine_proof: with CWD=services/api, `POST /buyer/intent-drafts/compile`
  returned a REAL draft (model `z-ai/glm-5.3-free`, Sony allowlist, ₹5000 cap,
  recurring forbidden) — the historical COMPILER_UNAVAILABLE trap is fixed;
  evidence `f005-cwd-independence/live-compile-from-services-api-cwd.json`
- result: repo-root launch, services/api launch, and foreign CWD all resolve
  configuration safely; env overrides intact

## F006 — One mission lineage

- gate_id: F006
- status: PASS
- start_head: `603282b` · end_head: `a203820`
- files_changed: `security_missions.py` (protocol-thesis runs the acceptance
  orchestrator on the mission's OWN intent; recipes carry
  `intent_max_quantity`/`intent_max_total_minor`), `merchant_sandbox.py`
  (caller-set intent profile), NEW `tests/test_mission_control_truth_f006.py`
- commands: pytest F006 tests + security-missions + merchant-sandbox + full
  `tests/phase4/`
- tests: 6 new (exactly-one-intent per run for ALL primary missions;
  cross-surface same-trace; scenario B/C wrappers still 200+BLOCK; recipe
  profile) + existing suites green
- real_engine_proof: live protocol-thesis mission: PROTOCOL_PASS →
  RazorGuard BLOCK (TOTAL_EXCEEDS_MAX) → semantic BLOCK pC=0.9996 → fusion
  BLOCK → ticket WITHHELD → provider 0 — all on ONE intent/checkout/trace
- result: the double-intent/double-trace path is removed; Scenario B/C remain
  compatibility wrappers (Phase-4 acceptance untouched and green)

## F007 — Mission Control wording/actions exactly true

- gate_id: F007
- status: PASS
- files_changed: `apps/web/src/app/mission-control/page.tsx`
- browser_actions: every control-deck button captured — navigation labeled
  "Open X (navigate) →", mission launches labeled "Launch new X mission",
  current-trace actions labeled "on current"; NEW current-trace buttons
  (Hidden recurring on current, Protocol mutation on current); the disguised
  nav button (testid mc-replay-scenario) removed; the false "Every action
  below acts on the CURRENT mission" claim replaced
- result: every button label accurately describes what actually happens
- notes: "Start safe mission" was a redirect — now honestly "Open Buyer —
  launch new mission (navigate) →"

## F008 — 13-node architecture visualization

- gate_id: F008
- status: PASS
- files_changed: `mission-control/page.tsx` (13-node PIPELINE),
  `trace_registry.py` (rejection-event projection key fix)
- browser_actions: blocked-trace render shows all 13 nodes: human, agent,
  merchant, protocol, **firewall PROTOCOL_PASS (from the real acceptance-run
  evidence)**, **ir DONE (packet reached the decision stages)**, razorguard
  BLOCK, semantic BLOCK, fusion BLOCK, ticket WITHHELD, provider —; packet
  stops at razorguard with the real stop marker
- real_engine_proof: firewall node status comes from the rejection event's
  real `protocol_firewall` payload — fixed the projection that read wrong keys
  (`firewall` vs `protocol_firewall`) and always rendered empty evidence
- result: no decorative nodes; BLOCK stops at the actual stage

## F009 — Global-chain vs trace-anchor semantics

- gate_id: F009
- status: PASS
- start_head: `a203820` · end_head: `18d8e1b`
- files_changed: `api/routes/forensics.py`, `apps/web/src/app/audit/AuditForensics.tsx`,
  NEW `tests/test_audit_truth_f009.py`, 2 stale tests updated
- tests: interleaved-trace test with the REAL ledger append path (unrelated
  global events BETWEEN a trace's anchors): trace view NOT broken, gap counts
  honest (`global_gap_before`, `directly_linked_to_prev`, total), global
  verify VALID over every event
- browser_actions: chain view header reads "THIS TRACE'S ANCHORS IN THE
  GLOBAL AUDIT CHAIN · ANCHORED"; "LINK BROKEN" absent; GLOBAL CHAIN VERIFY
  shows "CHAIN VALID over 2311 events"
- result: interleaving is never presented as a break; /audit/verify stays the
  cryptographic authority; tamper simulation remains read-only

## F010 — Direct indexed lookups

- gate_id: F010
- status: PASS
- files_changed: `api/routes/forensics.py` (search), AuditForensics label/placeholder
- tests: old checkout found with `TraceRegistry.recent` stubbed to empty
  (direct demo_traces/transaction_baselines/execution_attempts lookups);
  order-id lookup over execution_attempts + provider_events; every id shape
  resolves; unknown ids honest 404
- browser_actions: search by checkout id finds the dossier live
- result: no recent(100) dependence; UI placeholder
  "trace / intent / checkout / attempt / order"

## F011 — WHY SEMANTIC AI MATTERS

- gate_id: F011
- status: PASS
- start_head: `18d8e1b` · end_head: `0a00e10`
- files_changed: NEW `semantic_only_demo.py`, `/security-lab/why-semantic-ai`
  route, Security Lab UI section, NEW `tests/test_semantic_only_demo_f011.py`
- tests: 5 (real-model tightening; provenance; **frozen-data
  non-contamination** — fixture text absent from every frozen jsonl; API shape;
  fail-closed)
- real_engine_proof: live run — RazorGuard ALLOW (structured facts) → REAL
  active model BLOCK (pC 0.9998 / 0.9999) → real `fuse` seam BLOCK → ticket
  WITHHELD → provider calls 0; runtime identity `phase3-finetuned-v2` /
  `semantic-thresholds-v3`
- result: fixture frozen as NEW_DEMO_FIXTURE / NON_FROZEN /
  NOT_USED_FOR_MODEL_SELECTION; live-pipeline disclosure included (the
  structured evidence builder deliberately mirrors the rules — the demo
  exercises the semantic lane directly on evidence the rules were never taught)
- notes: honest search performed first — naive in-pipeline candidates PASS
  (disclosed; not faked); the demo pairs were verified against the real model
  BEFORE freezing the fixture; no thresholds touched, no frozen data touched

## F012 — DEMO PREFLIGHT

- gate_id: F012
- status: PASS
- start_head: `0a00e10` · end_head: `9193e24`
- files_changed: NEW `preflight.py`, `/mission-control/preflight` route,
  Mission Control UI (panel + per-trace environment badge), NEW
  `tests/test_preflight_f012.py`
- tests: 5 (all 8 probes real; environment stated; no secrets in response;
  honest not-ready; warm-up optional/non-authoritative)
- browser_actions: panel live — PostgreSQL SELECT 1, Redis PING, compiler
  configured, active model identity, v2 challenger loaded (A_2ep shadow-only),
  Ed25519 keys present, chain valid over 2311 events, **Payment environment:
  RAZORPAY TEST MODE**
- result: presenter readiness is real, secrets-free, and the environment line
  prevents presenting local missions as live provider transactions; warm-up
  performs a non-authoritative provider health request only

## F013 — README truth

- gate_id: F013
- status: PASS
- end_head: `ce8361a`
- files_changed: `README.md`
- result: AgentPay-X wording precise (191-scenario policy benchmark, 100%
  safe-pass/attack-block at the policy gate, 0 false allows/blocks; strict
  per-case 156/191 with the 35 firewall-granularity differences PRESERVED, not
  hidden; separate exactly-once/provider acceptance tests); current verified
  counts (backend 992 collected as separate targeted suites; live-ingress 13/13
  in isolation with the known full-suite flake disclosed; vitest 35/35); all
  pages including mission-control/governance/merchant; never "one invocation"

## F014 — Fresh-clone challenger truth

- gate_id: F014
- status: PASS
- end_head: `53a773f`
- files_changed: NEW `tests/test_challenger_freshclone_f014.py` (code landed with F002)
- tests: 5 (path IS `settings.semantic_model_path_v2` via the real env
  override; artifact-absent → CHALLENGER_UNAVAILABLE honest reason, no stub;
  governance `shadow_mode_available` mirrors real state; real artifact identity
  `f9e0007c…`/A_2ep)
- result: fresh clones degrade truthfully (CHALLENGER UNAVAILABLE + reason);
  this machine shows CHALLENGER READY; nothing hardcoded True

## F015 — Final rehearsal + full regression

- gate_id: F015
- status: PASS (details below; regression numbers in the final response)
- rehearsal evidence: `f015-rehearsal/` (story steps with screenshots)
- regression: backend mass suite exit 0; targeted new-gate suites green;
  phase-4 acceptance green; live-ingress 13/13 in isolation; ruff/mypy clean;
  tsc/eslint clean; vitest green; next build OK; Playwright smoke of the
  video story; security scan PASS; frozen ML evaluation NOT rerun

---

## F015 — Final rehearsal + full regression (detailed record)

- gate_id: F015
- status: PASS
- start_head: `53a773f` (after F013/F014) · end_head: this commit
- files_changed (beyond gate commits): `api/routes/buyer.py` (G012/G015 parity
  for buyer-proposed checkouts: immutable baseline capture + trace linkage +
  expected hashes), `apps/web/src/app/buyer/page.tsx` (fixture-intent auto
  effect suppressed once a draft exists — removes the intent/trace swap race),
  `apps/web/src/app/mission-control/page.tsx` (preflight state declared after
  setStatus — fixes eslint react-hooks ordering; lint now 0 errors),
  `scripts/security_check.py` + `TESTING.md` (allowlist entry for the status
  doc's quoted synthetic literal, justification recorded), mypy fixes
  (forensics/semantic_only_demo/security_missions), rehearsal evidence.
- commands (all recorded): pytest main suite (789 passed, exit 0 — the
  summary-line quirk under redirection documented in memory; 0 FAILED lines);
  pytest tests/phase4 (203/203, exit 0); live-ingress file in isolation
  (13/13, exit 0) after cleaning interactive-probe residue from razormesh_test
  (the probe runs had seeded the Scenario-B/C demo products + mission intents
  into the TEST database, making `catalog items[0]` the hidden-recurring
  product → RECURRING_NOT_ALLOWED on the ALLOW-chains; reproduced identically
  on PRISTINE e934bfe worktree — pre-existing state pollution, not a code
  regression); ruff clean; mypy clean (116 files); tsc clean; eslint 0 errors;
  vitest 35/35; next build OK; playwright full suite; security scan PASS
  (0 blocking).
- browser rehearsal (evidence `f015-rehearsal/`, 13 screenshots):
  1-2 preflight ALL COMPONENTS READY (incl. Payment environment RAZORPAY TEST
  MODE); 3-6 typed mandate → REAL AI compile (Sony allowlist, ₹5,000 cap,
  recurring forbidden) → draft; 7 CONFIRMED AUTHORITY + live trace;
  8-9 REAL shopping-agent search/rank (3 candidates) + selected candidate;
  10 checkout proposed ON THE SAME TRACE (post buyer-route linkage fix);
  11-12 Hidden recurring on current → authorized-vs-current diff
  (recurring No→Yes, frequency None→monthly, subscription_terms object
  rendered); 13 real 13-stage pipeline (IR DONE, razorguard stages);
  14-15 execute-current → REAL revalidation STALE_CHECKOUT (drift hashes
  displayed), ticket not minted, provider 0 (audit-verified call count);
  16-18 audit SAME trace: dossier, read-only replay, GLOBAL CHAIN VERIFY
  CHAIN VALID over 2,417 events + this-trace anchors (never "broken");
  19 protocol-valid/intent-invalid (API-verified: PROTOCOL_PASS → final BLOCK,
  provider false); 20 WHY SEMANTIC AI MATTERS (real model pC=0.9998;
  RG ALLOW → semantic BLOCK → fusion BLOCK → ticket WITHHELD → 0 calls);
  21 clean safe mission; 22 Razorpay Test boundary (order creation exactly-once
  per committed acceptance evidence); 24 REAL v2 shadow in canonical NLI
  orientation (ACTIVE BLOCK + challenger BLOCK, challenger IGNORED for
  authority); 26 governance truth (REJECTED / NOT ACTIVATED / shadow only).
- real_engine_proof: every rehearsal verdict came from the live engines
  (TokenRouter compile, DeBERTa semantic lane, deterministic rules, real
  revalidation contract, global ledger verify) — nothing painted.
- fixes found by the rehearsal (the point of the gate):
  (a) buyer-proposed checkouts never linked to the mission trace → Mission
  Control could not act on the video story's own checkout (G015 parity fix);
  (b) no G012 baseline for buyer-proposed checkouts → diff/execute failed with
  BASELINE_MISSING / predates-captured-hash (parity fix incl. expected
  hashes so the execute-current revalidation contract works);
  (c) fixture-intent auto-effect race could swap the active intent after
  confirm (UI fix); (d) mission-control preflight setState-before-declare
  lint error.
- known non-regressions (documented, per the recorded protocol):
  e2e reviewer-v2 3 specs fail ONLY because the owner's running `next dev`
  (PID on :3000, `reuseExistingServer: true`) lacks RAZORMESH_REVIEWER_ENABLED
  — verified identical on the pristine baseline; a fresh flagged server could
  not be spawned for comparison (Next refuses a second dev instance of the
  same project; `::1` IPv6 + port-refused artifacts recorded). Full-suite
  smoke:72 order-dependent flake passes in isolation (11/11 file run).
  The video does not use /reviewer.
- security_invariants: all preserved — no frozen eval rerun, no retraining,
  no recalibration, v2 never activated, BLOCKED never executes, tamper
  simulation read-only, no secrets exposed, nothing pushed.
- result: F001–F015 all individually PASS.

## Final acceptance token

RAZORMESH_FINAL_VIDEO_TRUTH_FIX_PASS
/ VIDEO_READY
/ CANONICAL_NLI_ORIENTATION
/ REAL_PROTOCOL_CRYPTO_WHERE_SUPPORTED
/ SINGLE_TRACE_DEMO
/ PRE_V2_ACTIVE
/ V2_REAL_SHADOW_NON_AUTHORITATIVE
