# MOTION_STATE_MACHINE.md — Visual State Contract (M006)

Every visual state is a pure function of a real event/result. **UI animation state is never
authority**; backend/audit evidence is. No visual state exists without backend provenance.

## Node states (per pipeline stage)

```
pending    → no event yet (stage exists in the story, nothing claimed)
active     → stage currently executing (bound to a real in-flight request)
pass       → stage completed with PASS/done evidence
challenge  → stage completed with CHALLENGE evidence
block      → stage completed with BLOCK evidence (authoritative stop reason shown)
failed     → stage errored (truthful failure display)
stopped    → downstream of a BLOCK: not executed (evidence: no event; provenance = blocking stage)
```

## Terminal outcome states

```
ALLOW → ticket ISSUED (ticket event) → provider lifecycle (below)
CHALLENGE → awaiting reauthorization (decision event)
BLOCK → ticket WITHHELD (event) → provider NOT CONTACTED (counter from audit evidence)
```

## Provider/payment lifecycle states (frontend FSM, maps to backend semantics)

```
IDLE → REVALIDATING → READY → CREATING_ORDER → OPENING_CHECKOUT → AWAITING_USER
     → SUCCEEDED | PAYMENT_FAILED | USER_DISMISSED | PAYMENT_ACCEPTED_PENDING_PROVIDER
     → PENDING_RECONCILIATION → SUCCEEDED | EXPIRED
BLOCKED (terminal, distinct from payment failures)
ERROR (infrastructure error, not a payment claim)
```

Transitions are driven **only** by: real request lifecycle (fetch start/finish), backend launch
payload, Razorpay checkout.js events (`payment.failed`, handler success, modal ondismiss), backend
status/callback/webhook responses. Failure → auto-close modal → `PAYMENT_FAILED` + safe reason +
Try Again (fresh server revalidation). Dismissal ≠ failure (no failure claim without a failure
event). Unknown → `PENDING_RECONCILIATION` (never blind retry).

## Motion grammar (what animates and why)

| Motion | Trigger | Meaning |
|---|---|---|
| Packet travels along SVG connector | stage event arrives | real progression through the pipeline |
| Stage node fills/pulses | active | real in-flight request |
| Mutation flash (before→after) | merchant mutation event | exact changed facts |
| Red stop + edge break | BLOCK evidence | packet stops at the *actual* stopping stage — never animates past it |
| Ticket token mint animation | TICKET_ISSUED | authority granted (visual only) |
| WITHHELD stamp | TICKET_WITHHELD | authority not granted |
| Provider call counter increments | audit provider event | real call count |
| Probability bars resolve | semantic event | real model output for this run |
| Convergence lanes → commitment | consistency result | MATCH/MISMATCH computed |
| Hash-chain node walk | chain verification | backend verify result |
| Replay scrub | user replay action | recorded events only (read-only) |

**Forbidden:** fake thinking states, decorative loops, progress not bound to a request,
animation continuing past the stopping stage, any motion implying authority the backend didn't grant.

## Controls

- Play/pause/speed/replay for long flows (replay = recorded events, zero side effects).
- `prefers-reduced-motion`: all keyframe/transition animations collapse to instant state changes
  (states + labels remain fully readable — motion is explanatory, never load-bearing).
