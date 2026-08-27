# RazorMesh Phase-4 MCP 2026-07-28 Conformance

> **Status: MODERN MCP 2026-07-28 — all Phase-4 live proofs PASS**

The Phase-4 cross-protocol ingress speaks the **MCP 2026-07-28
modern** per-request envelope exclusively for security-sensitive final
acceptance. The pre-modern `initialize` / `Mcp-Session-Id` path is
retained as a LEGACY compatibility shim and is **not** used for
Phase-4 acceptance.

The legacy path is gated behind the `legacy_initialize` /
`legacy_call_tool` methods on `DeterministicBuyerAgent`. The
`complete_authorized_checkout` MCP tool and the
`/phase4/acceptance/prepare` HTTP route use the modern path.

## A. modern `server/discover` → PASS

`POST /mcp-mount/mcp` with `MCP-Protocol-Version: 2026-07-28`,
`Mcp-Method: server/discover`, and `params._meta` carrying
`io.modelcontextprotocol/protocolVersion` +
`io.modelcontextprotocol/clientCapabilities` returns the modern
`DiscoverResult` with `supportedVersions: ["2026-07-28"]` and
the server's capabilities (tools / prompts / resources / experimental).

No `initialize` handshake is required.

## B. modern `tools/list` WITHOUT initialize → PASS

`POST /mcp-mount/mcp` with the same modern envelope and
`Mcp-Method: tools/list` returns the 14-tool safe surface:

  search_catalog, get_product, get_cart, create_cart, update_cart,
  propose_checkout, get_checkout, evaluate_checkout,
  request_authorization, get_authorization_status,
  complete_authorized_checkout, get_execution_status, get_order,
  get_audit_receipt

No `Mcp-Session-Id` is required or issued.

## C. modern `tools/call` WITHOUT initialize → PASS

`POST /mcp-mount/mcp` with `Mcp-Method: tools/call` and
`Mcp-Name: complete_authorized_checkout` invokes the live Phase-4
cross-protocol ingress (MCP → UCP → AP2 → Firewall → IR →
Consistency MATCH → RazorGuard → ALLOW) without any prior
`initialize` handshake. The tool returns:

```json
{
  "decision": "ALLOW",
  "mcp_version": "2026-07-28",
  "ucp_version": "2026-04-08",
  "ap2_version": "v0.2.0",
  "firewall": "PROTOCOL_PASS",
  "cross_protocol_consistency": "MATCH",
  "razorguard": "ALLOW",
  "tickets_endpoint": "/buyer/execute"
}
```

## D. Mcp-Session-Id → ABSENT

The modern response carries no `Mcp-Session-Id` header. The
`complete_authorized_checkout` tool and all modern responses are
stateless per request.

## E. missing required protocol metadata → deterministic protocol error

A modern request missing `params._meta.io.modelcontextprotocol/protocolVersion`
or `params._meta.io.modelcontextprotocol/clientCapabilities` is rejected
with `code: -32602` and a clear message naming the missing keys. The
same rejection applies to a request that omits the `MCP-Protocol-Version`
header but provides a body version, or vice versa.

## F. unsupported / downgraded version → reject

A modern request with `MCP-Protocol-Version: 2025-99-99` and matching
body version is rejected with `code: -32022` (UNSUPPORTED_PROTOCOL_VERSION)
and the typed `UnsupportedProtocolVersionErrorData` payload listing
`supported: ["2026-07-28"]` and `requested: "2025-99-99"`. The 2025-era
`initialize` handshake is still accepted on the LEGACY path but
returns a 2025-era response and is **not** used for Phase-4 acceptance.

## G. final acceptance via modern MCP

The `complete_authorized_checkout` tool (and the HTTP route
`POST /phase4/acceptance/prepare` that it delegates to) execute
through the MODERN MCP path exclusively. The proof lives in:

  - `services/api/tests/phase4/test_live_ingress_e2e.py` — 13 tests
    including the dedicated
    `test_concurrent_identical_complete_authorized_checkout_exactly_one_effect`
    which proves exactly-once under 20 concurrent identical calls
  - `services/api/src/razormesh_api/protocol/buyer_agent.py` —
    `DeterministicBuyerAgent.run_modern_acceptance` drives the full
    modern chain (discover → tools/list → tools/call) without
    initialize and without `Mcp-Session-Id`

## Legacy compatibility (NOT Phase-4 acceptance)

The pre-modern path is retained for backward compatibility with
agents that still speak the 2025-era `initialize` handshake. It is
LABELED LEGACY and is **not** used for the Phase-4 acceptance run.
The legacy path:

  - returns `Mcp-Session-Id` on `initialize`
  - uses SSE/JSON response framing
  - is gated behind `legacy_initialize` / `legacy_call_tool` on
    `DeterministicBuyerAgent`

The Phase-4 final acceptance always uses the modern path.
