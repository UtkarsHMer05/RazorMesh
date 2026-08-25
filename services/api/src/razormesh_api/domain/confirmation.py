"""P3-M16 (D-042): human confirmation domain flow.

An AI-produced IntentDraft is a PROPOSAL, never authority (P3-S03). This module
defines the durable draft state machine and the single fail-closed mapping from
a CONFIRMED draft to IntentContract terms:

- DRAFT / NEEDS_CLARIFICATION are reviewable; only a non-superseded DRAFT can
  be confirmed; CONFIRMED / REJECTED are terminal.
- A fresh compile that still carries ambiguities lands in NEEDS_CLARIFICATION:
  it cannot be confirmed until the human clarifies (a new compile supersedes
  it).
- Authority materialization is fail-closed: no stated money -> no authority;
  nothing permissive is ever invented (aggregate budget/approval threshold
  default TO the stated cap, quantity to 1, recurring to forbidden unless the
  human explicitly allowed it).
"""

from datetime import UTC, datetime, timedelta
from enum import StrEnum

from razormesh_api.domain.ids import AgentId, IntentId, PrincipalId
from razormesh_api.domain.intent import (
    BrandRestriction,
    ConditionRestriction,
    IntentContract,
    IntentStatus,
)
from razormesh_api.domain.intent_draft import CompilerIntentPayload
from razormesh_api.domain.money import CURRENCY_EXPONENTS, Money

# A confirmed authorization generation is short-lived by design; re-authorization
# after expiry requires a fresh human confirmation.
AUTHORIZATION_TTL = timedelta(hours=24)


class DraftState(StrEnum):
    DRAFT = "DRAFT"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"


REJECTABLE_STATES = frozenset({DraftState.DRAFT, DraftState.NEEDS_CLARIFICATION})
TERMINAL_STATES = frozenset({DraftState.CONFIRMED, DraftState.REJECTED})


class ConfirmationError(Exception):
    """Fail-closed refusal in the confirmation flow; ``code`` is stable."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def initial_state_for(payload: CompilerIntentPayload) -> DraftState:
    """A compile with unresolved ambiguities is not confirmable as-is."""
    return DraftState.NEEDS_CLARIFICATION if payload.ambiguities else DraftState.DRAFT


def build_confirmed_contract(
    payload: CompilerIntentPayload,
    *,
    principal_id: PrincipalId,
    agent_id: AgentId,
    intent_id: IntentId,
    generation: int,
    now: datetime,
) -> IntentContract:
    """Deterministic fail-closed mapping of a CONFIRMED draft to contract terms.

    Raises ConfirmationError when the draft cannot ground authority (no stated
    money, or a currency the trust core does not support). Never invents
    permissive terms.
    """
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    max_amount = payload.hard.max_amount
    if max_amount is None:
        raise ConfirmationError(
            "DRAFT_MISSING_MONEY",
            "draft states no maximum amount; cannot create bounded authority",
        )
    if max_amount.currency not in CURRENCY_EXPONENTS:
        raise ConfirmationError(
            "DRAFT_UNSUPPORTED_CURRENCY",
            f"currency {max_amount.currency} is not supported by the trust core",
        )

    cap = Money(max_amount.amount_minor, max_amount.currency)
    brand_names = tuple(b.casefold() for b in payload.hard.brand_allowlist)
    return IntentContract(
        intent_id=intent_id,
        principal_id=principal_id,
        agent_id=agent_id,
        authorization_generation=generation,
        status=IntentStatus.AUTHORIZED,
        allowed_merchant_ids=None,  # merchant names stay semantic-layer work (D-042)
        allowed_product_ids=None,
        allowed_categories=None,
        brand_restriction=(
            BrandRestriction(brands=frozenset(brand_names), mode="allow_only")
            if brand_names
            else None
        ),
        condition_restriction=(
            ConditionRestriction(allowed_conditions=frozenset(payload.hard.condition_allowlist))
            if payload.hard.condition_allowlist
            else None
        ),
        currency=cap.currency,
        max_total=cap,
        aggregate_budget=cap,  # no invented larger lifetime budget
        max_quantity=payload.hard.quantity_max or 1,
        recurring_allowed=payload.hard.recurring_forbidden is False,
        approval_threshold=cap,
        issued_at=now.astimezone(UTC),
        authorized_at=now.astimezone(UTC),
        expires_at=(now + AUTHORIZATION_TTL).astimezone(UTC),
    )
