"""AgentPay-X benchmark (M46).

A defensive/synthetic cross-protocol benchmark covering 5 attack
families out of the 45 in master prompt §19:

1. amount mutation
2. merchant substitution
3. recurring-term insertion
4. protocol-version downgrade
5. signature manipulation

The full benchmark targets 150-300 scenarios. The slice here covers
the highest-leverage families; expanding is a one-line addition of
new mutation cases per family.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from razormesh_api.protocol import (
    AgentCommerceIR,
    SourceProtocol,
    commitment_hash,
    compute_commitment,
    envelope_from_raw,
    equal_under_commitment,
    evaluate_envelope,
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


@dataclass
class AgentPayXScenario:
    name: str
    family: str  # one of the master prompt §19 families
    safe: bool  # True if scenario is a "safe suspicious-looking text" case; False if attack
    ir_a: AgentCommerceIR
    ir_b: AgentCommerceIR | None = None  # mutated variant (if attack)
    expected_block: bool = True
    notes: str = ""


@dataclass
class AgentPayXResult:
    scenario: AgentPayXScenario
    passed: bool
    reason: str = ""


def _base_ir() -> AgentCommerceIR:
    return AgentCommerceIR(
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


def build_scenarios() -> list[AgentPayXScenario]:
    """Build the AgentPay-X slice. 12 scenarios across 5 families."""
    out: list[AgentPayXScenario] = []
    base = _base_ir()

    # 1. amount mutation
    a = base
    b = base.model_copy(update={"totals": _IRTotals(total_minor=189901)})
    out.append(AgentPayXScenario(
        name="amount.plus-one",
        family="amount_mutation",
        safe=False,
        ir_a=a, ir_b=b,
        expected_block=True,
        notes="Same authorization-relevant values, total_minor +1",
    ))

    # 2. merchant substitution
    a = base
    b = base.model_copy(update={"merchant": _IRMerchant(merchant_id="merch_b")})
    out.append(AgentPayXScenario(
        name="merchant.substitution",
        family="merchant_substitution",
        safe=False,
        ir_a=a, ir_b=b,
        expected_block=True,
    ))

    # 3. product substitution
    a = base
    b = base.model_copy(update={
        "items": [
            _IRItem(
                product_id="prod_b",
                quantity=_Quantity(value=1, unit="EA", scale=0),
                unit_price=_Money(value_minor=189900, currency="INR"),
            )
        ]
    })
    out.append(AgentPayXScenario(
        name="product.substitution",
        family="product_substitution",
        safe=False,
        ir_a=a, ir_b=b,
        expected_block=True,
    ))

    # 4. quantity mutation
    a = base
    b = base.model_copy(update={
        "items": [
            _IRItem(
                product_id="prod_a",
                quantity=_Quantity(value=2, unit="EA", scale=0),
                unit_price=_Money(value_minor=189900, currency="INR"),
            )
        ]
    })
    out.append(AgentPayXScenario(
        name="quantity.double",
        family="quantity_mutation",
        safe=False,
        ir_a=a, ir_b=b,
        expected_block=True,
    ))

    # 5. recurring-term insertion
    a = base
    b = base.model_copy(update={"recurring": _IRRecurring(mode="monthly", interval="1m", amount_minor=189900)})
    out.append(AgentPayXScenario(
        name="recurring.inserted",
        family="recurring_term_insertion",
        safe=False,
        ir_a=a, ir_b=b,
        expected_block=True,
    ))

    # 6. currency mutation
    a = base
    b = base.model_copy(update={"currency": "USD"})
    out.append(AgentPayXScenario(
        name="currency.usd",
        family="currency_mutation",
        safe=False,
        ir_a=a, ir_b=b,
        expected_block=True,
    ))

    # 7. equivalent representation (safe)
    out.append(AgentPayXScenario(
        name="equivalent.canonical",
        family="equivalent_representation",
        safe=True,
        ir_a=base, ir_b=base.model_copy(deep=True),
        expected_block=False,
    ))

    # 8. protocol-version downgrade (attack)
    out.append(AgentPayXScenario(
        name="mcp.downgrade",
        family="mcp_protocol_downgrade",
        safe=False,
        ir_a=base, ir_b=None,
        expected_block=True,
        notes="Firewall must reject MCP 2025-11-25",
    ))

    # 9. AP2 unknown vct
    out.append(AgentPayXScenario(
        name="ap2.unknown_vct",
        family="ap2_unknown_constraint",
        safe=False,
        ir_a=base, ir_b=None,
        expected_block=True,
    ))

    # 10. UCP unsupported version
    out.append(AgentPayXScenario(
        name="ucp.unsupported_version",
        family="ucp_unsupported_version",
        safe=False,
        ir_a=base, ir_b=None,
        expected_block=True,
    ))

    # 11. UCP invalid Content-Digest
    out.append(AgentPayXScenario(
        name="ucp.invalid_digest",
        family="ucp_invalid_content_digest",
        safe=False,
        ir_a=base, ir_b=None,
        expected_block=True,
    ))

    # 12. ACP illegal transition
    out.append(AgentPayXScenario(
        name="acp.illegal_transition",
        family="acp_illegal_lifecycle_transition",
        safe=False,
        ir_a=base, ir_b=None,
        expected_block=True,
    ))

    return out


def run_scenario(scenario: AgentPayXScenario) -> AgentPayXResult:
    """Run a single scenario and return the outcome."""
    if scenario.name == "mcp.downgrade":
        # Firewall check on a downgraded envelope.
        env = envelope_from_raw(
            source_protocol=SourceProtocol.MCP,
            source_protocol_version="2025-11-25",  # older
            source_transport="stdio",
            adapter_version="razormesh-mcp-adapter-0.1.0",
            message_id="msg_x",
            request_id="r_x",
            idempotency_key=None,
            raw_payload=b'{"x":1}',
            signature_evidence={"scheme": "ed25519"},
            identity_evidence={"agent": "a"},
            capability_evidence={"tools": []},
            agent="a",
            principal_reference="p",
            merchant_reference="m",
            commerce_payload_reference="c",
        )
        result = evaluate_envelope(env)
        passed = result.decision.value == "PROTOCOL_BLOCK"
        return AgentPayXResult(
            scenario=scenario,
            passed=passed,
            reason="PROTOCOL_BLOCK" if passed else f"got {result.decision.value}",
        )
    if scenario.name == "ucp.unsupported_version":
        env = envelope_from_raw(
            source_protocol=SourceProtocol.UCP,
            source_protocol_version="2099-99-99",
            source_transport="rest",
            adapter_version="razormesh-ucp-adapter-0.1.0",
            message_id="msg_y",
            request_id="r_y",
            idempotency_key=None,
            raw_payload=b'{"x":1}',
            signature_evidence={"scheme": "ucp-ed25519"},
            identity_evidence={"agent": "a"},
            capability_evidence={"profile": "2099-99-99"},
            agent="a",
            principal_reference="p",
            merchant_reference="m",
            commerce_payload_reference="c",
        )
        result = evaluate_envelope(env)
        passed = result.decision.value == "PROTOCOL_BLOCK"
        return AgentPayXResult(
            scenario=scenario,
            passed=passed,
            reason="PROTOCOL_BLOCK" if passed else f"got {result.decision.value}",
        )
    if scenario.name == "ucp.invalid_digest":
        # UCP signature evidence missing/digest absent.
        env = envelope_from_raw(
            source_protocol=SourceProtocol.UCP,
            source_protocol_version="2026-04-08",
            source_transport="rest",
            adapter_version="razormesh-ucp-adapter-0.1.0",
            message_id="msg_z",
            request_id="r_z",
            idempotency_key=None,
            raw_payload=b'{"x":1}',
            signature_evidence={},  # invalid: no signature
            identity_evidence={"agent": "a"},
            capability_evidence={"profile": "2026-04-08"},
            agent="a",
            principal_reference="p",
            merchant_reference="m",
            commerce_payload_reference="c",
        )
        result = evaluate_envelope(env)
        passed = result.decision.value == "PROTOCOL_BLOCK"
        return AgentPayXResult(
            scenario=scenario,
            passed=passed,
            reason="PROTOCOL_BLOCK" if passed else f"got {result.decision.value}",
        )
    if scenario.name == "ap2.unknown_vct":
        # AP2 vct not in allowed set. We don't have a real AP2 envelope
        # validator, but the contract is documented: unknown vct is
        # rejected by the verifier. We test the contract via the
        # ap2_verifier module's vct enforcement.
        from razormesh_api.protocol.ap2_verifier import (
            generate_ap2_test_merchant_key,
            build_ap2_merchant_checkout_jwt,
            export_ap2_test_merchant_pub_jwk,
            verify_ap2_merchant_jwt_es256,
        )
        key = generate_ap2_test_merchant_key()
        jwk = export_ap2_test_merchant_pub_jwk(key, "kid-1")
        jwt = build_ap2_merchant_checkout_jwt(
            key=key, kid="kid-1", ir=scenario.ir_a,
            vct="some.unauthorized.vct",
        )
        ok, reason = verify_ap2_merchant_jwt_es256(
            jwt=jwt, public_jwk=jwk, expected_vct="ap2.checkout.merchant.v0.2.0",
        )
        passed = (not ok) and reason == "vct_mismatch"
        return AgentPayXResult(
            scenario=scenario, passed=passed,
            reason=("vct_mismatch" if passed else f"unexpected: {ok} {reason}"),
        )
    if scenario.name == "acp.illegal_transition":
        from razormesh_api.protocol.acp_adapter import (
            ACPLifecycleState, is_legal_transition,
        )
        passed = not is_legal_transition(
            ACPLifecycleState.NOT_READY, ACPLifecycleState.COMPLETED
        )
        return AgentPayXResult(
            scenario=scenario, passed=passed,
            reason="illegal_transition_blocked" if passed else "transition_allowed",
        )
    if scenario.ir_b is None:
        return AgentPayXResult(
            scenario=scenario, passed=False, reason="no_mutation_target",
        )
    # Default: commitment-equality check (master prompt §20).
    a = compute_commitment(scenario.ir_a)
    b = compute_commitment(scenario.ir_b)
    if scenario.expected_block:
        passed = (a != b) and not equal_under_commitment(scenario.ir_a, scenario.ir_b)
    else:
        passed = (a == b) and equal_under_commitment(scenario.ir_a, scenario.ir_b)
    return AgentPayXResult(
        scenario=scenario, passed=passed,
        reason="MISMATCH" if a != b else "MATCH",
    )


def run_benchmark() -> dict[str, Any]:
    """Run the AgentPay-X slice and return the metrics dict."""
    scenarios = build_scenarios()
    results = [run_scenario(s) for s in scenarios]
    safe_results = [r for r in results if r.scenario.safe]
    attack_results = [r for r in results if not r.scenario.safe]
    safe_pass = sum(1 for r in safe_results if r.passed)
    attack_block = sum(1 for r in attack_results if r.passed)
    return {
        "scenarios_total": len(scenarios),
        "scenarios_safe": len(safe_results),
        "scenarios_attack": len(attack_results),
        "safe_pass_rate": (safe_pass / len(safe_results)) if safe_results else 1.0,
        "attack_block_rate": (attack_block / len(attack_results)) if attack_results else 1.0,
        "results": [
            {
                "name": r.scenario.name,
                "family": r.scenario.family,
                "safe": r.scenario.safe,
                "expected_block": r.scenario.expected_block,
                "passed": r.passed,
                "reason": r.reason,
            }
            for r in results
        ],
    }


__all__ = [
    "AgentPayXScenario",
    "AgentPayXResult",
    "build_scenarios",
    "run_scenario",
    "run_benchmark",
]
