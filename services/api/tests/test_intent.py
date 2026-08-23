"""M17 acceptance: IntentContract validation, serialization and fixtures."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from razormesh_api.domain.intent import BrandRestriction, IntentContract, IntentStatus
from razormesh_api.domain.money import Money


def _ts(offset_min: int) -> datetime:
    return datetime.now(UTC) + timedelta(minutes=offset_min)


def valid_contract(**overrides: object) -> dict[str, object]:
    from razormesh_api.domain.ids import new_ulid as _new_ulid

    base: dict[str, object] = {
        "intent_id": f"intent_{_new_ulid()}",
        "principal_id": "usr_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        "agent_id": "agt_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        "authorization_generation": 1,
        "status": "AUTHORIZED",
        "allowed_merchant_ids": ["mrc_01ARZ3NDEKTSV4RRFFQ69G5FAV"],
        "currency": "INR",
        "max_total": {"amount_minor": 500000, "currency": "INR"},
        "aggregate_budget": {"amount_minor": 2000000, "currency": "INR"},
        "max_quantity": 2,
        "recurring_allowed": False,
        "approval_threshold": {"amount_minor": 400000, "currency": "INR"},
        "issued_at": _ts(-10),
        "authorized_at": _ts(-5),
        "expires_at": _ts(60),
    }
    base.update(overrides)
    return base


def test_valid_contract_serializes_and_roundtrips() -> None:
    contract = IntentContract.model_validate(valid_contract())
    assert contract.status is IntentStatus.AUTHORIZED
    assert contract.is_active()

    dumped = contract.model_dump(mode="json")
    restored = IntentContract.model_validate(dumped)
    assert restored == contract
    assert restored.max_total == Money(500000)
    schema = IntentContract.model_json_schema()
    assert "authorization_generation" in schema["properties"]


def test_naive_datetimes_rejected() -> None:
    naive = datetime(2026, 1, 1, 12, 0, 0)  # no tzinfo
    with pytest.raises(ValidationError):
        IntentContract.model_validate(valid_contract(authorized_at=naive))


def test_expiry_must_be_after_authorization() -> None:
    with pytest.raises(ValidationError, match="expires_at"):
        IntentContract.model_validate(valid_contract(expires_at=_ts(-10)))


def test_max_total_cannot_exceed_budget() -> None:
    with pytest.raises(ValidationError, match="aggregate_budget"):
        IntentContract.model_validate(
            valid_contract(
                max_total={"amount_minor": 3000000, "currency": "INR"},
            )
        )


def test_currency_consistency_enforced() -> None:
    with pytest.raises(ValidationError, match="currency"):
        IntentContract.model_validate(
            valid_contract(max_total={"amount_minor": 100, "currency": "USD"})
        )


def test_generation_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        IntentContract.model_validate(valid_contract(authorization_generation=0))


def test_brand_restriction_model() -> None:
    c = IntentContract.model_validate(
        valid_contract(brand_restriction={"brands": ["Sony"], "mode": "allow_only"})
    )
    assert c.brand_restriction is not None
    assert isinstance(c.brand_restriction, BrandRestriction)
    assert "Sony" in c.brand_restriction.brands
