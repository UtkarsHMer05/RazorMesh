# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Next.js 16.3.2 (App Router, static prerender) + React 19.2.8 + TypeScript 5.9.3 + CSS Modules. ESLint 9.39.5 (dev-only compatibility pin). Vitest 4.1.11 + Testing Library + Playwright 1.62.1. Components: `@razorpay/blade` (Blade-first rule from DESIGN.md §3) where current compatibility permits; CSS Modules for everything else. No Tailwind, no UI framework other than Blade.

## Users

**Primary:** Devs and trust-engineers evaluating RazorMesh as the trust layer beneath an AI agent that spends money. They arrive at the prototype to inspect the runtime integrity property, not to shop. They want to see the audit trail, the BLOCK/CHALLENGE reasoning, the ticket lifecycle, the Security Lab scenarios, the mock provider, and the evidence chain. They will click through every defense, run the security lab, replay an attempt, and read the audit dashboard.

**Secondary (same prototype, different lens):** Reviewers and hackathon judges who want a calm, plain-language confirmation UI demonstrating what an end-buyer would see if an AI agent proposed a payment. The Buyer surface serves both audiences from the same code.

**Tertiary (proof-only, not a user of the prototype):** Merchants receiving the payments and end-buyers using the agentic-commerce app. They are not the primary user; the Merchant page exists to prove the data authority boundary, not to ship a merchant product.

## Product Purpose

Prove that a financial action may execute only when the exact current transaction remains within the human-confirmed authorization and the trusted execution context. Success means a reviewer can inspect the runtime and confirm that no path exists from "AI proposed" to "money moved" without the authorization state having been confirmed by a human, signed, revalidated at execution, and recorded in the evidence ledger.

## Positioning

The intent-to-execution integrity guarantee, made inspectable. The AI proposes; RazorGuard authorizes; the trusted executor executes. Neighbouring trust products either skip the human confirmation step (the agent acts alone) or skip the runtime NLI verifier (the agent acts on semantic plausibility alone). RazorMesh proves both can be in the loop at once, and surfaces the proof in a UI a non-author can click through. The unique claim is not the depth of any single defense; it is that the defenses compose, and the composition is observable.

## Operating Context

The prototype is run locally (`pnpm dev` in `apps/web`) against a local Postgres (Docker) and a local Razorpay mock. A reviewer opens the home page, reads the trust-core banner, and follows the Buyer / Merchant / Security Lab / Audit headings. The Security Lab runs server-side scenarios; the Audit dashboard is a read-only timeline with a tamper-simulation toggle. No external network is required for the prototype to demonstrate the property; the only secrets are local and gitignored. The product must be labeled as an unofficial hackathon prototype wherever the Razorpay context is implied.

## Capabilities and Constraints

**Capabilities (confirmed):**
- IntentDraft proposal + human confirmation flow (DRAFT / NEEDS_CLARIFICATION / CONFIRMED / REJECTED).
- Conservative policy fusion: semantics can only STRICTEN deterministic RazorGuard decisions (D-039).
- Local DeBERTa NLI verifier (fine-tuned cross-encoder) with fail-closed CHALLENGE on any model error.
- Evidence ledger with JCS canonical hash chain and tamper-simulation.
- Security Lab with 5 defensive scenarios run server-side.
- 14-pair benchmark and ablation study (rules-only / never-fires / full fusion).

**Constraints (durable, must be preserved):**
- **Blade-first components** where current compatibility permits (DESIGN.md §3). Research-backed from public Razorpay sources only.
- **No Razorpay endorsement implied.** Prototype labeled as unofficial hackathon wherever the Razorpay context is shown.
- **No invented brand tokens.** No "official Razorpay font" or private brand token unless publicly verified (DESIGN.md §2).
- **Security invariants P3-S01..S20 + P2-S01..S24 are product constraints, not just engineering constraints.** UI must respect them and the design must communicate them: no client-side secret, money is integer minor units, BLOCKED never executes, ambiguous provider outcomes are never blindly retried, conservative fusion only tightens, raw human text never persisted.
- **Page inventory is durable:** Home, Buyer, Merchant, Security Lab, Audit. Future redesigns can change visual language, not surface topology, without explicit approval.
- **Trust-core banner** on the home page is a non-negotiable: it is the first thing a reviewer sees and the rest of the app must reinforce it.

**Stack decisions deferred (no product constraint yet):**
- The specific fonts beyond Blade's default; the precise colour-palette derivation from Blade tokens; the motion language. These will be set in `/impeccable document` (record the incumbent) or in a `/impeccable craft <surface>` call (build a new surface with ambition).

## Brand Commitments

**Name:** RazorMesh Trust (also: "RazorMesh"). The "Razor" prefix is a deliberate signal of the Razorpay context; the design must respect that lineage without claiming endorsement.

**Voice:** Calm, precise, technical, never urgent unless the underlying state actually is. Warnings are visible, not loud. The voice in copy and in microcopy must match the voice in the security lab output: "this attempt was blocked because …", not "you cannot do this".

**Assets on hand:**
- Blade design system (open-source; pinned compatible version).
- A small set of placeholder product images (50 synthetic products seeded into the catalog) sufficient for the Buyer / Merchant flows but explicitly synthetic.

**Personality:** Trust through transparency. The UI is a window onto the runtime, not a smoothing layer over it.

## Evidence on Hand

**What is real:**
- Full Phase-1/2/3 test batteries: 522 backend tests (pytest), 12 frontend tests (vitest), 5 Playwright E2E, security-check 0 findings, ruff/mypy strict both clean.
- 14-pair benchmark: F1 = 1.0; Phase-3 fine-tuned NLI test 127 rows block P=0.977 R=1.000 F1=0.989; Phase-3 human-gold heldout 79 cards 0.937 acc.
- Evidence-ledger hash chain verifiable from the Audit page; tamper-simulation toggle.
- `docs/PHASE3_COMPLETION_REPORT.md` and `docs/PHASE3_NLI_FINETUNE_EVAL.md` are the authoritative numbers.

**What is fabricated by the prototype (must not be presented as real):**
- The 50 seeded products are synthetic. Catalog data is real-to-the-demo, not real.
- The mock Razorpay provider is mocked; no real money moves. The UI must keep this obvious.
- The TokenRouter model (Qwen3.8 via the free tier) is a free hosted model; the prototype does not own it.

**What future work must not fabricate:**
- Customer logos, testimonials, benchmarks against named competitors, deployment claims, pricing, or licensing.
- Any "official Razorpay" font, glyph, or private brand token.

## Product Principles

1. **The AI proposes. RazorGuard authorizes. The executor executes.** Every UI surface should reinforce this order; no surface should let a user act as if the AI has already decided.
2. **Calm warnings, not loud ones.** A BLOCK state is shown with a precise reason and the evidence behind it, not with red, exclamation, and a modal. The Security Lab output is the template.
3. **Inspectability is the product.** If a reviewer cannot click something and see the underlying state, the design has hidden something that should be visible.
4. **No client-side secrets, ever.** The browser is a view; authority lives in the backend. The design must show this boundary, not blur it.
5. **Tokens over recipes.** A redesign changes a Blade token, not a per-page stylesheet. Surface topology is stable; visual language is iterated.

## Accessibility & Inclusion

WCAG 2.1 AA is the floor. The Security Lab output and the Audit dashboard are table-heavy; the design must keep them navigable by keyboard, with semantic markup and reasonable contrast. The trust-core banner is the most-read surface; it must work in a screen reader before it works in a screenshot. No animation conveys state alone; motion accompanies, never replaces, the underlying textual change. Colour is never the only signal of BLOCK vs CHALLENGE vs ALLOW — every state also carries an icon and a textual reason.
