"""M34 acceptance: context-bound single-use execution ticket verification."""

from datetime import UTC, datetime, timedelta

import pytest

from razormesh_api.domain.authz_hash import (
    checkout_authorization_hash,
    intent_authorization_hash,
)
from razormesh_api.domain.checkout import BoundedText, CheckoutEnvelope, LineItem
from razormesh_api.domain.ids import (
    DecisionId,
    ExecutionTicketId,
    IntentId,
    new_ulid,
)
from razormesh_api.domain.intent import IntentContract
from razormesh_api.domain.money import Money
from razormesh_api.domain.provenance import Provenanced
from razormesh_api.keys import DevSigningKeys
from razormesh_api.tickets import (
    CurrentBinding,
    ExecutionTicketClaims,
    SignedTicket,
    TicketIssuer,
    TicketRejected,
    TicketVerifier,
)

NOW = datetime.now(UTC)


def _envelope() -> CheckoutEnvelope:
    it = LineItem(
        product_id=f"prd_{new_ulid()}",
        display_name=Provenanced[BoundedText].model_construct(
            value=BoundedText(text="Headphones"),
            trust_class="UNTRUSTED_CONTENT",
            source_type="MERCHANT_FREE_TEXT",
            source_id="c",
            observed_at=NOW,
        ),
        quantity=1,
        unit_price=Money(100000),
    )
    return CheckoutEnvelope(
        checkout_id=f"chk_{new_ulid()}",
        revision=1,
        merchant_id=f"mrc_{new_ulid()}",
        line_items=(it,),
        tax=Money(0),
        shipping=Money(0),
        fees=Money(0),
        provided_total=Money(100000),
        observed_at=NOW,
    )


def _intent() -> IntentContract:
    return IntentContract(
        intent_id=IntentId.generate(),
        principal_id=f"usr_{new_ulid()}",
        agent_id=f"agt_{new_ulid()}",
        authorization_generation=1,
        currency="INR",
        max_total=Money(500000),
        aggregate_budget=Money(2000000),
        approval_threshold=Money(400000),
        issued_at=NOW,
        authorized_at=NOW,
        expires_at=NOW + timedelta(minutes=30),
    )


@pytest.fixture()
def keys(tmp_path):  # type: ignore[no-untyped-def]
    return DevSigningKeys(
        private_path=str(tmp_path / "p.pem"), public_path=str(tmp_path / "pub.pem")
    ).ensure()


def _claims(env: CheckoutEnvelope, contract: IntentContract) -> ExecutionTicketClaims:
    return ExecutionTicketClaims(
        ticket_id=ExecutionTicketId.generate(),
        decision_id=DecisionId.generate(),
        checkout_id=env.checkout_id,
        intent_id=contract.intent_id,
        principal_id=contract.principal_id.value,
        agent_id=contract.agent_id.value,
        authorization_generation=contract.authorization_generation,
        intent_hash=intent_authorization_hash(contract),
        checkout_hash=checkout_authorization_hash(env),
        checkout_revision=env.revision,
        merchant_id=env.merchant_id.value,
        amount_minor=env.compute_total().amount_minor,
        currency="INR",
        policy_version="razormesh-phase1-policy-v1",
        nonce=f"nonce-{new_ulid()}{new_ulid()}",
        issued_at=NOW,
        expires_at=NOW + timedelta(seconds=60),
    )


def _binding(claims: ExecutionTicketClaims) -> CurrentBinding:
    return CurrentBinding(
        principal_id=claims.principal_id,
        agent_id=claims.agent_id,
        intent_id=str(claims.intent_id),
        intent_hash=claims.intent_hash,
        authorization_generation=claims.authorization_generation,
        checkout_id=str(claims.checkout_id),
        checkout_hash=claims.checkout_hash,
        checkout_revision=claims.checkout_revision,
        merchant_id=claims.merchant_id,
        amount_minor=claims.amount_minor,
        currency=claims.currency,
    )


def _verifier(keys, offset_seconds: int = 0) -> TicketVerifier:  # type: ignore[no-untyped-def]
    return TicketVerifier(keys, now_utc=NOW + timedelta(seconds=offset_seconds))


def test_happy_path_issue_and_verify(keys) -> None:  # type: ignore[no-untyped-def]
    env, contract = _envelope(), _intent()
    claims = _claims(env, contract)
    signed = TicketIssuer(keys).issue(claims)
    verified = _verifier(keys).verify(signed, _binding(claims))
    assert verified.ticket_id == claims.ticket_id


def test_tampered_amount_rejected_by_signature(keys) -> None:  # type: ignore[no-untyped-def]
    env, contract = _envelope(), _intent()
    claims = _claims(env, contract)
    signed = TicketIssuer(keys).issue(claims)
    # attacker bumps the amount inside the transport JSON
    tampered_json = signed.claims_json.replace('"amount_minor":100000', '"amount_minor":99000')
    if tampered_json == signed.claims_json:
        raise AssertionError("test setup failed to modify amount")
    with pytest.raises(TicketRejected) as err:
        _verifier(keys).verify(SignedTicket(tampered_json, signed.signature_hex), _binding(claims))
    assert err.value.code == "SIGNATURE_INVALID"


def test_expired_ticket_rejected_even_when_binding_matches(keys) -> None:  # type: ignore[no-untyped-def]
    env, contract = _envelope(), _intent()
    claims = _claims(env, contract)
    signed = TicketIssuer(keys).issue(claims)
    verifier_late = TicketVerifier(keys, now_utc=NOW + timedelta(seconds=61))
    with pytest.raises(TicketRejected) as err:
        verifier_late.verify(signed, _binding(claims))
    assert err.value.code == "TICKET_EXPIRED"


def test_wrong_principal_agent_merchant_rejected(keys) -> None:  # type: ignore[no-untyped-def]
    env, contract = _envelope(), _intent()
    claims = _claims(env, contract)
    signed = TicketIssuer(keys).issue(claims)

    good = _binding(claims)
    wrong_principal = CurrentBinding(**{**good.__dict__, "principal_id": "usr_attacker"})
    wrong_agent = CurrentBinding(**{**good.__dict__, "agent_id": "agt_rogue"})
    wrong_merchant = CurrentBinding(**{**good.__dict__, "merchant_id": f"mrc_{new_ulid()}"})

    for binding, expected_code in (
        (wrong_principal, "PRINCIPAL_MISMATCH"),
        (wrong_agent, "AGENT_MISMATCH"),
        (wrong_merchant, "MERCHANT_MISMATCH"),
    ):
        with pytest.raises(TicketRejected) as err:
            _verifier(keys).verify(signed, binding)
        assert err.value.code == expected_code


def test_superseded_authorization_rejected(keys) -> None:  # type: ignore[no-untyped-def]
    """A new authorization generation invalidates outstanding tickets."""
    env, contract = _envelope(), _intent()
    claims = _claims(env, contract)
    signed = TicketIssuer(keys).issue(claims)

    stale = CurrentBinding(
        **{
            **_binding(claims).__dict__,
            "authorization_generation": claims.authorization_generation + 1,
            "intent_hash": "newgen_" + claims.intent_hash[7:],
        }
    )
    with pytest.raises(TicketRejected) as err:
        _verifier(keys).verify(signed, stale)
    assert err.value.code == "AUTHORIZATION_SUPERSEDED"


def test_changed_checkout_rejected(keys) -> None:  # type: ignore[no-untyped-def]
    env, contract = _envelope(), _intent()
    claims = _claims(env, contract)
    signed = TicketIssuer(keys).issue(claims)

    drifted_hash = CurrentBinding(
        **{**_binding(claims).__dict__, "checkout_hash": "drifted" + claims.checkout_hash[7:]}
    )
    drifted_rev = CurrentBinding(**{**_binding(claims).__dict__, "checkout_revision": 2})

    for binding in (drifted_hash, drifted_rev):
        with pytest.raises(TicketRejected) as err:
            _verifier(keys).verify(signed, binding)
        assert err.value.code == "CHECKOUT_CHANGED"


def test_nonce_is_required_in_claims(keys) -> None:  # type: ignore[no-untyped-def]
    env, contract = _envelope(), _intent()
    base = _claims(env, contract).model_dump()
    del base["nonce"]
    with pytest.raises(Exception, match="nonce"):
        ExecutionTicketClaims.model_validate(base)


def test_signature_from_foreign_key_fails(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey as K

    rogue = K.generate()
    env, contract = _envelope(), _intent()
    claims = _claims(env, contract)
    payload = SignedTicket.__mro__  # silence unused warnings in strict mode
    _ = payload
    forged_hex = rogue.sign(b"whatever").hex()

    legit_keys = DevSigningKeys(
        private_path=str(tmp_path / "p.pem"), public_path=str(tmp_path / "pub.pem")
    ).ensure()
    signed = TicketIssuer(legit_keys).issue(claims)
    forged = SignedTicket(signed.claims_json, forged_hex)
    with pytest.raises(TicketRejected) as err:
        _verifier(legit_keys).verify(forged, _binding(claims))
    assert err.value.code == "SIGNATURE_INVALID"
