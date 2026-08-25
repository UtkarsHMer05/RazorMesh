"""P3-M11: IntentDraft schema — strict money, no invented defaults, bounds."""

import re
from datetime import UTC, datetime

import pytest
from hypothesis import given
from hypothesis import settings as hyp_settings
from hypothesis import strategies as st
from pydantic import ValidationError

from razormesh_api.domain.intent_draft import (
    SCHEMA_VERSION_VALUE,
    Ambiguity,
    CompilerIntentPayload,
    HardConstraints,
    IntentDraft,
    MoneyBound,
    SemanticConstraint,
    UnspecifiedField,
)

_VALID_DRAFT = CompilerIntentPayload(
    schema_version=SCHEMA_VERSION_VALUE,
    product_summary="wireless headphones",
    hard=HardConstraints(
        max_amount=MoneyBound(amount_minor=500_000, currency="INR"),
        quantity_max=2,
        recurring_forbidden=True,
    ),
    semantic_constraints=(
        SemanticConstraint(text="The product must be brand new.", family_hint="condition"),
    ),
    ambiguities=(
        Ambiguity(question="Wired or wireless acceptable?", options=("wired", "wireless")),
    ),
    unspecified=(UnspecifiedField(field="merchant"),),
)


def test_valid_draft_round_trips() -> None:
    dumped = _VALID_DRAFT.model_dump()
    again = CompilerIntentPayload.model_validate(dumped)
    assert again == _VALID_DRAFT
    assert _VALID_DRAFT.schema_version == SCHEMA_VERSION_VALUE


def test_defaults_are_none_never_invented() -> None:
    bare = CompilerIntentPayload(schema_version=SCHEMA_VERSION_VALUE, product_summary="coffee")
    assert bare.hard.max_amount is None  # no implicit budget
    assert bare.hard.brand_allowlist == ()  # no implicit brand
    assert bare.hard.recurring_forbidden is None  # no implicit no-subscription
    assert bare.semantic_constraints == ()
    assert bare.unspecified == ()


def test_float_money_rejected_even_if_integral() -> None:
    with pytest.raises(ValidationError):
        MoneyBound(amount_minor=500.0, currency="INR")  # type: ignore[arg-type]


def test_bool_money_rejected() -> None:
    with pytest.raises(ValidationError):
        MoneyBound(amount_minor=True, currency="INR")  # type: ignore[arg-type]


def test_zero_and_negative_money_rejected() -> None:
    for bad in (0, -1):
        with pytest.raises(ValidationError):
            MoneyBound(amount_minor=bad, currency="INR")


def test_lowercase_currency_rejected() -> None:
    with pytest.raises(ValidationError):
        MoneyBound(amount_minor=100, currency="inr")


@pytest.mark.parametrize("extra", [{"currency": "USD"}])
def test_extra_keys_forbidden_on_hard(extra: dict) -> None:
    with pytest.raises(ValidationError):
        HardConstraints(max_amount=MoneyBound(amount_minor=1, currency="INR"), **extra)  # type: ignore[arg-type]


def test_wrong_schema_version_rejected() -> None:
    with pytest.raises(ValidationError):
        CompilerIntentPayload(schema_version="agentpay-intent-draft-v2", product_summary="x")


def test_oversized_text_rejected() -> None:
    with pytest.raises(ValidationError):
        SemanticConstraint(text="x" * 281)
    ok = SemanticConstraint(text="y" * 280)
    assert len(ok.text) == 280


def test_empty_semantic_text_rejected() -> None:
    with pytest.raises(ValidationError):
        SemanticConstraint(text="ab")


def test_too_many_allowlist_items_rejected() -> None:
    with pytest.raises(ValidationError):
        HardConstraints(
            max_amount=MoneyBound(amount_minor=1, currency="INR"),
            brand_allowlist=tuple(f"b{i}" for i in range(9)),
        )


def test_unknown_unspecified_field_rejected() -> None:
    with pytest.raises(ValidationError):
        UnspecifiedField(field="color")


def test_ambiguity_option_bounds() -> None:
    with pytest.raises(ValidationError):
        Ambiguity(question="Which one exactly??", options=tuple(f"o{i}" for i in range(7)))


def test_durable_wrapper_requires_server_identity() -> None:
    draft = IntentDraft(
        **_VALID_DRAFT.model_dump(),
        draft_id="drf_" + "0" * 26,
        source_text_sha256="a" * 64,
        created_at=datetime.now(UTC),
    )
    assert re.match(r"^drf_[0-9A-Z]{26}$", draft.draft_id)
    with pytest.raises(ValidationError):
        IntentDraft(
            **_VALID_DRAFT.model_dump(),
            draft_id="attacker-chosen-id",
            source_text_sha256="a" * 64,
            created_at=datetime.now(UTC),
        )


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------

_money = st.integers(min_value=1, max_value=10_000_000_000)
_currency = st.sampled_from(["INR", "USD", "EUR"])
_text = st.text(
    alphabet=st.characters(min_codepoint=32, max_codepoint=0x2FFF), min_size=3, max_size=200
).filter(lambda s: s.strip() == s and "\n" not in s)


@hyp_settings(max_examples=100, deadline=None)
@given(amount=_money, currency=_currency, qty=st.integers(min_value=1, max_value=999))
def test_hard_constraints_round_trip_property(amount: int, currency: str, qty: int) -> None:
    hc = HardConstraints(
        max_amount=MoneyBound(amount_minor=amount, currency=currency), quantity_max=qty
    )
    again = HardConstraints.model_validate(hc.model_dump())
    assert again == hc
    assert again.max_amount is not None and again.max_amount.amount_minor == amount


@hyp_settings(max_examples=60, deadline=None)
@given(text=_text)
def test_semantic_constraint_accepts_bounded_unicode(text: str) -> None:
    sc = SemanticConstraint(text=text.strip())
    assert SemanticConstraint.model_validate(sc.model_dump()) == sc
