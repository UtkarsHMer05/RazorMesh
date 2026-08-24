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
    CONTEXT_SWAP = "CONTEXT_SWAP"
    REPLAY = "REPLAY"
    CHECKOUT_DRIFT = "CHECKOUT_DRIFT"
    APPROVAL_SPLIT = "APPROVAL_SPLIT"
    PROVIDER_UNKNOWN = "PROVIDER_UNKNOWN"
    EXPIRED_AUTHORIZATION = "EXPIRED_AUTHORIZATION"


class ExpectedOutcome(StrEnum):
    ALLOW_EXECUTE_ONCE = "ALLOW_EXECUTE_ONCE"
    EXECUTION_REJECTED = "EXECUTION_REJECTED"
    SINGLE_EFFECT_ONLY = "SINGLE_EFFECT_ONLY"
    STALE_DETECTED = "STALE_DETECTED"
    SPLIT_PREVENTED = "SPLIT_PREVENTED"
    NO_FRESH_OP_AFTER_UNKNOWN = "NO_FRESH_OP_AFTER_UNKNOWN"


class ScenarioSpec(BaseModel):
    """Schema-validated scenario definition."""

    model_config = ConfigDict(frozen=True)

    scenario_id: str = Field(min_length=4, max_length=64, pattern=r"^[a-z0-9_\-]+$")
    family: ScenarioFamily
    description: str = Field(min_length=8, max_length=500)
    expected_outcome: ExpectedOutcome

    # Structured mutation parameters (interpreted ONLY by the runner).
    swap_principal_to: str | None = None
    replay_count: int = Field(default=1, ge=1, le=50)
    drift_field: str | None = None
    split_parts: int = Field(default=1, ge=1, le=10)

    def model_post_init(self, __context: object) -> None:
        if self.family == ScenarioFamily.CONTEXT_SWAP and not self.swap_principal_to:
            raise ValueError("CONTEXT_SWAP requires swap_principal_to")
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
    ),
    ScenarioSpec(
        scenario_id="context-swap-principal",
        family=ScenarioFamily.CONTEXT_SWAP,
        description="Attacker replays a valid ticket under a different principal id.",
        expected_outcome=ExpectedOutcome.EXECUTION_REJECTED,
        swap_principal_to="usr_attacker",
    ),
    ScenarioSpec(
        scenario_id="replay-same-ticket-five-times",
        family=ScenarioFamily.REPLAY,
        description="Same ticket submitted five times; nonce must cap effects at one.",
        expected_outcome=ExpectedOutcome.SINGLE_EFFECT_ONLY,
        replay_count=5,
    ),
    ScenarioSpec(
        scenario_id="checkout-drift-quantity",
        family=ScenarioFamily.CHECKOUT_DRIFT,
        description="Checkout quantity mutated after decision; ticket must die.",
        expected_outcome=ExpectedOutcome.STALE_DETECTED,
        drift_field="quantity",
    ),
    ScenarioSpec(
        scenario_id="approval-split-three-under-threshold",
        family=ScenarioFamily.APPROVAL_SPLIT,
        description="Split one over-threshold purchase into three just-under pieces.",
        expected_outcome=ExpectedOutcome.SPLIT_PREVENTED,
        split_parts=3,
    ),
    ScenarioSpec(
        scenario_id="provider-unknown-no-fresh-op",
        family=ScenarioFamily.PROVIDER_UNKNOWN,
        description="Provider times out post-send; retry must never double-charge.",
        expected_outcome=ExpectedOutcome.NO_FRESH_OP_AFTER_UNKNOWN,
    ),
    ScenarioSpec(
        scenario_id="expired-authorization-reuse",
        family=ScenarioFamily.EXPIRED_AUTHORIZATION,
        description="Ticket presented after authorization expiry window.",
        expected_outcome=ExpectedOutcome.EXECUTION_REJECTED,
    ),
)


REQUIRED_FAMILIES: set[ScenarioFamily] = {
    f
    for f in ScenarioFamily
    if f != ScenarioFamily.__members__  # placeholder-safe
} - set()


def validate_registry() -> list[str]:
    problems: list[str] = []
    ids = [s.scenario_id for s in SCENARIOS]
    if len(set(ids)) != len(ids):
        problems.append("duplicate scenario ids")
    present = {s.family for s in SCENARIOS}
    missing = set(ScenarioFamily) - present
    if missing:
        problems.append(f"missing families: {sorted(m.value for m in missing)}")
    return problems
