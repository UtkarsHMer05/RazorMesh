# TRACE_CONTRACT.md — Shared Live Trace Contract (M004)

**Principle:** the display trace is a *mapping*, never a second authority system. Durable
Postgres state (intents, checkouts, decisions, tickets, attempts, audit events) remains the only
financial truth. The trace registry is a projection + linkage table.

## Display trace

- Format: `RM-` + 6 uppercase base32 chars (Crockford alphabet, no I/L/O/U to avoid ambiguity):
  e.g. `RM-84C91A`.
- Generated server-side only, from `secrets`-quality entropy (OS randomness), checked against
  existing registry rows for collision (regenerate on collision; 32^6 ≈ 1B space, birthday-safe
  for demo scale).
- Owned by the backend; frontend never invents trace ids.

## Mapping to existing authoritative IDs

| Artifact | Existing ID kind | Link mechanism |
|---|---|---|
| Intent (fixture or compiled) | `intent_...` (ULID) | trace row created at intent creation; `intent_id` column |
| Intent draft (compiled mandate) | draft id | best-effort link via audit event lineage (compiled→confirmed intent) |
| Checkout | `chk_...` | link via audit event `checkout_id` |
| Decision | decision id / audit seq | via audit event |
| Ticket | `tk_...` | via audit event `ticket_id` |
| Protocol run | `acc-...` (in-memory) + audit events | via audit events on the same intent; run registry also linked by intent_id |
| Execution attempt | attempt id | via audit events |
| Razorpay order | `order_...` | via audit event payload (safe subset only) |
| Audit chain | event seq range | all events whose `intent_id` maps to the trace |

**Resolution direction:** trace → intent is authoritative; all other artifacts resolve through
existing audit-event fields keyed by `intent_id`/`checkout_id`. No artifact ever resolves *backwards*
to rewrite an intent's trace (immutable binding).

## Ownership + collision rules

- One intent belongs to exactly one trace (1:1). A trace with no confirmed activity is a
  "draft-only" trace (searchable, harmless).
- Fixture intents (`POST /buyer/fixture-intent`), compiled intents (`/buyer/intent-drafts/compile`
  + confirm), phase4 acceptance intents, and security-lab scenario intents each create/link a trace
  the moment an `intent_id` is known. Existing pre-Phase-5 intents (created before the registry)
  resolve lazily: a trace is minted on first lookup and cached in the registry (migration-safe;
  old evidence is never rewritten — the audit chain is untouched; only the projection table links).
- Deep links: `/page?trace=RM-84C91A` — validated server-side; invalid → clean 404/empty state.
- Display trace contains no secrets; it is a random public label, unguessable enough for a demo,
  and never used as a security token.

## Trace summary read model (feeds M011)

```
trace_id, created_at, updated_at,
intent_id, draft_id?, checkout_id?, run_id?,
state: MANDATE_DRAFT|MANDATE_CONFIRMED|SEARCHING|PROPOSED|DECIDED|EXECUTING|SETTLED|WITHHELD|FAILED|PENDING_RECONCILIATION (derived from events, never stored as authority),
final_decision?, provider_contacted: bool, provider_call_count: int (derived from audit events),
amount_minor?, currency?, merchant_name?, headline? (safe display strings)
```

Derivation is a pure function of audit events; the registry caches the mapping only
(trace_id ↔ intent_id ↔ first-class ids + summary cache invalidated on new events).
