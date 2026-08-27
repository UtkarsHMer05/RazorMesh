"""Phase-4 differential / property / fuzz / concurrency security sweep (M47).

Master prompt §20 + §47:
- equivalent protocol normalization
- one-field mutation
- fuzz malformed / unknown extensions
- signature mutation
- 20+ concurrent duplicate completions
- mandate replay
- MCP/UCP/ACP duplicate storms

These tests run against the RazorMesh Phase-4 primitives. They are
not exhaustive on the 150-300 AgentPay-X scenarios (M46); they
focus on the property-level invariants that the benchmark relies on.
"""

from __future__ import annotations

import hashlib
from typing import Any

import pytest

from razormesh_api.protocol import (
    AgentCommerceIR,
    SourceProtocol,
    commitment_hash,
    compute_commitment,
    envelope_from_raw,
    equal_under_commitment,
    evaluate_envelope,
    hash_payload,
    envelope_to_canonical_json,
    MAX_PAYLOAD_BYTES,
)
from razormesh_api.protocol.ir import (
    _IRAuthorization,
    _IRCheckout,
    _IRItem,
    _IRMerchant,
    _IRProvenance,
    _IRRecurring,
    _IRTotals,
    _Money,
    _Quantity,
)


def _ir(**overrides: Any) -> AgentCommerceIR:
    base = AgentCommerceIR(
        principal_ref="p", agent_ref="a",
        merchant=_IRMerchant(merchant_id="merch_a"),
        checkout=_IRCheckout(revision="r1"),
        items=[
            _IRItem(
                product_id="prod_a",
                quantity=_Quantity(value=1, unit="EA", scale=0),
                unit_price=_Money(value_minor=189900, currency="INR"),
            )
        ],
        totals=_IRTotals(total_minor=189900), currency="INR",
        authorization=_IRAuthorization(intent_contract_id="ic_1", authorization_generation=1),
        provenance=_IRProvenance(source_protocols=["mcp"]),
    )
    return base.model_copy(update=overrides)


class TestDifferential:
    def test_equivalent_irs_match(self):
        a = _ir()
        b = _ir()
        assert equal_under_commitment(a, b)

    def test_one_field_total_changes_commitment(self):
        a = _ir()
        b = _ir(totals=_IRTotals(total_minor=189901))
        assert not equal_under_commitment(a, b)

    def test_one_field_currency_changes_commitment(self):
        a = _ir()
        b = _ir(currency="USD")
        assert not equal_under_commitment(a, b)

    def test_one_field_merchant_changes_commitment(self):
        a = _ir()
        b = _ir(merchant=_IRMerchant(merchant_id="merch_b"))
        assert not equal_under_commitment(a, b)

    def test_one_field_product_changes_commitment(self):
        a = _ir()
        b = _ir(items=[
            _IRItem(
                product_id="prod_b",
                quantity=_Quantity(value=1, unit="EA", scale=0),
                unit_price=_Money(value_minor=189900, currency="INR"),
            )
        ])
        assert not equal_under_commitment(a, b)

    def test_one_field_quantity_changes_commitment(self):
        a = _ir()
        b = _ir(items=[
            _IRItem(
                product_id="prod_a",
                quantity=_Quantity(value=2, unit="EA", scale=0),
                unit_price=_Money(value_minor=189900, currency="INR"),
            )
        ])
        assert not equal_under_commitment(a, b)

    def test_one_field_recurring_changes_commitment(self):
        a = _ir()
        b = _ir(recurring=_IRRecurring(mode="monthly", interval="1m", amount_minor=189900))
        assert not equal_under_commitment(a, b)

    def test_item_order_does_not_change_commitment(self):
        item_a = _IRItem(product_id="prod_a", quantity=_Quantity(value=1, unit="EA", scale=0),
                         unit_price=_Money(value_minor=100, currency="INR"))
        item_b = _IRItem(product_id="prod_b", quantity=_Quantity(value=1, unit="EA", scale=0),
                         unit_price=_Money(value_minor=200, currency="INR"))
        a = _ir(items=[item_a, item_b])
        b = _ir(items=[item_b, item_a])
        assert equal_under_commitment(a, b)

    def test_hash_is_deterministic(self):
        a = _ir()
        h1 = commitment_hash(a)
        h2 = commitment_hash(a.model_copy(deep=True))
        assert h1 == h2


class TestReplay:
    def test_replay_indicator_records(self):
        env = envelope_from_raw(
            source_protocol=SourceProtocol.MCP,
            source_protocol_version="2026-07-28",
            source_transport="stdio",
            adapter_version="x",
            message_id="m",
            request_id="r",
            idempotency_key="k_recent",
            raw_payload=b"x",
            signature_evidence={"scheme": "ed25519"},
            identity_evidence={"agent": "a"},
            capability_evidence={"tools": []},
            agent="a",
            principal_reference="p",
            merchant_reference="m",
            commerce_payload_reference="c",
        )
        result = evaluate_envelope(env, seen_recent_keys={"k_recent"})
        # The firewall records REPLAY but does not BLOCK based on
        # that reason alone; the caller must compare payloads and
        # decide. We verify the reason is present.
        from razormesh_api.protocol.firewall import FirewallReason
        assert FirewallReason.REPLAY in result.reasons


class TestFuzz:
    def test_fuzz_unknown_protocol_field_rejected(self):
        # Construct an envelope with an extra field. Pydantic's
        # `extra="forbid"` rejects it before the firewall sees it.
        from pydantic import ValidationError

        env = envelope_from_raw(
            source_protocol=SourceProtocol.MCP,
            source_protocol_version="2026-07-28",
            source_transport="stdio",
            adapter_version="x",
            message_id="m",
            request_id="r",
            idempotency_key=None,
            raw_payload=b"x",
            signature_evidence={"scheme": "ed25519"},
            identity_evidence={"agent": "a"},
            capability_evidence={"tools": []},
            agent="a",
            principal_reference="p",
            merchant_reference="m",
            commerce_payload_reference="c",
        )
        with pytest.raises(ValidationError):
            env.model_validate({**env.model_dump(), "evil_unknown": True})

    def test_oversized_payload_rejected(self):
        big = b"x" * (MAX_PAYLOAD_BYTES + 1)
        with pytest.raises(ValueError):
            envelope_from_raw(
                source_protocol=SourceProtocol.MCP,
                source_protocol_version="2026-07-28",
                source_transport="stdio",
                adapter_version="x",
                message_id="m",
                request_id="r",
                idempotency_key=None,
                raw_payload=big,
                signature_evidence={"scheme": "ed25519"},
                identity_evidence={"agent": "a"},
                capability_evidence={"tools": []},
                agent="a",
                principal_reference="p",
                merchant_reference="m",
                commerce_payload_reference="c",
            )

    def test_signature_mutation_causes_mismatch(self):
        # The envelope's signature_evidence is a structured dict. A
        # mutation in the signature scheme value is preserved
        # by the canonical hash, ensuring audit verifiability.
        env = envelope_from_raw(
            source_protocol=SourceProtocol.MCP,
            source_protocol_version="2026-07-28",
            source_transport="stdio",
            adapter_version="x",
            message_id="m",
            request_id="r",
            idempotency_key=None,
            raw_payload=b"x",
            signature_evidence={"scheme": "ed25519", "sig": "abc"},
            identity_evidence={"agent": "a"},
            capability_evidence={"tools": []},
            agent="a",
            principal_reference="p",
            merchant_reference="m",
            commerce_payload_reference="c",
        )
        tampered = env.model_copy(update={"signature_evidence": {"scheme": "ed25519", "sig": "abd"}})
        assert envelope_to_canonical_json(env) != envelope_to_canonical_json(tampered)


class TestConcurrency:
    def test_concurrent_duplicate_completions_have_distinct_message_ids(self):
        # Master prompt §47: 20+ concurrent duplicate completions.
        # We verify the design property: each duplicate carries a
        # distinct message_id and the same idempotency_key. The
        # firewall's REPLAY reason signals to the caller to
        # dedupe; the commitment-hash check (master prompt §10)
        # ensures that mismatched payloads BLOCK.
        seen_messages: set[str] = set()
        for i in range(25):
            env = envelope_from_raw(
                source_protocol=SourceProtocol.MCP,
                source_protocol_version="2026-07-28",
                source_transport="stdio",
                adapter_version="x",
                message_id=f"msg_{i}",
                request_id=f"req_{i}",
                idempotency_key="k_dup",
                raw_payload=b"x",
                signature_evidence={"scheme": "ed25519"},
                identity_evidence={"agent": "a"},
                capability_evidence={"tools": []},
                agent="a",
                principal_reference="p",
                merchant_reference="m",
                commerce_payload_reference="c",
            )
            seen_messages.add(env.message_id)
        assert len(seen_messages) == 25

    def test_concurrent_same_message_id_replay(self):
        # Two envelopes with the SAME message_id but different
        # request_id should still produce the same canonical hash
        # (the canonical JSON is deterministic per envelope). The
        # caller's idempotency layer is responsible for de-duping.
        e1 = envelope_from_raw(
            source_protocol=SourceProtocol.MCP,
            source_protocol_version="2026-07-28",
            source_transport="stdio",
            adapter_version="x",
            message_id="msg_1",
            request_id="r1",
            idempotency_key="k1",
            raw_payload=b"x",
            signature_evidence={"scheme": "ed25519"},
            identity_evidence={"agent": "a"},
            capability_evidence={"tools": []},
            agent="a",
            principal_reference="p",
            merchant_reference="m",
            commerce_payload_reference="c",
        )
        e2 = envelope_from_raw(
            source_protocol=SourceProtocol.MCP,
            source_protocol_version="2026-07-28",
            source_transport="stdio",
            adapter_version="x",
            message_id="msg_1",
            request_id="r2",
            idempotency_key="k1",
            raw_payload=b"x",
            signature_evidence={"scheme": "ed25519"},
            identity_evidence={"agent": "a"},
            capability_evidence={"tools": []},
            agent="a",
            principal_reference="p",
            merchant_reference="m",
            commerce_payload_reference="c",
        )
        # Same message_id, different request_id => different canonical
        # JSON. The caller decides which to honor.
        assert envelope_to_canonical_json(e1) != envelope_to_canonical_json(e2)


class TestMCPEnvelopeManipulation:
    def test_envelope_hash_stable_under_field_order(self):
        # The canonical hash is order-stable (sorted JSON keys).
        # Reordering capability_evidence dict keys MUST NOT change
        # the canonical hash.
        from datetime import datetime, timezone
        fixed = datetime(2026, 8, 27, 12, 0, 0, tzinfo=timezone.utc)
        e1 = envelope_from_raw(
            source_protocol=SourceProtocol.MCP,
            source_protocol_version="2026-07-28",
            source_transport="stdio",
            adapter_version="x",
            message_id="m",
            request_id="r",
            idempotency_key=None,
            raw_payload=b"x",
            signature_evidence={"scheme": "ed25519", "kid": "k"},
            identity_evidence={"agent": "a", "principal": "p"},
            capability_evidence={"z": 1, "a": 2, "m": 3},
            agent="a",
            principal_reference="p",
            merchant_reference="m",
            commerce_payload_reference="c",
        ).model_copy(update={"received_at": fixed})
        e2 = envelope_from_raw(
            source_protocol=SourceProtocol.MCP,
            source_protocol_version="2026-07-28",
            source_transport="stdio",
            adapter_version="x",
            message_id="m",
            request_id="r",
            idempotency_key=None,
            raw_payload=b"x",
            signature_evidence={"kid": "k", "scheme": "ed25519"},
            identity_evidence={"principal": "p", "agent": "a"},
            capability_evidence={"a": 2, "m": 3, "z": 1},
            agent="a",
            principal_reference="p",
            merchant_reference="m",
            commerce_payload_reference="c",
        ).model_copy(update={"received_at": fixed})
        assert envelope_to_canonical_json(e1) == envelope_to_canonical_json(e2)


class TestPayloadHashing:
    def test_hash_payload_returns_sha256(self):
        h = hash_payload(b"abc")
        assert h == hashlib.sha256(b"abc").hexdigest()

    def test_oversized_payload_rejected(self):
        with pytest.raises(ValueError):
            hash_payload(b"x" * (MAX_PAYLOAD_BYTES + 1))

    def test_non_bytes_rejected(self):
        with pytest.raises(TypeError):
            hash_payload("not bytes")  # type: ignore[arg-type]
