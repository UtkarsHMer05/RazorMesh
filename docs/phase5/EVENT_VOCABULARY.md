# EVENT_VOCABULARY.md — Judge-Facing Event Model (M005)

Normalized, privacy-safe events **projected from canonical audit/domain state**. The projection
never invents events; if a stage has no backend evidence, the stage stays `absent` (never faked).

## Event envelope

```json
{
  "seq": 1069,                       // authoritative audit seq when available
  "ts": "2026-08-30T18:04:59Z",      // authoritative timestamp
  "stage": "razorguard",             // pipeline stage id (below)
  "kind": "decision.blocked",        // event kind (below)
  "title": "Deterministic RazorGuard decision",
  "detail": "Recurring terms are forbidden by the confirmed mandate.",
  "status": "BLOCK",                 // PASS|CHALLENGE|BLOCK|DONE|FAILED|INFO|WITHHELD|...
  "source": "razorguard",           // originating module (from audit actor)
  "ids": {"intent_id": "intent_...", "checkout_id": "chk_..."},  // safe ids only
  "evidence": { /* stage-specific safe payload, see table */ }
}
```

## Stage ids and kinds (complete story coverage)

| stage | kind(s) | Projected from (authoritative source) |
|---|---|---|
| human | `mandate.compiled`, `mandate.confirmed`, `mandate.rejected` | confirmation-service audit events (INTENT_COMPILED / HUMAN_INTENT_CONFIRMED / reject); evidence: hard constraints (safe projection), explicit vs inferred flags |
| agent | `search.started`, `search.completed`, `candidate.proposed` | Phase-5 search API execution (real fetch/filter/rank counts from catalog) |
| merchant | `offer.mutated`, `offer.reverted` | Phase-5 merchant sandbox events (real demo mutations; before/after values) |
| protocol | `packet.sent`, `packet.checks`, `firewall.decided` | phase4 acceptance evidence (versions, sig/digest status, idempotency, firewall verdict) |
| ir | `ir.normalized`, `ir.commitment` | AgentCommerceIR evidence (schema, total, commitment hash prefix) |
| consistency | `consistency.match`, `consistency.mismatch` | cross-protocol consistency engine results |
| razorguard | `decision.allowed`, `decision.challenged`, `decision.blocked` | DECISION_RECORDED audit event + reason codes |
| semantic | `semantic.checked` | SEMANTIC_VERIFICATION_RUN audit event (probabilities, verdict, policy version — **no model/provider branding in normal flow**) |
| fusion | `fusion.decided` | POLICY_FUSION_DECIDED audit event (deterministic + semantic + final) |
| ticket | `ticket.issued`, `ticket.withheld` | TICKET_ISSUED / TICKET_WITHHELD audit events (safe ticket id, amount; never signature material) |
| execution | `attempt.started` | executor/audit events (attempt id) |
| provider | `provider.contacting`, `provider.order_created`, `provider.rejected`, `provider.unknown`, `provider.not_contacted` | RAZORPAY_* audit events + executor state (call counts derived from audit evidence only) |
| reconciliation | `reconciliation.required`, `reconciliation.run`, `callback.verified`, `webhook.ingested` | RAZORPAY_CALLBACK_VERIFIED / WEBHOOK_INGESTED / RECONCILIATION_RUN events |
| payment | `payment.state` | reducer state projection (IDLE…SUCCEEDED per M0095 state machine) |
| audit | `audit.chained` | seq/hash head info (tamper-evident chain) |
| replay | `replay.rejected` | ticket replay/idempotency rejections (403 TICKET_EXPIRED etc.) |

## Privacy rules (hard)

- No secrets, no key material, no signatures/token bodies, no raw cards, no row-level
  human-gold/review data, no internal agent prompts, no reviewer endpoints.
- Semantic evidence exposes probabilities + verdict + policy version only; model file names and
  provider branding go to the collapsed Advanced/Evidence disclosure (or omitted in normal flow).
- Merchant hostile text is transported as clearly-marked **untrusted content** and rendered as
  inert data (escaped, never interpreted, never styled as system text).
- Hashes shown truncated with full value available under advanced disclosure.

## Order + determinism

Events are ordered by audit `seq` (authoritative append order). For Phase-5 non-audit events
(agent search, merchant mutations) the projector assigns monotonic sub-seq from the same
ledger append (these flows write real audit events too, so ordering remains total).
