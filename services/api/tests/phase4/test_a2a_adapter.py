"""A2A `v1.0.1` compatibility slice tests (M44)."""

from __future__ import annotations

from razormesh_api.protocol import SourceProtocol, evaluate_envelope
from razormesh_api.protocol.a2a_adapter import (
    A2A_TARGET_VERSION,
    RMA_A2A_AGENT_CARD,
    a2a_message_id_is_idempotency_key,
    build_a2a_envelope,
    build_a2a_message_with_ucp_datapart,
)


def test_target_version_pinned():
    assert A2A_TARGET_VERSION == "v1.0.1"


def test_agent_card_advertises_ucp_extension():
    exts = RMA_A2A_AGENT_CARD["capabilities"]["extensions"]
    uris = [e["uri"] for e in exts]
    assert "https://razormesh.dev/extensions/ucp/v1" in uris
    # AP2 evidence refs advertised.
    assert "https://razormesh.dev/extensions/ap2/v0.2.0" in uris


def test_agent_card_http_json_binding():
    si = RMA_A2A_AGENT_CARD["supportedInterfaces"]
    assert any(i["protocolBinding"] == "HTTP+JSON" for i in si)
    assert any(i["protocolVersion"] == A2A_TARGET_VERSION for i in si)


def test_agent_card_not_a_full_a2a_platform():
    # Master prompt §17: this is a *slice*, not a full platform.
    skills = RMA_A2A_AGENT_CARD["skills"]
    assert len(skills) <= 1
    # And we do not claim streaming / push notifications.
    assert RMA_A2A_AGENT_CARD["capabilities"]["streaming"] is False
    assert RMA_A2A_AGENT_CARD["capabilities"]["pushNotifications"] is False


def test_a2a_envelope_construction():
    env = build_a2a_envelope(
        raw_payload=b'{"id":"msg_1","role":"ROLE_USER"}',
        message_id="msg_1",
        request_id="req_1",
        idempotency_key="idem_a2a_1",
        agent="a2a_agent",
        principal_reference="principal_a2a",
        merchant_reference="merch_a2a",
        commerce_payload_reference="ref_1",
        signature_evidence={"scheme": "ed25519", "key_id": "k"},
        identity_evidence={"agent": "a2a_agent"},
        capability_evidence={"skills": ["razormesh-protocol-gateway"]},
        extension_evidence=[{"uri": "https://razormesh.dev/extensions/ucp/v1"}],
    )
    assert env.source_protocol == SourceProtocol.A2A
    assert env.source_protocol_version == A2A_TARGET_VERSION
    assert env.idempotency_key == "idem_a2a_1"
    assert evaluate_envelope(env).decision.value == "PROTOCOL_PASS"


def test_message_carries_ucp_datapart():
    msg = build_a2a_message_with_ucp_datapart(
        message_text="Buy headphones under ₹5000",
        ucp_checkout_payload={"revision": "r1", "items": [{"product_id": "p1"}]},
        ap2_mandate_refs=["mandate_a"],
    )
    assert msg["id"].startswith("msg_")
    parts = msg["parts"]
    assert any(p.get("kind") == "data" and "ucp" in p.get("data", {}) for p in parts)
    assert "https://razormesh.dev/extensions/ucp/v1" in msg["extensions"]


def test_message_id_becomes_idempotency_key():
    msg = build_a2a_message_with_ucp_datapart(
        message_text="x",
        ucp_checkout_payload={"revision": "r1"},
    )
    key = a2a_message_id_is_idempotency_key(msg)
    assert key == msg["id"]
    # Different message => different key.
    msg2 = build_a2a_message_with_ucp_datapart(
        message_text="x",
        ucp_checkout_payload={"revision": "r1"},
    )
    assert a2a_message_id_is_idempotency_key(msg2) != key
