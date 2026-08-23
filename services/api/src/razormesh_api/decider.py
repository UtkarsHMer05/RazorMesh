"""M32: deterministic decision engine — ALLOW / CHALLENGE / BLOCK matrix.

Combination rules (evaluated in order, first match decides):

1. Intent status is not AUTHORIZED                    -> BLOCK  (state gate)
2. Any rule result FAIL                               -> BLOCK  (hard violation)
3. Any rule result UNKNOWN                            -> CHALLENGE
   (fail-closed step-up; e.g. APPROVAL_REQUIRED or unknown catalog facts)
4. Otherwise                                          -> ALLOW

No machine-learning scores, no randomness: identical input yields an identical
decision. BLOCK and CHALLENGE can never execute (SEC invariants); only an
ALLOW feeds ticket issuance.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from razormesh_api.domain.checkout import CheckoutEnvelope
from razormesh_api.domain.intent import IntentContract
from razormesh_api.domain.state_machine import (
    AuthorizationStatus,
    NotExecutableError,
    assert_executable,
)
from razormesh_api.rules.engine import (
    EvaluationContext,
    Rule,
    RuleOutcome,
    RuleResult,
    safe_evaluate,
)

POLICY_VERSION = "razormesh-phase1-policy-v1"


class Decision(StrEnum):
    ALLOW = "ALLOW"
    CHALLENGE = "CHALLENGE"
    BLOCK = "BLOCK"


@dataclass(frozen=True)
class DecisionOutcome:
    decision: Decision
    reason_codes: tuple[str, ...]
    rule_results: tuple[RuleResult, ...]
    policy_version: str = POLICY_VERSION


def _status_of(intent: IntentContract) -> AuthorizationStatus:
    return AuthorizationStatus(intent.status.value)


class DecisionEngine:
    def __init__(self, rules: Sequence[Rule]) -> None:
        if not rules:
            raise ValueError("DecisionEngine requires at least one rule")
        seen = {r.rule_id for r in rules}
        if len(seen) != len(rules):
            raise ValueError("duplicate rule ids are forbidden")
        self._rules = tuple(rules)

    def decide(
        self,
        *,
        intent: IntentContract,
        checkout: CheckoutEnvelope,
        ctx: EvaluationContext | None = None,
    ) -> DecisionOutcome:
        context = ctx if ctx is not None else EvaluationContext(intent=intent, checkout=checkout)
        results = tuple(safe_evaluate(rule, context) for rule in self._rules)

        # 1. State gate: only an active AUTHORIZED generation may proceed.
        try:
            assert_executable(_status_of(intent))
        except NotExecutableError:
            return DecisionOutcome(
                decision=Decision.BLOCK,
                reason_codes=("STATUS_NOT_EXECUTABLE", intent.status.value),
                rule_results=results,
            )

        # 2. Hard violations block.
        failed = [r for r in results if r.outcome == RuleOutcome.FAIL]
        if failed:
            return DecisionOutcome(
                decision=Decision.BLOCK,
                reason_codes=tuple(rc for r in failed for rc in r.reason_codes) or ("RULE_FAILED",),
                rule_results=results,
            )

        # 3. Undecidable/step-up requirements challenge.
        unknown = [r for r in results if r.outcome == RuleOutcome.UNKNOWN]
        if unknown:
            return DecisionOutcome(
                decision=Decision.CHALLENGE,
                reason_codes=tuple(rc for r in unknown for rc in r.reason_codes)
                or ("RULE_UNKNOWN",),
                rule_results=results,
            )

        # 4. Everything passed.
        return DecisionOutcome(decision=Decision.ALLOW, reason_codes=(), rule_results=results)
