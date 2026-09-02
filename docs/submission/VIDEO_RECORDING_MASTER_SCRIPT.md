# RazorMesh — Final Video Recording Script

> **Director's note.** This script was produced by walking the real application,
> on the current build, with every wait measured live (2026-09-01). Every button
> label below is copied from the running UI. Nothing is invented. Where a value
> can vary run-to-run (semantic probabilities, event counts, latency), ranges or
> "read what the screen shows" is used instead of a fixed number.

---

## 1. Recommended duration

| Version | Target | Maximum | When to use |
| --- | --- | --- | --- |
| **PRIMARY** | **3:30–4:00** | 4:30 | The recommended recording |
| EMERGENCY SHORT | 2:00–2:30 | 2:45 | Only if a live action fails late in the primary take |

The repository's own storyboard (`docs/phase5/VIDEO_STORYBOARD.md`) targets
90–150 s for a minimal cut; this script covers the same core arc at a calmer,
safer pace (real AI compile alone can take 25–60 s), plus the three proof
sections (semantic, governance, audit) that make the story credible.
**Do not exceed 4:30.** If you are over time, cut sections in this order:
(1) Protocol playground, (2) Governance shadow run, (3) Merchant page —
never cut the attack or the audit.

---

## 2. Video story in one sentence

A human authorizes a ₹5,000 one-time purchase, a merchant silently adds a
monthly subscription after authorization, and RazorMesh refuses the payment —
protocol-valid packet, zero provider contact, full audit evidence — because
**the transaction that executes must still be the transaction the human
authorized.**

---

## 3. Pre-recording environment

Run these from the repo root. Expected successful responses are listed after
each command.

```bash
# 1. Infrastructure (Postgres 127.0.0.1:15432 + Redis 127.0.0.1:16379)
docker compose up -d
docker compose ps        # expect: razormesh-postgres Up (healthy), razormesh-redis Up (healthy)

# 2. Migrations + catalog seed (idempotent)
uv run --project services/api alembic upgrade head   # expect: no error output
uv run --project services/api python -m razormesh_api.catalog   # expect: silence = success

# 3. Config sanity (names only, never values)
uv run --project services/api python -c "
from razormesh_api.settings import Settings, validate_payment_provider_config
s = Settings(); validate_payment_provider_config(s)
print(s.payment_provider, s.razorpay_mode)"      # expect: razorpay test

# 4. Backend API (with the live DeBERTa semantic runtime) — terminal window 1
uv run --project services/api --group semantic uvicorn razormesh_api.api.main:app --host 127.0.0.1 --port 8000
# expect eventually: INFO: Application startup complete.
curl -s http://127.0.0.1:8000/ready
# expect: {"status":"ok","checks":{"postgres":"ok","redis":"ok"},"payment_provider":"razorpay",...}

# 5. Frontend — terminal window 2
cd apps/web && pnpm dev          # expect: ✓ Ready on http://localhost:3000
```

- **Backend URL:** http://127.0.0.1:8000 (health at `/health`, readiness at `/ready`)
- **Frontend URL:** http://localhost:3000 (use **localhost**, not 127.0.0.1 — the dev
  CORS origin is `http://localhost:3000`)
- Leave both terminal windows running but **hidden during recording** (see §4).
- The zrok webhook tunnel is NOT required for this video (webhooks are proven by
  the committed test suite, not shown live).

### THE ONE CRITICAL EXTERNAL DEPENDENCY — the AI Intent Compiler

The Buyer mandate compile is a **real LLM call** (TokenRouter →
`z-ai/glm-5.3-free`). During the director's rehearsal on 2026-09-01 the
upstream provider **flapped between ~25 s responses, ~112 s responses, instant
failures, and 120-second timeouts** (the app correctly returns
`502 COMPILER_UNAVAILABLE` and never fakes a draft). **You MUST run the
30-second compiler verification in §19 (step 3) before recording.** If the
compiler is degraded, either wait and retry, or record the EMERGENCY SHORT
version (§18) which reduces the live-compile exposure to one beat.

---

## 4. Browser preparation

Use **Chrome**. One window, **five tabs in this exact order** (so Cmd+1…Cmd+5
are stable):

| Tab | Route | State before recording |
| --- | --- | --- |
| **TAB 1 — Mission Control** | `http://localhost:3000/mission-control` | Loaded; presenter mode ON (button top-right: **Presenter mode** → badge shows **RECORDING VIEW**); preflight panel visible from §19 check |
| **TAB 2 — Buyer** | `http://localhost:3000/buyer` | Loaded; mandate textarea empty |
| **TAB 3 — Security Lab** | `http://localhost:3000/security-lab` | Loaded; scrolled to the **Why semantic AI matters** card |
| **TAB 4 — Governance** | `http://localhost:3000/governance` | Loaded; scrolled so the challenger metrics table is in view |
| **TAB 5 — Audit** | `http://localhost:3000/audit` | Loaded |

Preparation rules (all verified during rehearsal):

- **Resolution 1920×1080** (the pipeline's 13 nodes were readability-verified at
  1920×1080, 1440×900 and 1280×800; 1080p is the comfortable default). The
  rehearsal used 1600×900 successfully.
- **Browser zoom 100%** (Cmd+0). Do not zoom.
- **Presenter mode ON** on Mission Control (enlarges the pipeline).
- **DevTools CLOSED** (Cmd+Option+I) — never show the console.
- **Bookmarks bar hidden** (View → Always Show Bookmarks Bar OFF).
- **Terminal windows hidden** (minimize both; if a failure forces you to touch
  a terminal, pause the recording first — see §17).
- **Cursor**: macOS default cursor is fine; do NOT install a highlighter plugin
  (it draws attention to idle wiggling). Move the cursor deliberately,
  hover-and-hold as the script says, and park it between beats.
- **Theme**: the app is a fixed light Bauhaus design; keep the OS in light mode
  so the browser chrome matches.
- **Notifications OFF**: macOS Focus/Do-Not-Disturb ON for the whole recording.
- **The `LIVE MISSION` chip in the header will show some trace id** — that is
  fine and truthful; the script below rebinds it live on camera.
- **Refresh each tab immediately before pressing Record** (Cmd+R in all five,
  left to right, ending on TAB 1).

---

## 5. Demo state preparation

The app is **append-only by design**: old traces stay in Audit forever and this
is a FEATURE (the closing narration uses it). No destructive reset is needed or
performed. Do NOT run `make reset-local` (it is destructive and forbidden for
this session).

1. In TAB 1 (Mission Control), click **Run demo preflight**, then
   **Preflight + warm-up compiler** (the warm-up issues a non-authoritative
   health request AND warms the provider connection so the first real compile
   is not the slowest). The panel must show **REQUIRED SYSTEMS READY** with
   every required component ✓, the Payment environment line reading
   **RAZORPAY TEST MODE** (this text becomes the env badge next to the trace
   id), and the AI Intent Compiler showing
   **LIVE REACHABLE — provider health request succeeded**.
2. Verify the semantic model loaded: preflight line
   **Active Semantic Model — verifier loads: phase3-finetuned-v2 · policy
   semantic-thresholds-v3**.
3. If preflight shows **NOT READY — FIX BEFORE RECORDING**, stop. Fix per §17.
   The optional V2 Challenger Shadow line is optional by design — it never
   gates payment safety; if unavailable, the Governance shadow beat falls back
   per §17 (the static metrics table still works).

A fresh trace IS generated live during the video (the whole point). Nothing is
pre-baked.

---

## 6. Exact buyer prompt

Paste/type this EXACT text into the mandate box (TAB 2):

```
Buy Sony WH-1000XM5 wireless headphones under ₹5,000 all-in total, new condition only, quantity 1, one-time purchase with no subscription or recurring charges.
```

Why this wording (all verified live in rehearsal):

- It compiles cleanly to a **DRAFT** state on the first try. Shorter variants
  ("which form factor?") produced `NEEDS_CLARIFICATION` — avoid them.
- The compiler extracts exactly the constraint cards you narrate:
  **Budget (all-in) ≤ ₹5,000.00 · Brand Sony · Condition New (inferred) ·
  Recurring Forbidden · Product Sony WH-1000XM5 · Max quantity 1**.
- The catalog really contains the XM5 (₹4,799.00, free shipping) — it ranked
  #3 in rehearsal because two cheaper Sony items beat it on all-in price; the
  script clicks the XM5 card deliberately (it is the premium-looking choice and
  the 52→3 filtering story is the interesting part).
- It sets up the attack: "no subscription or recurring charges" is the exact
  constraint the merchant violates.

---

## 7. Main scenario (story in 8 lines)

1. Human types a natural-language mandate; the real AI compiler turns it into
   inspectable constraints.
2. The human confirms — that click is the ONLY place authority is created.
3. The shopping agent really searches 52 catalog products, filters to 3
   eligible, and ranks candidates; the human picks the XM5 (₹4,799).
4. The agent proposes the checkout; deterministic RazorGuard says **ALLOW** and
   a ticket is issued on the same trace.
5. The merchant mutates the offer after authorization: a hidden ₹499/month
   membership appears.
6. The same trace is pushed through the executor's real revalidation contract:
   **STALE_CHECKOUT** — the ticket's checkout hash no longer matches; the
   transaction "would never reach the provider."
7. Razorpay provider calls stay **0** (audit evidence), even though the
   protocol layer is valid.
8. The Audit page proves it on the same trace: diff (recurring No→Yes), global
   hash chain VALID, read-only replay that changes nothing.

Then three proof sections: protocol crypto playground (why protocol validity ≠
authority), WHY-SEMANTIC-AI (deterministic rules alone would have ALLOWed), and
Model Governance (a better-scoring model was REJECTED for safety).

---

## 8. FULL WORD-FOR-WORD RECORDING SCRIPT

Read the SAY column **exactly**. Short sentences. If you finish early, hold
silence for one breath — do not rush into the next click.

| Time | Tab | Action (exact) | Expected screen state | SAY THIS EXACTLY |
| --- | --- | --- | --- | --- |
| 00:00–00:08 | TAB 1 — Mission Control | No click. Presenter mode ON. Full pipeline visible, nodes pending. Cursor rests near the pipeline. | Pipeline visible; nodes mostly "—"; env badge may show the prior trace id. | "AI agents can produce payment requests that are perfectly valid at the protocol layer — and still violate what the human actually approved. RazorMesh exists to stop exactly that." |
| 00:08–00:14 | TAB 1 | No click. Hover cursor slowly down the pipeline: Human → Agent → Merchant → Protocol → Firewall → RazorGuard → Ticket → Razorpay. | Nodes stay pending (or show an old trace's states — do not worry). | "Protocol validity is not transaction authority. Here is the pipeline every transaction must survive — and today we'll push a real one through it." |
| 00:14–00:20 | TAB 1 | Hover the preflight panel (already open from §5). Point at "REQUIRED SYSTEMS READY" and the Payment environment line. | Panel shows REQUIRED SYSTEMS READY; RAZORPAY TEST MODE; semantic model loaded. | "Everything is live and local. Razorpay Test Mode — no real money. The semantic trust model is loaded. Let's create a human mandate." |
| 00:20–00:24 | **SWITCH TO TAB 2 — Buyer** (Cmd+2) | — | Buyer page: "1 · Human mandate". | "The buyer describes what they allow — in plain language." |
| 00:24–00:31 | TAB 2 | Click the mandate textarea; type/paste the §6 prompt EXACTLY. | Textarea shows the full mandate (3 rows). | "Buy Sony WH-1000XM5 wireless headphones. Under five thousand rupees, all-in. New condition. One-time purchase — no subscription, no recurring charges." |
| 00:31–00:35 | TAB 2 | Click **Compile mandate**. | Button shows "Compiling…"; stage checklist lights up: Reading mandate → Extracting constraints. | "The AI compiler turns those words into explicit constraints." |
| 00:35–00:60 | TAB 2 | WAIT. Do not click anything. Narrate through the wait (this is the real LLM call — 25–60 s when healthy). Keep cursor parked below the stage checklist. | "Validating" then "Draft ready" light up; constraint cards appear: Budget ≤ ₹5,000.00 · Brand Sony · Condition New · Recurring Forbidden · Product Sony WH-1000XM5 · Max quantity 1. | (start the beat when you click, ~25 s of speech) "While it works — three things matter. The compiler only drafts. Nothing here is authority yet. The human sees every constraint before any money can move. And the mandate is now explicit — a budget, a brand, a condition, a quantity, and a hard ban on recurring charges." (when cards appear) "There they are — exactly what was asked for." |
| 01:00–01:05 | TAB 2 | Click **Confirm — grant authority**. | Green **■ AUTHORITY GRANTED** banner; "Live mission RM-XXXXXX — follows you on every page"; agent checklist starts. | "Now the human confirms. This click is the only place authority is ever created." |
| 01:05–01:14 | TAB 2 | WAIT ~8 s. Hover the agent checklist, then the candidate cards. | Checklist: "Inspecting 52 catalog products (real count)"; "3 eligible · 49 rejected"; three candidate cards appear. | "The shopping agent just inspected fifty-two real products. Forty-nine were rejected against the mandate. Three survived." |
| 01:14–01:20 | TAB 2 | Click candidate card **#3 Sony WH-1000XM5 Wireless Headphones** (₹4,799.00, free shipping). Hover the "Why the agent chose this" list. | Card #3 becomes selected; why-list shows ✓ total ≤ budget, ✓ brand Sony, ✓ condition new. | "The human picks the XM5 — forty-seven ninety-nine, inside the five-thousand cap. The agent only proposes; it cannot pay." |
| 01:20–01:24 | TAB 2 | Click **Propose checkout**. | "Checkout proposal" summary: item, qty 1, total ₹4,799.00 server-recomputed; decision appears. | "The agent proposes the checkout. The server recomputes the total — the browser's number never counts." |
| 01:24–01:30 | TAB 2 | Hover the decision line and the small trust pipeline row. | **ALLOW** with no reason codes; ticket issued. | "Deterministic RazorGuard says ALLOW. Every constraint holds — so a single-use execution ticket is issued on this trace." |
| 01:30–01:36 | TAB 2 | Point at the "Payment provider boundary" card at the bottom (Razorpay contacted NO · Provider calls 0). Say the line, then hover the mission trace chip in the header. | "Razorpay contacted: NO — no authority to execute. Provider calls: 0." | "No one has paid yet. The ticket exists, but nothing touches Razorpay until execution. Keep an eye on this trace id — the same mission follows us everywhere." |
| 01:36–01:40 | **SWITCH TO TAB 1 — Mission Control** (Cmd+1) | — | Pipeline shows the live mission: Human DONE, Shopping Agent DONE, RazorGuard ALLOW, Ticket DONE; env badge RAZORPAY TEST MODE; same trace id as Buyer. | "Mission Control shows the same mission — same trace, same authorization." |
| 01:40–01:46 | TAB 1 | Hover the **Control deck**; point at "Actions on the CURRENT mission's transaction". | Deck shows trace id = live mission; buttons "…on current" enabled. | "Now the merchant attack. This button acts on the current transaction — the one that was just authorized." |
| 01:46–01:53 | TAB 1 | Click **Hidden recurring on current**. | Status line: "Hidden recurring membership (Rs499/month): changed subscription_terms. Original human mandate preserved — the confirmed IntentContract is untouched." Merchant node flips to DONE. | "The merchant silently adds a membership — four ninety-nine, every month. The mandate said no recurring charges. Watch what the system does with the same authorization." |
| 01:53–02:00 | TAB 1 | Hover the "Current transaction — authorized vs current" diff table. Read the changed fields aloud from the screen. | Diff rows: recurring No→Yes ← CHANGED · recurring_frequency None→monthly ← CHANGED · subscription_terms None→{frequency=monthly · recurring=Yes} ← CHANGED. | "Authorized: no recurring. Current: a monthly membership. The immutable baseline captured at proposal time proves the drift." |
| 02:00–02:06 | TAB 1 | Click **Execute current transaction**. | Status: "**STALE_CHECKOUT** — The transaction FAILED the executor's revalidation contract - it would never reach the provider." (~5 s wait) | "Now push it to execution." (wait) "STALE_CHECKOUT. The ticket is bound to the original checkout hash. The mutated transaction never reaches the provider." |
| 02:06–02:12 | TAB 1 | Point at the **Provider calls: 0** row in the Evidence sidebar. | Provider calls: 0. | "Razorpay was never contacted. Zero calls. The money simply cannot move." |
| 02:12–02:20 | **SWITCH TO TAB 5 — Audit** (Cmd+5) | The page loads; click the top recent-mission card with your trace id (or it deep-links via the mission control "Open Audit" link — the script uses the card). | Forensics dossier opens: timeline, Authorization vs current diff, Provider contact NO / 0 calls, chain anchors. | "The audit ledger proves it end to end — on the same trace." |
| 02:20–02:28 | TAB 5 | Hover the **Transaction timeline** top-to-bottom; then the **Authorization vs current** diff. | Timeline shows the mission's events; diff shows recurring No→Yes ← CHANGED. | "The full story is here — mandate confirmed, checkout proposed, ALLOW, ticket issued, then the merchant mutation. And the same drift: authorized no, current yes." |
| 02:28–02:36 | TAB 5 | Click **▶ Play** on "Replay this transaction (read-only playback)". Let it run (~5–7 s at 1×). | Position walks "1 / N … N / N"; current-event line updates; after finish the provider card still reads 0. | "Replay re-renders the stored evidence. It can never re-execute — no new tickets, no new provider calls. The count stays zero." |
| 02:36–02:42 | TAB 5 | Click **Verify hash chain** (top-right of the search row). | "CHAIN VALID over N events (backend verifier)" (N grows over time; read the number on screen). | "And the global hash chain validates — every event tamper-evident, history that cannot be quietly rewritten." |
| 02:42–02:47 | **SWITCH TO TAB 3 — Security Lab** (Cmd+3) | Scroll so the "Why semantic AI matters — semantic-only tightening" card is centered. | Card + button **Run WHY SEMANTIC AI MATTERS demo** visible. | "One question remains. If the deterministic rules are this strong, why does a semantic model exist?" |
| 02:47–02:53 | TAB 3 | Click **Run WHY SEMANTIC AI MATTERS demo**. WAIT ~2–10 s (real engines run). | Table appears: Structured RazorGuard **ALLOW** · Semantic Trust Check **BLOCK** · Conservative Fusion **BLOCK** · ExecutionTicket **NOT ISSUED** · Execution Attempt **NOT CREATED** · Provider calls **0**. | "Run it. A fresh transaction. On structured facts alone, the deterministic rules ALLOW — the structure looks fine. But the commerce evidence hides a continuing-service term. The semantic model reads it against the human authorization — and blocks. Fusion only tightens." |
| 02:53–02:59 | TAB 3 | Hover the result table rows top to bottom, ending on "Provider calls 0". | Rows as above; story paragraph below. | "So no ticket is ever issued. No execution attempt is created. Zero provider calls. Structure alone would have paid. The semantic layer is what caught it." |
| 02:59–03:05 | **SWITCH TO TAB 4 — Governance** (Cmd+4) | Scroll so both model cards and the challenger metrics table are visible. | ACTIVE card (Active Safety Model) + REJECTED challenger card: Human gold unsafe C→E **2 → 7 WORSENED**; macro-F1 **0.893 → 0.7757 REGRESSED**; OOD **5 → 6 WORSENED**; normal test **0.7367 → 0.9752 improved — not enough**. | "And the model itself is governed. We trained a challenger with far better headline accuracy. But on the security-critical human-gold set, the errors that matter got worse — two became seven. So the gate refused to activate it." |
| 03:05–03:12 | TAB 4 | Hover the "Human gold — unsafe contradiction→entailment 2 7 WORSENED" row, then the REJECTED banner. | As above. | "The active model stays active. The challenger can only run in a shadow lane — never fusion, never tickets, never the provider." |
| 03:12–03:20 | TAB 4 | (Optional if time allows, else skip to the close.) Click **Run shadow check** (defaults are fine). WAIT ~2–8 s. | Comparison table: ACTIVE lane vs CHALLENGER lane with probabilities; footer "Authority: ACTIVE MODEL ONLY · CHALLENGER IGNORED · never enters fusion / ticket / provider". | "Here is that shadow — the real rejected checkpoint, running beside the active model. Whatever it says, it is ignored for authority." |
| 03:20–03:26 | **SWITCH TO TAB 1 — Mission Control** (Cmd+1) | No click. Full pipeline of the attack trace on screen; "The packet stopped at razorguard — Razorpay was never contacted." banner visible (if the last trace shown is the protocol-thesis trace) OR the attack trace with STALE_CHECKOUT status. | Final full-screen state. | "Protocol-valid packets. Deterministic rules. Semantic trust. Model governance. And one principle underneath all of it." |
| 03:26–03:35 | TAB 1 | Slowly hover the pipeline one last time, Human → Razorpay, and stop on the Razorpay node. | — | "RazorMesh lets AI agents propose and negotiate — without ever giving them authority to spend. The AI proposes. RazorGuard authorizes. The trusted executor executes. The transaction that executes must still be the transaction the human authorized. That is intent-to-execution integrity." |

**END — 3:35.** If your naturally-spoken version lands between 3:30 and 4:00 it
is perfect.

---

## 9. Cursor choreography

Deliberate hover-and-hold; never wiggle. The five moments where the cursor
carries the story:

1. **00:08** — sweep the pipeline top-to-bottom in ~5 s, one node per
   half-second.
2. **01:53** — park ON the diff table's "recurring" row while saying the
   authorized/current values; tap nothing.
3. **02:06** — circle the Provider calls 0 row once, then hold still on it.
4. **02:53** — walk the semantic result table row by row, ending on Provider
   calls 0.
5. **03:26** — final slow pipeline sweep, ending parked on the Razorpay node
   for the closing sentence.

---

## 10. Tab switching cheat sheet

Tabs are in fixed order (§4), so keyboard switching is stable and recommended:

```
Cmd+1  Mission Control
Cmd+2  Buyer
Cmd+3  Security Lab
Cmd+4  Governance
Cmd+5  Audit
```

Order used by the script: 1 → 2 → 1 → 5 → 3 → 4 → 1. If you prefer visible
clicks on the tab strip, that is equally fine — just never hunt for a tab; the
keyboard is the safety net.

---

## 11. Pause / wait timing (measured 2026-09-01)

| Step | Wait | Narrate through? |
| --- | --- | --- |
| **Compile mandate** (real LLM) | **~25–60 s when the provider is healthy; the upstream was flapping on 2026-09-01 (25 s and 112 s successes, then instant failures and 120 s timeouts)** — §19 gate 3 decides if you may record | YES — the 00:35–01:00 beat is written for it |
| Confirm — grant authority | < 1 s | no |
| Shopping agent search (auto-runs) | ~2–8 s | yes ("fifty-two real products…") |
| Propose checkout → ALLOW | ~2–4 s | yes ("the server recomputes…") |
| Hidden recurring on current | ~5 s | hold one breath |
| Execute current transaction → STALE_CHECKOUT | ~5 s | say "Now push it to execution." then wait silently |
| Audit replay play button | runs 5–7 s at 1× | yes (written) |
| Verify hash chain | ~1–2 s | no |
| WHY SEMANTIC AI demo | ~2–10 s | yes (written) |
| Governance shadow check | ~2–8 s | yes (written) |
| Protocol playground send (if §13 used) | ~4–10 s | yes |

---

## 12. Exact values expected on screen

Say numbers from the screen where they vary; the constants below are stable.

| Screen | Expected |
| --- | --- |
| Constraint cards | Budget ≤ ₹5,000.00 · Brand Sony · Condition New · Recurring Forbidden · Product Sony WH-1000XM5 · Max quantity 1 |
| Agent search | Inspecting 52 catalog products · 3 eligible · 49 rejected |
| XM5 candidate | #3 Sony WH-1000XM5 Wireless Headphones · ₹4,799.00 · free shipping · All-in ₹4,799.00 |
| Checkout decision | **ALLOW**, total ₹4,799.00 (server-recomputed) |
| Provider boundary (pre-attack) | Razorpay contacted NO · Provider calls 0 |
| Attack status | Hidden recurring membership (Rs499/month): changed subscription_terms |
| Diff rows | recurring No→Yes · recurring_frequency None→monthly · subscription_terms None→{frequency=monthly · recurring=Yes} |
| Execute outcome | **STALE_CHECKOUT** — "would never reach the provider" |
| Attack-trace evidence | Provider calls 0 |
| Audit chain | CHAIN VALID over N events (read N from screen; grows every run) |
| Semantic demo | Structured RazorGuard **ALLOW** · Semantic **BLOCK** (p(contradiction) ≈ 0.999–1.000, read from screen) · Fusion **BLOCK** · Ticket **NOT ISSUED** · Attempt **NOT CREATED** · Provider **0** |
| Governance table | gold C→E 2→7 WORSENED · gold macro-F1 0.893→0.7757 REGRESSED · OOD 5→6 WORSENED · normal 0.7367→0.9752 improved — not enough |
| Governance cards | ACTIVE: deberta (PRE_V2 runtime), policy semantic-thresholds-v3 · CHALLENGER: REJECTED — M2_FROZEN_EVALUATION_FAIL / V2_NOT_ACTIVATED |

---

## 13. Safe-flow segment (Razorpay Test order)

**Included as a narrated boundary, NOT a live modal.** The in-modal card entry
is a documented human-only sandbox step on this account, and the committed
acceptance evidence already proves the safe chain: RazorGuard ALLOW → ticket →
trusted executor → **Razorpay Test order created exactly once**; every attack
chain: zero provider contact. Use the 01:30 beat ("No one has paid yet…") to
state it. If the owner wants the live safe path anyway, it is a separate,
post-recording option (Buyer → Propose → **Pay securely via Razorpay (Test
Mode)** → modal) — but **never** say "payment completed" unless one actually
completed on camera. Correct phrasing: "A Razorpay Test order is created
exactly once."

Optional +20 s protocol-crypto beat (only if under 3:10 at 02:42): switch to
`/protocols`, with **UCP** selected choose mutation **Corrupt signature/digest
(real bytes corrupted)** → **Send through gateway** → the check list shows
Cryptographic signature **FAIL** (real ES256/P-256, RFC 9421 + RFC 9530
Content-Digest: `content_digest_mismatch`) while Schema stays PASS — then say:
"Real cryptographic verification for UCP and AP2. MCP, ACP and A2A contribute
protocol binding and normalization evidence. And even a packet that passes all
of this still has to face RazorGuard." **Skip this beat if time is tight.**

---

## 14. Final closing shot

TAB 1 — Mission Control, presenter mode, the attack trace's pipeline on screen:
Human DONE → Shopping Agent DONE → Merchant DONE (offer.mutated) → … →
Execution Ticket WITHHELD or the STALE_CHECKOUT status visible, Provider calls
0 in the sidebar, RAZORPAY TEST MODE badge next to the trace id.

---

## 15. Exact closing words

> "RazorMesh lets AI agents propose and negotiate — without ever giving them
> authority to spend. The AI proposes. RazorGuard authorizes. The trusted
> executor executes. The transaction that executes must still be the
> transaction the human authorized. That is intent-to-execution integrity."

Hold the final frame two seconds after the last word. Stop recording.

---

## 16. Do not say / do not show

**Never show:** the `.env` file; any API key or secret; the terminal during the
take; DevTools; stack traces; local filesystem paths; the `/reviewer` page;
row-level gold/review data; frozen-evaluation internals beyond the governance
panel's approved aggregates; long commit hashes; test card numbers.

**Never say (banned phrases + corrections):**

| ❌ Never say | ✅ Say instead |
| --- | --- |
| "Razorpay payment completed" / "we paid" | "A Razorpay Test order is created exactly once" (order creation ≠ payment) |
| "All five protocols use cryptographic signatures" | "UCP and AP2 use real cryptographic verification; MCP, ACP and A2A contribute protocol binding and normalization evidence." |
| "v2 is the active model" | "PRE_V2 remains active; the v2 challenger is shadow-only." |
| "the semantic model authorizes payments" | "The semantic model can only tighten a decision — it never issues tickets and never contacts the provider." |
| "fraud-proof" / "production ready" / "perfectly secure" | "A local prototype of the trust core — every decision auditable." |
| "AI bought the headphones" | "The human authorized; the agent proposed; the system executed within that authority." |
| "it detected fraud" | "it detected authorization drift" |
| "99.99% accurate" or any invented metric | read only the numbers visible on screen |
| "Phase 5" / milestone codes (M00x, G0xx, R0xx, S0xx, F0xx) | nothing — the audience needs no internal history |
| "as you can see" (more than twice) | point with the cursor and state the fact |
| "basically", "actually", "so yeah", "kind of" | — (omit) |

**Wording precision for the main attack:** the hidden membership is caught by
the executor's revalidation contract (STALE_CHECKOUT: the ticket is bound to
the original checkout hash). Do not claim "semantic BLOCK" for THIS beat — the
semantic-only story is the separate Security Lab section, and there the
deterministic engine genuinely ALLOWs first. Narrate exactly what each beat
shows.

---

## 17. Failure recovery (bounded, honest, never fake)

**IF PREFLIGHT ≠ REQUIRED SYSTEMS READY:** do not record. Fix the failing
required line (Postgres/Redis: `docker compose up -d`; API: see its terminal),
then re-run **Preflight + warm-up compiler**. An *optional* component
(the V2 Challenger Shadow) being unavailable does NOT block recording — skip
the 03:12 shadow beat and keep its narration on the static table.

**IF THE AI COMPILER SLOW (>20 s):** keep narrating the written 00:35–01:00
beat; the script is timed for up to 60 s of wait. If it exceeds ~75 s, say
"…the live model is under load — one moment," and let it land.

**IF THE AI COMPILER FAILS (502 COMPILER_UNAVAILABLE / NEEDS_CLARIFICATION):**
do not improvise, do not open DevTools. Click **Compile mandate** once more. If
it fails again: leave the textarea state, switch the story to the EMERGENCY
SHORT version (§18) — its Buyer beat is already recorded in the can (the first
take's compile) or use the pre-confirmed mission path: the attack, audit,
semantic, and governance sections need no compiler. Never claim a draft that
did not appear.

**IF THE ATTACK BUTTON CLICK MISSES / page scrolled:** re-click **Hidden
recurring on current** once. The mutation is idempotent per checkout revision;
a double-click just re-mutates the same revision (verified in rehearsal).

**IF EXECUTE-CURRENT DOES NOT SHOW STALE_CHECKOUT:** stop; do not proceed to
the audit beat; re-click **Execute current transaction** once. If it still
shows anything else, **stop the take** — this beat is the spine of the video.
(Wrong outcome here means the checkout was not mutated — re-check the diff
table shows recurring Yes before executing.)

**IF THE SEMANTIC DEMO BUTTON SHOWS AN ERROR CARD:** wait 5 s, click **Run WHY
SEMANTIC AI MATTERS demo** once more (first run can cold-load the model).
Second failure → skip the section; say instead (on Governance): "the semantic
layer runs the active fine-tuned model — and when inference fails, it fails
closed to a challenge — never an allow." (True and frozen policy.)

**IF GOVERNANCE SHADOW RETURNS CHALLENGER UNAVAILABLE:** that is the honest
state; point at it and say: "The challenger lane reports unavailable — and
authority is unchanged, because the shadow never decides." Continue.

**IF AUDIT RECENT CARDS DON'T INCLUDE YOUR TRACE:** use the search box — type
the trace id (the 6-char RM-XXXXXX from the header chip), press **Search**.
Never hunt by intent id.

**IF THE PAGE FREEZES / API DIES mid-take:** stop the recording. Restart the
API (terminal window 1 — the uvicorn command from §3), refresh tabs, resume
from the start of the current section. Do NOT try to narrate over a dead
backend, and do NOT restart Docker (data must persist on camera).

**IF A SYSTEM NOTIFICATION POPS:** pause recording, dismiss it, resume from
the start of the current row.

**Never, under any circumstance:** hardcode a result, claim a state the screen
did not show, edit the recording to insert a fabricated screen state, or run
`make reset-local` between takes (it is destructive and unnecessary — old
traces coexist by design).

---

## 18. Emergency short version (2:00–2:30)

Same tabs; only TAB 1, TAB 2, TAB 5 used.

| Time | Tab | Action | SAY |
| --- | --- | --- | --- |
| 00:00–00:10 | TAB 1 | Pipeline on screen, presenter mode. | "AI agents can produce perfectly valid payment requests that still violate what the human approved. Protocol validity is not transaction authority." |
| 00:10–00:45 | TAB 2 | Type/paste the §6 mandate → **Compile mandate** → narrate through the wait → **Confirm — grant authority**. | "A human mandate, in plain language. The AI compiles it into explicit constraints — budget, brand, condition, quantity, and no recurring charges. Authority exists only when the human confirms." |
| 00:45–00:55 | TAB 2 | Candidate cards → click **#3 Sony WH-1000XM5** → **Propose checkout** → ALLOW visible. | "The agent searched fifty-two products, three qualified. It proposes the XM5. Deterministic rules say ALLOW — a single-use ticket is issued." |
| 00:55–01:15 | TAB 1 | **Hidden recurring on current** → diff → **Execute current transaction** → STALE_CHECKOUT → point Provider calls 0. | "Now the merchant adds a hidden monthly membership after authorization. Same trace. Authorized: no recurring. Current: monthly. Execution is refused — STALE_CHECKOUT. The ticket no longer matches the transaction. Razorpay: zero calls." |
| 01:15–01:35 | TAB 5 | Open the trace card → timeline → **▶ Play** → **Verify hash chain**. | "The audit ledger holds the whole story — and replay re-renders evidence without re-executing anything. The global chain validates." |
| 01:35–01:55 | TAB 3 | **Run WHY SEMANTIC AI MATTERS demo** → table. | "And when structure alone would allow — a hidden continuing-service term — the semantic model catches it. Ticket not issued. Provider: zero." |
| 01:55–02:10 | TAB 1 | Final pipeline frame. | "The AI proposes. RazorGuard authorizes. The trusted executor executes. The transaction that executes must still be the transaction the human authorized." |

If even this is impossible because the compiler is down: replace the TAB 2 beat
with Mission Control's **Launch new Hidden-membership mission** button (a real
one-click full-pipeline attack with its own fresh trace — verified live), and
say: "This mission launches a pre-authorized demo transaction and mutates it —
watch the pipeline resolve from real events." The rest is unchanged.

---

## 19. Final one-take rehearsal (do immediately before pressing Record)

Numbered, top to bottom, ~5 minutes:

1. [ ] macOS Do-Not-Disturb ON; mic checked (say one test sentence, listen back).
2. [ ] Both terminal windows running and then hidden; screen resolution
       1920×1080; Chrome zoom 100% (Cmd+0); bookmarks bar hidden; devtools closed.
3. [ ] **The compiler gate:** in TAB 2 type `Test compile` → click **Compile
       mandate** → expect a draft or a clean NEEDS_CLARIFICATION within ~60 s.
       ✅ proceed. ❌ wait 10 minutes and retry up to 3 times; if still failing,
       record the EMERGENCY SHORT version (§18) or postpone. (During the
       director's rehearsal the upstream provider flapped; the §17 fallbacks
       exist for this.)
       Then refresh TAB 2 (Cmd+R) to clear the test draft.
4. [ ] TAB 1: click **Run demo preflight** then **Preflight + warm-up
       compiler** → panel shows **REQUIRED SYSTEMS READY**, AI Intent Compiler
       **LIVE REACHABLE**, semantic model **phase3-finetuned-v2**, payment
       environment **RAZORPAY TEST MODE**.
5. [ ] All five tabs open in order (§4), each freshly loaded; TAB 1 in
       presenter mode (RECORDING VIEW badge visible).
6. [ ] The §6 mandate text sits in your clipboard, ready to paste.
7. [ ] Read §16 once more — especially the banned-phrase table.
8. [ ] Say the first sentence of 00:00 out loud, in your recording voice, once.
9. [ ] Press Record. Begin at 00:00.

**Post-take check (before closing anything):** the take includes — the
AUTHORITY GRANTED banner, the diff with recurring Yes ← CHANGED, the
STALE_CHECKOUT status, Provider calls 0 (twice: Mission Control and Audit),
the semantic table with NOT ISSUED / NOT CREATED, and the closing words. If any
is missing, re-record only the missing section and edit — never fabricate.
