"""M27: composable deterministic RazorGuard rule engine foundation.

Every rule is a pure function of its evaluation context and returns one of:

- PASS    the rule is satisfied;
- FAIL    the proposed transaction violates this rule (reason codes explain);
- UNKNOWN the rule cannot decide on the given inputs — treated as fail-closed
          by the decision engine (never silently allowed).

No randomness, no network, no ML scores: identical input yields an identical
report, byte for byte.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol

from razormesh_api.domain.checkout import CheckoutEnvelope
from razormesh_api.domain.intent import IntentContract


class RuleOutcome(StrEnum):
    PASS = "PASS"  # noqa: S105 - outcome label, not a credential
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ProductFacts:
    """Structured facts resolved by the TRUSTED system (never merchant text).

    A ``None`` field means 'fact unavailable' — rules that need it must return
    UNKNOWN rather than guess.
    """

    brand: str | None = None
    category: str | None = None


@dataclass(frozen=True)
class EvaluationContext:
    intent: IntentContract
    checkout: CheckoutEnvelope
    committed_minor: int = 0  # durable spend already committed against authority
    reserved_minor: int = 0  # open reservations held against authority
    product_facts: dict[str, ProductFacts] | None = None  # trusted catalog facts


@dataclass(frozen=True)
class RuleResult:
    rule_id: str
    outcome: str  # PASS | FAIL | UNKNOWN
    reason_codes: tuple[str, ...] = ()
    explanation: str = ""
    details: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.outcome not in (RuleOutcome.PASS, RuleOutcome.FAIL, RuleOutcome.UNKNOWN):
            raise ValueError(f"invalid rule outcome: {self.outcome}")


class Rule(Protocol):
    @property
    def rule_id(self) -> str: ...

    def evaluate(self, ctx: EvaluationContext) -> RuleResult: ...


class FunctionRule:
    """Adapt a plain callable into a Rule."""

    def __init__(
        self,
        rule_id: str,
        fn: "Callable[[EvaluationContext], RuleResult]",
    ) -> None:
        self._rule_id = rule_id
        self._fn = fn

    @property
    def rule_id(self) -> str:
        return self._rule_id

    def evaluate(self, ctx: EvaluationContext) -> RuleResult:
        return self._fn(ctx)


def _safe(rule: Rule, ctx: EvaluationContext) -> RuleResult:
    """A crashing rule degrades to UNKNOWN (fail-closed), never to PASS."""
    try:
        return rule.evaluate(ctx)
    except Exception as exc:  # noqa: BLE001 - fail-closed by design
        return RuleResult(
            rule_id=rule.rule_id,
            outcome=RuleOutcome.UNKNOWN,
            reason_codes=("RULE_ERROR",),
            explanation=f"rule raised {type(exc).__name__}; failing closed",
        )


class AllOf:
    """Composite rule: passes only when every child passes; first FAIL wins."""

    def __init__(self, rule_id: str, rules: Sequence[Rule]) -> None:
        if not rules:
            raise ValueError("AllOf requires at least one child rule")
        self._rule_id = rule_id
        self._rules = tuple(rules)

    @property
    def rule_id(self) -> str:
        return self._rule_id

    def evaluate(self, ctx: EvaluationContext) -> RuleResult:
        failures: list[RuleResult] = []
        unknowns: list[RuleResult] = []
        for rule in self._rules:
            result = _safe(rule, ctx)
            if result.outcome == RuleOutcome.FAIL:
                failures.append(result)
            elif result.outcome == RuleOutcome.UNKNOWN:
                unknowns.append(result)
        if failures:
            reasons = tuple(rc for r in failures for rc in r.reason_codes)
            return RuleResult(
                rule_id=self._rule_id,
                outcome=RuleOutcome.FAIL,
                reason_codes=reasons or ("RULE_FAILED",),
                explanation="; ".join(r.explanation for r in failures if r.explanation),
                details={"failed_rules": [r.rule_id for r in failures]},
            )
        if unknowns:
            return RuleResult(
                rule_id=self._rule_id,
                outcome=RuleOutcome.UNKNOWN,
                reason_codes=tuple(rc for r in unknowns for rc in r.reason_codes)
                or ("RULE_UNKNOWN",),
                explanation="one or more sub-rules could not decide",
                details={"unknown_rules": [r.rule_id for r in unknowns]},
            )
        return RuleResult(
            rule_id=self._rule_id,
            outcome=RuleOutcome.PASS,
            explanation=f"all {len(self._rules)} sub-rules passed",
        )


@dataclass(frozen=True)
class EvaluationReport:
    results: tuple[RuleResult, ...]

    @property
    def failed(self) -> tuple[RuleResult, ...]:
        return tuple(r for r in self.results if r.outcome == RuleOutcome.FAIL)

    @property
    def unknown(self) -> tuple[RuleResult, ...]:
        return tuple(r for r in self.results if r.outcome == RuleOutcome.UNKNOWN)

    @property
    def passed(self) -> bool:
        return not self.failed and not self.unknown

    @property
    def reason_codes(self) -> tuple[str, ...]:
        return tuple(
            rc for r in self.results if r.outcome != RuleOutcome.PASS for rc in r.reason_codes
        )


class RazorGuardEngine:
    """Deterministic rule pipeline. Order of rules is preserved in the report."""

    def __init__(self, rules: Sequence[Rule]) -> None:
        if not rules:
            raise ValueError("RazorGuardEngine requires at least one rule")
        seen = {r.rule_id for r in rules}
        if len(seen) != len(rules):
            raise ValueError("duplicate rule ids are forbidden")
        self._rules = tuple(rules)

    def evaluate(self, ctx: EvaluationContext) -> EvaluationReport:
        return EvaluationReport(results=tuple(_safe(r, ctx) for r in self._rules))
