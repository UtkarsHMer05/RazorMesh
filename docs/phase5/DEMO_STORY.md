# DEMO_STORY.md — Phase-5 Canonical Judge Story (M003)

**Duration target:** 90–150 seconds. **Alignment:** every step maps to a real backend capability
verified in M001/M002 (PHASE5_JOURNEY_MAP.md). No step contradicts security invariants, frozen
evals, or D-048/D-055/D-056 truth.

## The story

> **Protocol validity is not transaction authority.**
> **The AI proposes. RazorGuard authorizes. The trusted executor executes.**

1. **(0–15s) Problem.** AI agents can produce *technically valid* transactions that no longer
   match what the human approved. Landing → Buyer.
2. **(15–35s) Human mandate + agent.** Judge types the canonical mandate:
   `Buy Sony wireless headphones under ₹5,000 all-in, new only, no subscription.`
   AI Intent Compiler visibly turns language into constraint cards (product, budget, condition,
   recurring, brand, currency). Human confirms authority (AI has none until then).
3. **(35–60s) Attack.** Shopping agent searches/ranks the catalog and proposes a checkout.
   Merchant mutates the offer *after* authorization (hidden recurring membership, ₹499/month).
   Watch the mutation propagate: protocol firewall still PASSES (schema/signature/replay valid),
   deterministic RazorGuard detects `recurring_forbidden` → BLOCK, Semantic Trust Check shows
   contradiction ~99%, conservative fusion keeps BLOCK, ticket WITHHELD, Razorpay calls = 0.
4. **(60–80s) Forensics.** Same trace in Audit: visual timeline, authorization-vs-execution
   diff highlighting the changed recurring term, verified hash chain.
5. **(80–100s) Protocol thesis.** Generate a protocol-valid, signature-valid packet carrying an
   unauthorized amount/quantity (backend test keys only). Protocol PASS. Final BLOCK. Provider 0.
6. **(100–120s) Safe path.** Revert mutation (evidence preserved) or start clean mission.
   Same mandate, clean checkout: ALLOW → ticket issued → Razorpay Test order created exactly once.
7. **(Optional +20s) Governance + breadth.** Model Governance: challenger scored higher on
   normal tests but was REJECTED by the frozen safety gate; AgentPay-X 191/191 campaign.

## Mandatory scenarios (all real, backend-derived outcomes)

| # | Scenario | Entry | Expected (from real pipeline, never hardcoded) |
|---|---|---|---|
| A | **Safe** | Buyer typed mandate → confirm → agent select → propose → pay | ALLOW; ticket; provider order exactly once (Test Mode/mock per settings) |
| B | **Hidden recurring** | Merchant mutation after authorization (or Mission Control preset) | RazorGuard BLOCK (RECURRING_NOT_ALLOWED); semantic contradiction; fusion BLOCK; ticket withheld; provider 0 |
| C | **Protocol-valid / intent-invalid** | Protocols playground or Mission Control preset (D-056 scenario-c generator) | Protocol PASS + final BLOCK + provider 0 |
| D | **Replay** | Replay same ticket/message | Second attempt rejected/idempotent (403 TICKET_EXPIRED / idempotency semantics), no second provider effect |

## Fallbacks / human-only steps

- Completing the Razorpay Test checkout inside the modal is a **human sandbox step** (owner
  completes with test card). The demo shows order creation + launch; narration must never claim
  a *completed payment* unless the owner actually completed it (per RAZORPAY_TEST_ACCEPTANCE.md).
- In mock provider mode (default), provider boundary evidence says "mock provider" — label truthfully.

## Non-goals (never in the story)

- No rerun of frozen evaluations; no v2 activation; no real Razorpay live keys; no claims of
  payment completion by the UI; no scraping of real commerce sites; no provider/model branding
  in the buyer flow (advanced disclosure only).
