# VIDEO_STORYBOARD.md — Phase-5 Submission Video (M115)

Duration target: 90–150 s (plus optional governance/campaign extension). Every
frame corresponds to a real, reproducible page state proven in the Phase-5
milestones. No invented claims; the fallback for the human-only Razorpay
sandbox step is explicit.

Recording setup: 1920×1080, Mission Control presenter mode ON, reduced-motion
OFF (animations are the story), Chrome.

## 0–15 s — Problem (Mission Control, no mission yet)

- Open http://localhost:3000/mission-control (presenter mode).
- Pipeline visible, all nodes pending. Narrate:
  > "AI agents can create technically valid transactions that no longer match
  > what a human approved."
- Cut to the thesis banner text on Protocols (or overlay the same words):
  > "Protocol validity is not transaction authority."

## 15–35 s — Human mandate + agent (Buyer)

- Open /buyer. Type the canonical mandate:
  `Buy Sony WH-1000XM5 wireless headphones under ₹5,000 all-in total, new condition only, one-time purchase with no subscription.`
- Click **Compile mandate** — watch the real stage checklist (Reading →
  Extracting → Validating → Draft ready), then the constraint cards appear
  (Budget ≤ ₹5,000 EXPLICIT · Brand Sony · Recurring Forbidden · …).
- Click **Confirm — grant authority** → AUTHORITY GRANTED banner + mission
  trace id appears (e.g. RM-XXXXXX).
- The Shopping Agent auto-runs: "52 catalog products inspected · 3 eligible ·
  49 rejected" — real counts. Show the ranked candidates and "Why the agent
  chose this".

## 35–60 s — Attack (Mission Control hidden-membership)

- Open /mission-control → click **Hidden membership attack**.
- Watch the nodes resolve from real events: protocol/firewall **PASS**
  (the packet is protocol-valid!) → RazorGuard **BLOCK** (recurring not
  authorized) → Semantic contradiction ~100% → Fusion **BLOCK** → Ticket
  WITHHELD. NOTE: the protocol layer PASSES here — the stop is an
  intent/authority stop, not a protocol stop.
- The banner lands the thesis: "The packet stopped at razorguard — Razorpay
  was never contacted." Provider calls: 0 (evidence sidebar). The stopping
  node is razorguard (the decision boundary), not the protocol gateway.
- Optional beat: the same mutation applied by hand in /merchant (hidden
  membership preset) with the authorized-vs-current diff (read the numbers
  from the live diff table; the authorized side is the immutable proposal
  baseline, never the catalog).

## 60–80 s — Forensics (Audit)

- Open /audit. Recent missions cards → click the attack's trace (or search it).
- Show the visual timeline, then **Authorization vs current** — the
  comprehensive diff (quantity, price, fees, recurring… whichever drifted)
  that explains the block.
- Click **▶ Play** on the read-only replay: the events walk one by one
  (0.5x/1x/2x), the current-event indicator moves, and after the full replay
  the provider-call count and event count are UNCHANGED (it never
  re-executes).
- Show the trace's own hash-chain nodes (each event links to the previous
  hash) — where tamper would break THIS trace — then click **Verify hash
  chain** for the global "CHAIN VALID over N events".

## 80–100 s — Protocol thesis (Mission Control)

- Back on /mission-control → **Protocol-valid / intent-invalid**.
- Nodes: protocol passes the gateway, the decision layer blocks. Banner:
  stopped at the boundary; provider 0.
- Optional deeper beat: /protocols playground — pick MCP, mutation "Amount
  +1": all protocol checks PASS, commitment MISMATCH. Then cross-protocol
  view: diverge AP2 — only that lane mismatches.

## 100–120 s — Safe path (Buyer)

- /buyer → "Start new mission" (or reuse) → run the mandate flow → the XM5
  candidate → **Propose checkout** → ALLOW → ticket ISSUED.
- Show the provider-boundary card flip to "Razorpay contacted" on execution
  in Razorpay Test Mode — order created exactly once.
- HUMAN-ONLY STEP (fallback): completing the payment inside the Razorpay
  modal requires the owner's test card; the video stops at order creation and
  narrates: "Razorpay Test order created exactly once; payment completion is
  the owner's sandbox step." (If the owner completed a payment, show the
  CAPTURED/PAID state as recorded evidence.)

## Optional +20 s — Governance + breadth

- /governance: ACTIVE safety model vs the REJECTED challenger table (human
  gold 2→7 WORSENED; test macro-F1 0.7367→0.9752 "improved — not enough").
  Then the challenger shadow: type the delivery-address contradiction
  ("The parcel will be routed through a local pickup point.") and run it —
  the REAL fine-tuned v2 checkpoint says CHALLENGE (p C≈0.05) while the
  ACTIVE model says BLOCK (p C≈0.999). Narrate: "The challenger disagrees
  with the active model here — the exact tau-band gap that got it rejected
  — and it is IGNORED for authority. Never fusion, never tickets, never
  the provider."
- /security-lab: Run red-team campaign — the 191-scenario adversarial
  policy benchmark: 37 safe @ 100% pass, 154 attacks @ 100% block
  (BLOCK or CHALLENGE), 0 false allows, 0 false blocks. Exactly-once and
  provider-execution behavior is proven by SEPARATE acceptance tests
  (order created exactly once; attack chains 0 provider calls) — the
  benchmark itself is a policy engine, not live provider traffic.
- Close: "Safety ships over headline accuracy. The AI proposes. RazorGuard
  authorizes. The trusted executor executes."

## Fallback / honesty rules

- No narration may claim a completed payment unless the owner actually
  completed one in the sandbox.
- The mock-provider mode banner must not be cropped out (truthful labeling).
- Numbers on screen are backend-derived; the video never adds overlays with
  metrics that the pages do not show.
- If the AI compile takes >20 s cold, pre-warm the backend before recording
  (first compile loads the DeBERTa runtime).
