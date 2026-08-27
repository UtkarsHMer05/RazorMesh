"""Deterministic untrusted buyer agent client.

The untrusted buyer agent is the Phase-4 acceptance client. It is:
  - Reproducible: no LLM, no TokenRouter dependency
  - Untrusted: it never holds the Razorpay secret, webhook secret,
    DB credentials, AP2 private keys, the ExecutionTicket private key,
    the payment provider, shell access, or arbitrary networking
  - Bounded: it can only interact with the live MCP surface
    (initialize, tools/list, tools/call)

The agent drives the full Phase-4 cross-protocol ingress:
  1. initialize MCP session
  2. create_cart (agent_id, principal_id)
  3. update_cart (items)
  4. propose_checkout (cart_id, intent_id, items)
  5. get_checkout
  6. evaluate_checkout
  7. request_authorization
  8. complete_authorized_checkout  <-- live Phase-4 chain runs

The agent returns the orchestrator evidence so the test/UI can
correlate every artifact.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib import request as urlrequest

MCP_PROTOCOL_VERSION = "2026-07-28"


@dataclass
class DeterministicBuyerAgent:
    """A reproducible MCP client for the Phase-4 acceptance ingress."""

    mcp_url: str
    agent_id: str
    principal_id: str
    timeout_seconds: float = 30.0

    def _http(
        self,
        *,
        method: str,
        body: dict[str, Any] | None = None,
        session_id: str | None = None,
    ) -> tuple[int, dict[str, Any] | str, dict[str, str]]:
        data = json.dumps(body).encode("utf-8") if body is not None else b""
        req = urlrequest.Request(
            self.mcp_url,
            data=data,
            method=method,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                **({"mcp-session-id": session_id} if session_id else {}),
            },
        )
        with urlrequest.urlopen(req, timeout=self.timeout_seconds) as resp:
            raw = resp.read().decode("utf-8")
            headers = {k: v for (k, v) in resp.headers.items()}
            # MCP Streamable HTTP may return either JSON or SSE.
            if raw.startswith("event:"):
                # Parse SSE: take the last `data:` line and JSON-decode.
                last = ""
                for line in raw.splitlines():
                    if line.startswith("data:"):
                        last = line[len("data:") :].strip()
                parsed: dict[str, Any] | str = (
                    json.loads(last) if last else raw
                )
            else:
                parsed = json.loads(raw) if raw else {}
            return resp.status, parsed, headers

    def initialize(self) -> str:
        body = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "razormesh-buyer-agent", "version": "0.1"},
            },
        }
        status, payload, headers = self._http(method="POST", body=body)
        if status not in (200, 201):
            raise RuntimeError(f"initialize failed: {status} {payload!r}")
        session_id = headers.get("mcp-session-id") or headers.get("Mcp-Session-Id")
        if not session_id:
            raise RuntimeError("initialize returned no session id")
        return session_id

    def call_tool(
        self, session_id: str, name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        body = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
        status, payload, _ = self._http(method="POST", body=body, session_id=session_id)
        if status != 200:
            raise RuntimeError(f"tool {name} failed: {status} {payload!r}")
        result = payload.get("result") if isinstance(payload, dict) else None
        if not isinstance(result, dict):
            raise RuntimeError(f"tool {name} returned no result: {payload!r}")
        content = result.get("content", [])
        if not content:
            raise RuntimeError(f"tool {name} returned empty content")
        text = content[0].get("text", "{}")
        return json.loads(text)

    def run_acceptance(
        self,
        *,
        intent_id: str,
        product_id: str,
        quantity: int = 1,
        currency: str = "INR",
    ) -> dict[str, Any]:
        """Drive the full Phase-4 acceptance ingress via MCP."""
        session_id = self.initialize()
        # Tool 1: create_cart (deterministic id derivation).
        cart = self.call_tool(
            session_id,
            "create_cart",
            {"agent_id": self.agent_id, "principal_id": self.principal_id},
        )
        cart_id = cart.get("cart_id", "")
        # Tool 2: update_cart.
        self.call_tool(
            session_id,
            "update_cart",
            {"cart_id": cart_id, "items": [{"product_id": product_id, "quantity": quantity}]},
        )
        # Tool 3: propose_checkout.
        self.call_tool(
            session_id,
            "propose_checkout",
            {
                "cart_id": cart_id,
                "intent_id": intent_id,
                "items": [{"product_id": product_id, "quantity": quantity}],
            },
        )
        # Tool 4: get_checkout.
        self.call_tool(session_id, "get_checkout", {"checkout_id": "chk_preview"})
        # Tool 5: evaluate_checkout.
        self.call_tool(
            session_id,
            "evaluate_checkout",
            {"checkout_id": "chk_preview", "intent_id": intent_id},
        )
        # Tool 6: request_authorization.
        self.call_tool(session_id, "request_authorization", {"actor": "buyer-agent"})
        # Tool 7: complete_authorized_checkout (the live Phase-4 chain).
        final = self.call_tool(
            session_id,
            "complete_authorized_checkout",
            {
                "intent_id": intent_id,
                "product_id": product_id,
                "quantity": quantity,
                "currency": currency,
            },
        )
        return {
            "session_id": session_id,
            "cart_id": cart_id,
            "final": final,
        }


__all__ = ["MCP_PROTOCOL_VERSION", "DeterministicBuyerAgent"]
