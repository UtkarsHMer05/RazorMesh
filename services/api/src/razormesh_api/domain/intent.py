"""IntentContract: the human-confirmed authorization that bounds all spending."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from razormesh_api.domain.ids import AgentId, IntentId, MerchantId, PrincipalId, ProductId
from razormesh_api.domain.money import Money


class IntentStatus(StrEnum):
    DRAFT = "DRAFT"
    AUTHORIZED = "AUTHORIZED"
    CHALLENGED = "CHALLENGED"
    BLOCKED = "BLOCKED"
    SUPERSEDED = "SUPERSEDED"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"


class BrandRestriction(BaseModel):
    """Structured brand constraint (free-text brand matching is Phase-3 model work)."""

    brands: frozenset[str] = Field(default_factory=frozenset)
    mode: Literal["allow_only", "forbid"] = "allow_only"


def _new_only() -> frozenset[Literal["new", "refurbished", "used"]]:
    return frozenset({"new"})


class ConditionRestriction(BaseModel):
    allowed_conditions: frozenset[Literal["new", "refurbished", "used"]] = Field(
        default_factory=_new_only
    )


AwareDatetime = Annotated[datetime, Field(...)]


def _validate_aware_utc(name: str, value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value


class IntentContract(BaseModel):
    """Human-confirmed authority. Everything here is USER_AUTHORITY by construction.

    Constraint semantics (fail-closed per SEC-018):
    - ``allowed_merchant_ids is None`` means the human explicitly authorized ANY
      merchant. An empty set authorizes nothing.
    - The same applies to product/category/brand constraints.
    """

    model_config = ConfigDict(frozen=True)

    intent_id: IntentId
    principal_id: PrincipalId
    agent_id: AgentId
    authorization_generation: int = Field(ge=1)

    status: IntentStatus = IntentStatus.AUTHORIZED

    # Allowlists (None = any explicitly authorized; empty set = nothing)
    allowed_merchant_ids: frozenset[MerchantId] | None = None
    allowed_product_ids: frozenset[ProductId] | None = None
    allowed_categories: frozenset[str] | None = None
    brand_restriction: BrandRestriction | None = None
    condition_restriction: ConditionRestriction | None = None

    currency: str = "INR"

    # Per-checkout cap and lifetime aggregate budget for this authorization.
    max_total: Money
    aggregate_budget: Money

    max_quantity: int = Field(default=1, ge=1, le=1000)

    recurring_allowed: bool = False

    # Checkouts with payable total strictly above this require re-authorization.
    approval_threshold: Money

    issued_at: datetime  # contract drafted
    authorized_at: datetime  # human confirmation moment
    expires_at: datetime  # absolute expiry of this authorization generation

    @model_validator(mode="before")
    @classmethod
    def _check_datetimes(cls, data: object) -> object:
        if isinstance(data, dict):
            for key in ("issued_at", "authorized_at", "expires_at"):
                if key in data and isinstance(data[key], datetime):
                    _validate_aware_utc(key, data[key])
        return data

    @model_validator(mode="after")
    def _check_consistency(self) -> "IntentContract":
        if self.expires_at <= self.authorized_at:
            raise ValueError("expires_at must be after authorized_at")
        if self.authorized_at < self.issued_at:
            raise ValueError("authorized_at cannot precede issued_at")

        if self.max_total.currency != self.currency:
            raise ValueError(
                f"max_total currency {self.max_total.currency} != contract currency {self.currency}"
            )
        if self.aggregate_budget.currency != self.currency:
            raise ValueError(
                f"aggregate_budget currency {self.aggregate_budget.currency} "
                f"!= contract currency {self.currency}"
            )
        if self.approval_threshold.currency != self.currency:
            raise ValueError(
                f"approval_threshold currency {self.approval_threshold.currency} "
                f"!= contract currency {self.currency}"
            )
        if self.max_total > self.aggregate_budget:
            raise ValueError("max_total cannot exceed aggregate_budget")
        if self.approval_threshold > self.max_total:
            raise ValueError("approval_threshold cannot exceed max_total")
        return self

    def is_active(self) -> bool:
        return self.status is IntentStatus.AUTHORIZED
