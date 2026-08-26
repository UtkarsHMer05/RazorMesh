# Phase 4 Protocol Version Matrix (frozen 2026-08-27)

Live-verified against official sources. Every pin is a stable, named release
available on the official repository. No `main`-tip dependencies. No
fabricated conformance claims.

## MCP — Model Context Protocol

| Field | Value | Source |
|---|---|---|
| **Final spec revision** | `2026-07-28` | https://blog.modelcontextprotocol.io/posts/2026-07-28/ (final publication 2026-07-28) |
| **Prior revision** | `2025-11-25` (replaces) | https://modelcontextprotocol.io/specification/2026-07-28/changelog |
| **Status** | Current, Final | https://modelcontextprotocol.io/docs/learn/versioning |
| **Stateless core** | YES — no `initialize`/`notifications/initialized`/`Mcp-Session-Id` | SEP-2567 (https://modelcontextprotocol.io/specification/2026-07-28/changelog) |
| **Modern routing headers** | `Mcp-Method`, `Mcp-Name` | same |
| **Authorization hardening** | RFC 9207 issuer validation; CIMD over DCR | same |
| **Extensions** | MCP Apps, Tasks, Enterprise Managed Authorization (EMA) | https://modelcontextprotocol.io/docs |
| **Deprecations** | legacy SSE, roots, sampling, MCP protocol logging; ≥12 month window | https://modelcontextprotocol.io/community/feature-lifecycle |
| **Python SDK** | `mcp` v2.1.0 (PyPI, released 2026-08-24) | https://pypi.org/project/mcp/ |
| **SDK source commit** | `4d6f87e8d2df8b161bd279cecdb76c988d74bc8a` (v2.1.0) | https://github.com/modelcontextprotocol/python-sdk |
| **Wheel SHA-256** | `b8acaed6ca4b9376801377463e44246395749363b1c34467ec6243a50be5ed28` | PyPI |
| **License** | MIT | repo `LICENSE` |

## UCP — Universal Commerce Protocol

| Field | Value | Source |
|---|---|---|
| **Latest released version** | `2026-04-08` (released 2026-04-09) | https://github.com/Universal-Commerce-Protocol/ucp/releases/tag/v2026-04-08 |
| **Resolution of 2026-08-25 ambiguity** | The unversioned docs emit `2026-08-25`, but the official release tags and announcements still list `2026-04-08` as the latest explicitly announced release. **Pin to `2026-04-08`**; treat any `2026-08-25` references as draft/forward-compat only, never "stable conformance". | https://ucp.dev/documentation/announcements/ + repo tags |
| **Prior version** | `2026-01-23` | https://ucpchecker.com/protocol-tracker |
| **Discovery** | `/.well-known/ucp` profile; REST + MCP + A2A + Embedded transports | https://ucp.dev/2026-04-08/specification/overview/ |
| **Capabilities in 2026-04-08** | shopping.checkout, shopping.cart, shopping.catalog_search, shopping.catalog_lookup, shopping.order, fulfillment, discounts extension, AP2 mandates extension, buyer consent extension | repo changelog + https://dev.to/benjifisher/ucp-v2026-04-08-spec-update-39l2 |
| **Money** | integer minor units; `signed_amount.json` for totals | spec + changelog |
| **Signing** | RFC 9421 HTTP Message Signatures + RFC 9530 Content-Digest | https://ucp.dev/specification/signatures/ |
| **License** | Apache-2.0 | https://github.com/Universal-Commerce-Protocol/ucp/blob/main/LICENSE |
| **Conformance claim scope** | subset: profile/discovery + Catalog search/lookup + Cart + Checkout create/get/update/complete + Order get + UCP-over-MCP binding + signed event fixture path | master prompt §13, §4 |

## AP2 — Agent Payments Protocol

| Field | Value | Source |
|---|---|---|
| **Latest released version** | `v0.2.0` (released 2026-04-28) | https://github.com/google-agentic-commerce/AP2/releases |
| **Source commit** | `b4587ac1d055888a73b4b21750973cffba961793` (tag v0.2.0) | https://github.com/google-agentic-commerce/AP2 |
| **FIDO donation** | 2026-04-28 (Google → FIDO Alliance) | https://blog.google/products-and-platforms/platforms/google-pay/agent-payments-protocol-fido-alliance/ |
| **Mandate types** | Checkout Mandate (open/closed), Payment Mandate (open/closed), Receipts | https://ap2-protocol.org/ap2/specification/ |
| **Key/crypto rule** | Checkout JWT binding uses merchant-signed JWT; checkout-hash security requires a **nondeterministic** signature such as ECDSA — NOT Ed25519. RazorMesh's existing Ed25519 ExecutionTicket key is **separate** and must not be conflated. | https://ap2-protocol.org/ap2/checkout_mandate/ + master prompt §8 |
| **vct** | exact `vct` version matching required; unknown constraints fail verification | https://ap2-protocol.org/ap2/agent_authorization/ |
| **Authorization framework** | SD-JWT VC, key-binding, `cnf`, open vs closed mandates, PoP for HNP autonomous | https://ap2-protocol.org/ap2/agent_authorization/ |
| **License** | Apache-2.0 | repo `LICENSE` |
| **Local role boundaries** | RazorMesh = merchant-side verifier for Checkout Mandates + integration layer for Payment Mandate evidence; Trusted Surface simulator for local test flows. **No** real Credential Provider / network claim. | master prompt §14 |

## ACP — Agentic Commerce Protocol

| Field | Value | Source |
|---|---|---|
| **Latest stable release** | `2026-04-17` (spec; supersedes `2026-01-30`) | https://docs.stripe.com/agentic-commerce/acp + repo `changelog/` |
| **Target per master prompt** | `2026-01-30` (capability negotiation + payment handlers + extensions) | master prompt §16 + https://www.agenticcommerce.dev/docs/changelog |
| **Pinned** | **`2026-01-30`** per master prompt; the `2026-04-17` follow-up is a small add-on that does not change Phase-4 scope | M08 decision |
| **Capability negotiation** | single `capabilities` object; intersection semantics | https://github.com/agentic-commerce-protocol/agentic-commerce-protocol/blob/main/changelog/2026-01-30.md |
| **Payment handlers** | structured `capabilities.payment.handlers[]` with `psp`, `requires_delegate_payment`, `requires_pci_compliance` | same |
| **Lifecycle** | not-ready → ready → in-progress → completed / canceled | https://www.agenticcommerce.dev/docs/concepts/architecture |
| **License** | Apache-2.0 | repo `LICENSE` |
| **RazorMesh custom handler** | `io.razormesh.razorpay.test_checkout` (test mode only; not Delegate Payment; not PCI-credential relay) | master prompt §16, §42 |
| **NOT claimed** | "ACP Delegate Payment supported" — Razorpay does not implement ACP Delegate Payment or Stripe token semantics | master prompt §1, §16 |

## A2A — Agent-to-Agent Protocol

| Field | Value | Source |
|---|---|---|
| **Latest released version** | `v1.0.1` (released 2026-05-26) | https://github.com/a2aproject/A2A/releases |
| **Source commit** | `3303592588e388e62e0f69f701af531d2f4e3991` (v1.0.1) | same |
| **Prior line** | `v1.0.0` (2026-03-12) | same |
| **Spec URL** | https://a2a-protocol.org/v1.0.0/specification | https://a2a-protocol.org/latest/specification |
| **Well-known** | `/.well-known/agent-card.json` | spec §14.3 |
| **Bindings** | JSON-RPC, gRPC, HTTP+JSON | spec |
| **Headers** | `A2A-Version`, `A2A-Extensions` | spec |
| **Content-Type** | `application/a2a+json` | spec |
| **License** | Apache-2.0 | repo `LICENSE` |
| **Phase-4 scope** | compatibility slice only — Agent Card/profile fixture, UCP extension metadata, DataPart mapping for UCP checkout, `messageId` ↔ idempotency, AP2 evidence refs | master prompt §17, §44 |

## Cross-protocol rules (from master prompt §1, §8, §22)

- RazorMesh pins stable, named releases only. No `main`/`HEAD` dependencies.
- RazorMesh's existing Ed25519 ExecutionTicket key is **not** reused for AP2
  checkout JWT binding (which requires ECDSA per AP2 v0.2).
- No real AP2 Credential Provider / network claim.
- No ACP Delegate Payment claim for Razorpay.
- UCP `2026-04-08` is the only UCP version for which Phase 4 claims subset
  conformance; any newer docs/feature references are compatibility fixtures
  only.
- A2A scope is a compatibility slice, not full conformance.
- No Phase-5 work, no real payments, no live Razorpay.
- One local commit per milestone where practical; never push.
