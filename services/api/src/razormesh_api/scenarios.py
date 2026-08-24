"""M42: schema-validated synthetic attack/safety scenarios.

Every scenario declares its family, the mutation it applies to a baseline
authorized flow, and the EXPECTED security outcome. The runner (M43) executes
them against the REAL pipeline and records ACTUAL results; expected labels are
never fed into decision inputs.

Families required by the plan: safe baseline, context swap, replay,
checkout drift, approval split, provider-unknown, expired authorization.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ScenarioFamily(StrEnum):
    SAFE_BASELINE = "SAFE_BASELINE"
    SAFE_LOOKALIKE = "SAFE_LOOKALIKE"
    PRICE_DRIFT = "PRICE_DRIFT"
    MERCHANT_SUBSTITUTION = "MERCHANT_SUBSTITUTION"
    QUANTITY_MANIPULATION = "QUANTITY_MANIPULATION"
    SUBSCRIPTION_INSERTION = "SUBSCRIPTION_INSERTION"
    REPLAY = "REPLAY"
    CROSS_PRINCIPAL = "CROSS_PRINCIPAL"
    CROSS_AGENT = "CROSS_AGENT"
    CROSS_MERCHANT = "CROSS_MERCHANT"
    APPROVAL_SPLIT = "APPROVAL_SPLIT"
    AUTHORIZATION_SUPERSESSION = "AUTHORIZATION_SUPERSESSION"
    CHECKOUT_DRIFT = "CHECKOUT_DRIFT"
    UNTRUSTED_INSTRUCTION = "UNTRUSTED_INSTRUCTION"
    PROVIDER_UNKNOWN = "PROVIDER_UNKNOWN"
    EXPIRED_AUTHORIZATION = "EXPIRED_AUTHORIZATION"


class ExpectedOutcome(StrEnum):
    ALLOW_EXECUTE_ONCE = "ALLOW_EXECUTE_ONCE"
    EXECUTION_REJECTED = "EXECUTION_REJECTED"
    SINGLE_EFFECT_ONLY = "SINGLE_EFFECT_ONLY"
    STALE_DETECTED = "STALE_DETECTED"
    SPLIT_PREVENTED = "SPLIT_PREVENTED"
    NO_FRESH_OP_AFTER_UNKNOWN = "NO_FRESH_OP_AFTER_UNKNOWN"
    AUTHORITY_UNCHANGED = "AUTHORITY_UNCHANGED"


class ScenarioSpec(BaseModel):
    """Schema-validated scenario definition."""

    model_config = ConfigDict(frozen=True)

    scenario_id: str = Field(min_length=4, max_length=64, pattern=r"^[a-z0-9_\-]+$")
    family: ScenarioFamily
    description: str = Field(min_length=8, max_length=500)
    expected_outcome: ExpectedOutcome
    expected_reason_codes: tuple[str, ...] = ()
    safe_or_unsafe: str = Field(pattern=r"^(safe|unsafe)$")
    intent_fixture: str = "phase1-permissive-intent"
    initial_checkout_fixture: str = "single-synthetic-product"
    mutation: str = Field(min_length=3, max_length=200)
    synthetic_amount_minor: int = Field(default=0, ge=0)

    # Structured mutation parameters (interpreted ONLY by the runner).
    swap_principal_to: str | None = None
    replay_count: int = Field(default=1, ge=1, le=50)
    drift_field: str | None = None
    split_parts: int = Field(default=1, ge=1, le=10)

    def model_post_init(self, __context: object) -> None:
        if self.family == ScenarioFamily.CROSS_PRINCIPAL and not self.swap_principal_to:
            raise ValueError("CROSS_PRINCIPAL requires swap_principal_to")
        if self.family == ScenarioFamily.REPLAY and self.replay_count < 2:
            raise ValueError("REPLAY requires replay_count >= 2")
        if self.family == ScenarioFamily.CHECKOUT_DRIFT and not self.drift_field:
            raise ValueError("CHECKOUT_DRIFT requires drift_field")
        if self.family == ScenarioFamily.APPROVAL_SPLIT and self.split_parts < 2:
            raise ValueError("APPROVAL_SPLIT requires split_parts >= 2")


SCENARIOS: tuple[ScenarioSpec, ...] = (
    ScenarioSpec(
        scenario_id="safe-baseline-single",
        family=ScenarioFamily.SAFE_BASELINE,
        description="Fully authorized buyer buys one cheap product once.",
        expected_outcome=ExpectedOutcome.ALLOW_EXECUTE_ONCE,
        safe_or_unsafe="safe",
        mutation="none",
    ),
    ScenarioSpec(
        scenario_id="safe-lookalike-presentation-change",
        family=ScenarioFamily.SAFE_LOOKALIKE,
        description="Presentation-only merchant metadata changes after authorization.",
        expected_outcome=ExpectedOutcome.ALLOW_EXECUTE_ONCE,
        safe_or_unsafe="safe",
        mutation="change untrusted title only",
    ),
    ScenarioSpec(
        scenario_id="price-drift-after-allow",
        family=ScenarioFamily.PRICE_DRIFT,
        description="Authoritative unit price changes after ALLOW and before execution.",
        expected_outcome=ExpectedOutcome.STALE_DETECTED,
        expected_reason_codes=("STALE_CHECKOUT",),
        safe_or_unsafe="unsafe",
        mutation="increase unit_price_minor",
        drift_field="unit_price_minor",
    ),
    ScenarioSpec(
        scenario_id="merchant-substitution-after-allow",
        family=ScenarioFamily.MERCHANT_SUBSTITUTION,
        description="Durable checkout merchant changes after ALLOW.",
        expected_outcome=ExpectedOutcome.STALE_DETECTED,
        expected_reason_codes=("STALE_CHECKOUT",),
        safe_or_unsafe="unsafe",
        mutation="replace durable merchant_id",
        drift_field="merchant_id",
    ),
    ScenarioSpec(
        scenario_id="quantity-manipulation-after-allow",
        family=ScenarioFamily.QUANTITY_MANIPULATION,
        description="Checkout quantity increases after ALLOW.",
        expected_outcome=ExpectedOutcome.STALE_DETECTED,
        expected_reason_codes=("STALE_CHECKOUT",),
        safe_or_unsafe="unsafe",
        mutation="increase quantity",
        drift_field="quantity",
    ),
    ScenarioSpec(
        scenario_id="subscription-insertion-after-allow",
        family=ScenarioFamily.SUBSCRIPTION_INSERTION,
        description="Recurring monthly terms appear after ALLOW.",
        expected_outcome=ExpectedOutcome.STALE_DETECTED,
        expected_reason_codes=("STALE_CHECKOUT",),
        safe_or_unsafe="unsafe",
        mutation="insert recurring subscription terms",
        drift_field="subscription_terms",
    ),
    ScenarioSpec(
        scenario_id="context-swap-principal",
        family=ScenarioFamily.CROSS_PRINCIPAL,
        description="Attacker replays a valid ticket under a different principal id.",
        expected_outcome=ExpectedOutcome.EXECUTION_REJECTED,
        expected_reason_codes=("PRINCIPAL_MISMATCH",),
        safe_or_unsafe="unsafe",
        mutation="replace principal execution context",
        swap_principal_to="usr_attacker",
    ),
    ScenarioSpec(
        scenario_id="context-swap-agent",
        family=ScenarioFamily.CROSS_AGENT,
        description="A different agent attempts to use the signed ticket.",
        expected_outcome=ExpectedOutcome.EXECUTION_REJECTED,
        expected_reason_codes=("AGENT_MISMATCH",),
        safe_or_unsafe="unsafe",
        mutation="replace agent execution context",
    ),
    ScenarioSpec(
        scenario_id="context-swap-merchant",
        family=ScenarioFamily.CROSS_MERCHANT,
        description="Ticket for one merchant is presented under another merchant context.",
        expected_outcome=ExpectedOutcome.EXECUTION_REJECTED,
        expected_reason_codes=("MERCHANT_MISMATCH",),
        safe_or_unsafe="unsafe",
        mutation="replace merchant execution context",
    ),
    ScenarioSpec(
        scenario_id="replay-same-ticket-five-times",
        family=ScenarioFamily.REPLAY,
        description="Same ticket submitted five times; nonce must cap effects at one.",
        expected_outcome=ExpectedOutcome.SINGLE_EFFECT_ONLY,
        safe_or_unsafe="unsafe",
        mutation="submit same ticket five times",
        replay_count=5,
    ),
    ScenarioSpec(
        scenario_id="checkout-drift-quantity",
        family=ScenarioFamily.CHECKOUT_DRIFT,
        description="Checkout quantity mutated after decision; ticket must die.",
        expected_outcome=ExpectedOutcome.STALE_DETECTED,
        safe_or_unsafe="unsafe",
        mutation="change checkout quantity and product identity",
        drift_field="quantity",
    ),
    ScenarioSpec(
        scenario_id="approval-split-three-under-threshold",
        family=ScenarioFamily.APPROVAL_SPLIT,
        description="Split one over-threshold purchase into three just-under pieces.",
        expected_outcome=ExpectedOutcome.SPLIT_PREVENTED,
        safe_or_unsafe="unsafe",
        mutation="split aggregate amount across three executions",
        split_parts=3,
    ),
    ScenarioSpec(
        scenario_id="authorization-generation-superseded",
        family=ScenarioFamily.AUTHORIZATION_SUPERSESSION,
        description="Authorization generation changes after ticket issuance.",
        expected_outcome=ExpectedOutcome.EXECUTION_REJECTED,
        expected_reason_codes=("AUTHORIZATION_SUPERSEDED",),
        safe_or_unsafe="unsafe",
        mutation="increment authorization_generation",
    ),
    ScenarioSpec(
        scenario_id="untrusted-instruction-remains-data",
        family=ScenarioFamily.UNTRUSTED_INSTRUCTION,
        description="Merchant title asks the agent to ignore human authority.",
        expected_outcome=ExpectedOutcome.AUTHORITY_UNCHANGED,
        safe_or_unsafe="unsafe",
        mutation="inject prompt-like untrusted merchant title",
    ),
    ScenarioSpec(
        scenario_id="provider-unknown-no-fresh-op",
        family=ScenarioFamily.PROVIDER_UNKNOWN,
        description="Provider times out post-send; retry must never double-charge.",
        expected_outcome=ExpectedOutcome.NO_FRESH_OP_AFTER_UNKNOWN,
        safe_or_unsafe="unsafe",
        mutation="timeout after provider effect then repeat request",
    ),
    ScenarioSpec(
        scenario_id="expired-authorization-reuse",
        family=ScenarioFamily.EXPIRED_AUTHORIZATION,
        description="Ticket presented after authorization expiry window.",
        expected_outcome=ExpectedOutcome.EXECUTION_REJECTED,
        expected_reason_codes=("AUTHORIZATION_EXPIRED",),
        safe_or_unsafe="unsafe",
        mutation="advance authorization beyond expiry",
    ),
)


REQUIRED_FAMILIES: set[ScenarioFamily] = set(ScenarioFamily)


def validate_registry() -> list[str]:
    problems: list[str] = []
    ids = [s.scenario_id for s in SCENARIOS]
    if len(set(ids)) != len(ids):
        problems.append("duplicate scenario ids")
    present = {s.family for s in SCENARIOS}
    missing = REQUIRED_FAMILIES - present
    if missing:
        problems.append(f"missing families: {sorted(m.value for m in missing)}")
    return problems
