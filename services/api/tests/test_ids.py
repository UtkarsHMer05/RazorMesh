"""M15 acceptance: typed identifier parsing/validation."""

import pytest
from pydantic import BaseModel, ValidationError

from razormesh_api.domain.ids import (
    ALL_ID_TYPES,
    CheckoutId,
    IdentifierError,
    IntentId,
    MerchantId,
    new_ulid,
)


def test_generate_produces_valid_prefixed_ids() -> None:
    for id_type in ALL_ID_TYPES:
        ident = id_type.generate()
        assert str(ident).startswith(f"{id_type.PREFIX}_")
        assert id_type(str(ident)) == ident


def test_roundtrip_preserves_value_and_type() -> None:
    intent = IntentId.generate()
    assert IntentId(str(intent)) == intent
    assert intent.value == str(intent)
    assert hash(IntentId(str(intent))) == hash(intent)


def test_wrong_prefix_rejected() -> None:
    merchant = MerchantId.generate()
    with pytest.raises(IdentifierError):
        IntentId(str(merchant))


def test_malformed_ids_rejected() -> None:
    for bad in [
        "intent_",
        "intent_short",
        "intent_" + "0" * 25,  # too short
        "intent_" + "0" * 27,  # too long
        "intent_" + "!" * 26,  # invalid charset (I, L, O, U excluded from Crockford)
        "intent_" + "I" * 26,  # I not in alphabet
        "intent_" + new_ulid().lower(),  # lowercase rejected: canonical form only
        "intent" + "0" * 26,  # missing separator
    ]:
        with pytest.raises(IdentifierError):
            IntentId(bad)


def test_cross_type_equality_impossible() -> None:
    intent = IntentId.generate()
    checkout = CheckoutId.generate()
    assert intent != checkout
    assert intent != str(intent)
    assert intent != 123


def test_identifiers_immutable() -> None:
    intent = IntentId.generate()
    with pytest.raises(AttributeError):
        intent._value = "tampered"  # type: ignore[misc]


def test_pydantic_integration_parses_and_serializes() -> None:
    class Model(BaseModel):
        intent_id: IntentId

    m = Model(intent_id=IntentId.generate())
    assert isinstance(m.intent_id, IntentId)
    assert m.model_dump()["intent_id"] == m.intent_id.value

    valid_str = f"intent_{new_ulid()}"
    assert Model(intent_id=valid_str).intent_id.value == valid_str

    with pytest.raises(ValidationError):
        Model(intent_id="not-an-intent-id")
    with pytest.raises(ValidationError):
        Model(intent_id=12345)


def test_ulid_sortable_by_time() -> None:
    import time as _time

    first = f"intent_{new_ulid()}"
    _time.sleep(0.002)  # ULID has ms resolution; guarantee a different timestamp
    second = f"intent_{new_ulid()}"
    assert first < second
