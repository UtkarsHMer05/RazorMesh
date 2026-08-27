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
import threading
from dataclasses import dataclass
from typing import Any
from urllib import request as urlrequest

# Process-local monotonic counter for JSON-RPC ids.
_ID_LOCK = threading.Lock()
_ID_COUNTER = 0


def _next_id() -> int:
    global _ID_COUNTER
    with _ID_LOCK:
        _ID_COUNTER += 1
        return _ID_COUNTER


def _parse_json_or_sse(raw: str) -> dict[str, Any]:
    """Parse a JSON or SSE Streamable-HTTP reply into a JSON-RPC object."""
    if not raw:
        return {}
    if raw.startswith("event:"):
        last = ""
        for line in raw.splitlines():
            if line.startswith("data:"):
                last = line[len("data:") :].strip()
        raw = last or raw
    try:
        parsed = json.loads(raw)
    except (ValueError, RecursionError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _assert_no_session_id(headers: dict[str, str]) -> None:
    """The modern envelope is sessionless: no session header may appear."""
    for name in headers:
        if "session-id" in name.lower():
            raise RuntimeError(f"modern response must not carry a session id: {name!r}")


def _result_object(payload: dict[str, Any]) -> dict[str, Any]:
    """Return the JSON-RPC ``result`` object, normalising a bare result body."""
    result = payload.get("result", payload)
    return dict(result) if isinstance(result, dict) else {}


def _tool_payload(name: str, payload: dict[str, Any], *, allow_empty: bool) -> dict[str, Any]:
    """Decode the first text content block of a tools/call result."""
    result = _result_object(payload)
    content = result.get("content", [])
    if not isinstance(content, list) or not content:
        if allow_empty:
            return {}
        raise RuntimeError(f"tool {name} returned no content: {payload!r}")
    first = content[0]
    text = first.get("text", "{}") if isinstance(first, dict) else "{}"
    decoded = json.loads(text)
    if not isinstance(decoded, dict):
        raise RuntimeError(f"tool {name} returned non-object content")
    return decoded


MCP_PROTOCOL_VERSION = "2026-07-28"
MCP_PROTOCOL_META = {
    "io.modelcontextprotocol/protocolVersion": MCP_PROTOCOL_VERSION,
    "io.modelcontextprotocol/clientCapabilities": {},
}
# Routing headers required by the MCP 2026-07-28 modern per-request
# envelope. The server rejects any modern request that omits these.
MCP_MODERN_VERSION_HEADER = "MCP-Protocol-Version"
MCP_MODERN_METHOD_HEADER = "Mcp-Method"
MCP_MODERN_NAME_HEADER = "Mcp-Name"


@dataclass
class DeterministicBuyerAgent:
    """A reproducible MCP client for the Phase-4 acceptance ingress.

    The agent speaks the MCP 2026-07-28 **modern** per-request
    envelope by default. It is sessionless (no ``Mcp-Session-Id``),
    performs no ``initialize`` handshake, and carries the required
    protocol metadata in ``params._meta`` and the
    ``MCP-Protocol-Version`` / ``Mcp-Method`` / ``Mcp-Name``
    routing headers. The legacy ``initialize`` path is retained as
    ``legacy_initialize`` for tests that still exercise the
    pre-modern compatibility shim; the Phase-4 acceptance run
    uses the modern path exclusively.
    """

    mcp_url: str
    agent_id: str
    principal_id: str
    timeout_seconds: float = 30.0

    def _post(
        self,
        body: dict[str, Any],
        extra_headers: dict[str, str],
    ) -> tuple[int, dict[str, Any], dict[str, str]]:
        """POST one JSON-RPC envelope and parse the JSON/SSE reply."""
        request = urlrequest.Request(
            self.mcp_url,
            data=json.dumps(body).encode("utf-8"),
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                **extra_headers,
            },
        )
        with urlrequest.urlopen(request, timeout=self.timeout_seconds) as resp:
            raw = resp.read().decode("utf-8")
            headers = {key: value for key, value in resp.headers.items()}
            return resp.status, _parse_json_or_sse(raw), headers

    def _http_modern(
        self,
        *,
        method: str,
        params: dict[str, Any],
        mcp_name: str | None = None,
    ) -> tuple[int, dict[str, Any], dict[str, str]]:
        """Send a single MCP 2026-07-28 modern per-request envelope.

        This is the **only** path the agent uses for the Phase-4
        acceptance run. It is sessionless (no ``Mcp-Session-Id``),
        requires no ``initialize`` handshake, and carries the
        required protocol metadata in ``params._meta`` plus the
        ``MCP-Protocol-Version`` + ``Mcp-Method`` routing headers.
        """
        body: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": _next_id(),
            "method": method,
            "params": {
                **params,
                "_meta": {**MCP_PROTOCOL_META, **params.get("_meta", {})},
            },
        }
        headers = {
            MCP_MODERN_VERSION_HEADER: MCP_PROTOCOL_VERSION,
            MCP_MODERN_METHOD_HEADER: method,
            **({MCP_MODERN_NAME_HEADER: mcp_name} if mcp_name else {}),
        }
        return self._post(body, headers)

    def discover(self) -> dict[str, Any]:
        """Send a modern ``server/discover`` (no session, no initialize)."""
        status, payload, headers = self._http_modern(method="server/discover", params={})
        if status != 200:
            raise RuntimeError(f"server/discover failed: {status} {payload!r}")
        _assert_no_session_id(headers)
        return _result_object(payload)

    def list_tools_modern(self) -> list[dict[str, Any]]:
        """Modern ``tools/list`` without initialize."""
        status, payload, headers = self._http_modern(method="tools/list", params={})
        if status != 200:
            raise RuntimeError(f"tools/list failed: {status} {payload!r}")
        _assert_no_session_id(headers)
        tools = _result_object(payload).get("tools", [])
        if not isinstance(tools, list):
            raise RuntimeError(f"tools/list returned non-list tools: {tools!r}")
        return [dict(tool) for tool in tools if isinstance(tool, dict)]

    def call_tool_modern(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Modern ``tools/call`` without initialize.

        The MCP modern routing contract requires the tool name to also
        appear in the ``Mcp-Name`` header for name-bearing methods.
        """
        status, payload, headers = self._http_modern(
            method="tools/call",
            params={"name": name, "arguments": arguments},
            mcp_name=name,
        )
        if status != 200:
            raise RuntimeError(f"tools/call {name} failed: {status} {payload!r}")
        _assert_no_session_id(headers)
        return _tool_payload(name, payload, allow_empty=True)

    def initialize(self) -> str:
        """LEGACY-compat wrapper around :meth:`legacy_initialize`."""
        return self.legacy_initialize()

    def call_tool(self, session_id: str, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """LEGACY-compat wrapper around :meth:`legacy_call_tool`."""
        return self.legacy_call_tool(session_id, name, arguments)

    def legacy_initialize(self) -> str:
        """LEGACY-compat only: the pre-modern ``initialize`` handshake."""
        body: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": _next_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "razormesh-buyer-agent", "version": "0.1"},
            },
        }
        status, payload, headers = self._post(body, {})
        if status not in (200, 201):
            raise RuntimeError(f"initialize failed: {status} {payload!r}")
        session_id = headers.get("mcp-session-id") or headers.get("Mcp-Session-Id")
        if not session_id:
            raise RuntimeError("initialize returned no session id")
        return session_id

    def legacy_call_tool(
        self, session_id: str, name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """LEGACY-compat only: ``tools/call`` bound to an initialize session."""
        body: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": _next_id(),
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
        status, payload, _ = self._post(body, {"mcp-session-id": session_id})
        if status != 200:
            raise RuntimeError(f"tool {name} failed: {status} {payload!r}")
        return _tool_payload(name, payload, allow_empty=False)

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

    def run_modern_acceptance(
        self,
        *,
        intent_id: str,
        product_id: str,
        quantity: int = 1,
        currency: str = "INR",
    ) -> dict[str, Any]:
        """Drive the Phase-4 acceptance ingress via the MCP 2026-07-28
        **modern** per-request envelope. No ``initialize`` handshake,
        no ``Mcp-Session-Id``. Every call carries the required
        ``params._meta`` envelope + ``MCP-Protocol-Version`` +
        ``Mcp-Method`` + ``Mcp-Name`` headers.
        """
        # Step 1: modern server/discover (no session, no init).
        discover = self.discover()
        if "2026-07-28" not in discover.get("supportedVersions", []):
            raise RuntimeError(f"server does not advertise modern 2026-07-28; got {discover!r}")
        # Step 2: modern tools/list.
        tools = self.list_tools_modern()
        names = {t["name"] for t in tools}
        for required in (
            "create_cart",
            "update_cart",
            "propose_checkout",
            "get_checkout",
            "evaluate_checkout",
            "request_authorization",
            "complete_authorized_checkout",
        ):
            if required not in names:
                raise RuntimeError(f"modern tools/list missing required tool {required!r}")
        # Step 3: modern tools/call — cart + checkout prep.
        cart = self.call_tool_modern(
            "create_cart",
            {"agent_id": self.agent_id, "principal_id": self.principal_id},
        )
        cart_id = cart.get("cart_id", "")
        self.call_tool_modern(
            "update_cart",
            {
                "cart_id": cart_id,
                "items": [{"product_id": product_id, "quantity": quantity}],
            },
        )
        self.call_tool_modern(
            "propose_checkout",
            {
                "cart_id": cart_id,
                "intent_id": intent_id,
                "items": [{"product_id": product_id, "quantity": quantity}],
            },
        )
        self.call_tool_modern("get_checkout", {"checkout_id": "chk_preview"})
        self.call_tool_modern(
            "evaluate_checkout",
            {"checkout_id": "chk_preview", "intent_id": intent_id},
        )
        self.call_tool_modern("request_authorization", {"actor": "buyer-agent"})
        # Step 4: modern complete_authorized_checkout.
        final = self.call_tool_modern(
            "complete_authorized_checkout",
            {
                "intent_id": intent_id,
                "product_id": product_id,
                "quantity": quantity,
                "currency": currency,
            },
        )
        return {
            "discover": discover,
            "tool_count": len(tools),
            "cart_id": cart_id,
            "final": final,
        }


__all__ = [
    "MCP_PROTOCOL_META",
    "MCP_PROTOCOL_VERSION",
    "DeterministicBuyerAgent",
]
