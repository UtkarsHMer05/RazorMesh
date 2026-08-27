"""ACP `2026-01-30` adapter tests (M40..M43)."""

from __future__ import annotations

from razormesh_api.protocol.acp_adapter import (
    ACP_RAZORMESH_PAYMENT_HANDLER,
    ACP_TARGET_VERSION,
    ACPLifecycleState,
    build_acp_checkout_session,
    build_acp_complete_response,
    build_acp_envelope,
    intersect_capabilities,
    is_legal_transition,
)
from razormesh_api.protocol.ir import (
    AgentCommerceIR,
    _IRAuthorization,
    _IRCheckout,
    _IRItem,
    _IRMerchant,
    _IRProvenance,
    _IRTotals,
    _Money,
    _Quantity,
)


def test_target_version_pinned():
    assert ACP_TARGET_VERSION == "2026-01-30"


def test_lifecycle_legal_transitions():
    assert is_legal_transition(ACPLifecycleState.NOT_READY, ACPLifecycleState.READY)
    assert is_legal_transition(ACPLifecycleState.READY, ACPLifecycleState.IN_PROGRESS)
    assert is_legal_transition(ACPLifecycleState.IN_PROGRESS, ACPLifecycleState.COMPLETED)
    # Illegal: not_ready -> completed (skipping intermediate states).
    assert not is_legal_transition(ACPLifecycleState.NOT_READY, ACPLifecycleState.COMPLETED)
    # Illegal: completed is terminal.
    assert not is_legal_transition(ACPLifecycleState.COMPLETED, ACPLifecycleState.IN_PROGRESS)


def test_lifecycle_cancel_legal_from_open_states():
    for src in (
        ACPLifecycleState.NOT_READY,
        ACPLifecycleState.READY,
        ACPLifecycleState.IN_PROGRESS,
    ):
        assert is_legal_transition(src, ACPLifecycleState.CANCELED)


def test_razorpay_handler_namespaced_and_nonstandard():
    h = ACP_RAZORMESH_PAYMENT_HANDLER
    assert h["name"] == "io.razormesh.razorpay.test_checkout"
    # P4-S18: we never claim standard ACP Delegate Payment via Razorpay.
    assert h["requires_delegate_payment"] is False
    assert h["requires_pci_compliance"] is False
    assert h["test_mode"] is True
    # psp is razorpay but the handler is namespaced and not Stripe.
    assert h["psp"] == "razorpay"
    assert "stripe" not in h["name"].lower()


def test_capability_intersection_handlers():
    seller = {
        "payment": {
            "handlers": [
                {"id": "razorpay_test_checkout", "name": "io.razormesh.razorpay.test_checkout"},
                {"id": "card_tokenized", "name": "dev.acp.tokenized.card"},
            ]
        },
        "interventions": {"supported": ["3ds", "address_verification"]},
        "extensions": [{"name": "discount"}],
    }
    agent = {
        "payment": {
            "handlers": [
                {"id": "razorpay_test_checkout", "name": "io.razormesh.razorpay.test_checkout"},
            ]
        },
        "interventions": {"supported": ["3ds"]},
        "extensions": [{"name": "discount"}, {"name": "shipping"}],
    }
    inter = intersect_capabilities(agent, seller)
    ids = [h["id"] for h in inter["payment"]["handlers"]]
    assert ids == ["razorpay_test_checkout"]
    assert inter["interventions"]["supported"] == ["3ds"]
    assert inter["extensions"] == ["discount"]


def test_capability_intersection_empty():
    seller = {"payment": {"handlers": [{"id": "x"}]}, "interventions": {"supported": ["3ds"]}}
    agent = {"payment": {"handlers": [{"id": "y"}]}, "interventions": {"supported": []}}
    inter = intersect_capabilities(agent, seller)
    assert inter["payment"]["handlers"] == []
    assert inter["interventions"]["supported"] == []


def test_acp_checkout_session_shape():
    items = [
        {"product_id": "prod_a", "quantity": 1, "unit_price_minor": 189900},
        {"product_id": "prod_b", "quantity": 2, "unit_price_minor": 49900},
    ]
    session = build_acp_checkout_session(
        items=items,
        currency="INR",
        total_minor=189900 + 2 * 49900,
        intent_contract_id="ic_1",
    )
    assert session["status"] == ACPLifecycleState.NOT_READY.value
    assert session["currency"] == "INR"
    assert session["totals"]["total_minor"] == 189900 + 2 * 49900
    assert session["capabilities"]["payment"]["handlers"][0]["name"] == (
        "io.razormesh.razorpay.test_checkout"
    )


def test_acp_complete_response_with_ir():
    ir = AgentCommerceIR(
        principal_ref="p",
        agent_ref="a",
        merchant=_IRMerchant(merchant_id="m1"),
        checkout=_IRCheckout(revision="r1"),
        items=[
            _IRItem(
                product_id="prod_a",
                quantity=_Quantity(value=1, unit="EA", scale=0),
                unit_price=_Money(value_minor=189900, currency="INR"),
            )
        ],
        totals=_IRTotals(total_minor=189900),
        currency="INR",
        authorization=_IRAuthorization(intent_contract_id="ic_1", authorization_generation=1),
        provenance=_IRProvenance(source_protocols=["acp"]),
    )
    response = build_acp_complete_response(
        session_id="co_1",
        intent_contract_id="ic_1",
        ir=ir,
        execution_attempt_id="att_1",
    )
    assert response["status"] == "completed"
    assert "commerce_commitment" in response
    assert response["razormesh_test_mode"] is True
    assert response["payment_handler"] == "io.razormesh.razorpay.test_checkout"


def test_acp_complete_response_no_execution_attempt_blocks():
    ir = AgentCommerceIR(
        principal_ref="p",
        agent_ref="a",
        merchant=_IRMerchant(merchant_id="m1"),
        checkout=_IRCheckout(revision="r1"),
        items=[
            _IRItem(
                product_id="prod_a",
                quantity=_Quantity(value=1, unit="EA", scale=0),
                unit_price=_Money(value_minor=100, currency="INR"),
            )
        ],
        totals=_IRTotals(total_minor=100),
        currency="INR",
        authorization=_IRAuthorization(intent_contract_id="ic_1", authorization_generation=1),
        provenance=_IRProvenance(source_protocols=["acp"]),
    )
    response = build_acp_complete_response(
        session_id="co_1",
        intent_contract_id="ic_1",
        ir=ir,
        execution_attempt_id=None,
    )
    assert response["status"] == ACPLifecycleState.NOT_READY.value


def test_acp_envelope_construction():
    from razormesh_api.protocol import SourceProtocol, evaluate_envelope

    env = build_acp_envelope(
        raw_payload=b'{"id":"co_1"}',
        message_id="m1",
        request_id="r1",
        idempotency_key="k1",
        agent="agent_test",
        principal_reference="principal_test",
        merchant_reference="merch_test",
        commerce_payload_reference="ref_1",
        signature_evidence={"scheme": "ed25519", "key_id": "k"},
        identity_evidence={"agent": "agent_test"},
        capability_evidence={"handlers": ["razorpay_test_checkout"]},
    )
    assert env.source_protocol == SourceProtocol.ACP
    assert env.source_protocol_version == ACP_TARGET_VERSION
    assert evaluate_envelope(env).decision.value == "PROTOCOL_PASS"
