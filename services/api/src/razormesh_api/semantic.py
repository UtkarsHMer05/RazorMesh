"""M41: future semantic-verification interface (NO model dependency in Phase 1).

Defines the seam where a real semantic risk model will plug in during a later
phase. Phase 1 ships only:

- ``NullSemanticVerifier``      production Phase-1 default: always UNDECIDED;
- ``DeterministicKeywordVerifier``  a fully deterministic TEST double.

The rule adapter converts assessments to the RazorGuard matrix:

    SAFE      -> rule PASS
    UNSAFE    -> rule FAIL  (SEMANTIC_UNSAFE)
    UNDECIDED -> rule UNKNOWN (fail-closed; blocks ALLOW downstream)

No transformers/torch/onnx dependency may be introduced in Phase 1.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from razormesh_api.rules.engine import (
    EvaluationContext,
    FunctionRule,
    RuleOutcome,
    RuleResult,
)


class SemanticVerdict(StrEnum):
    SAFE = "SAFE"
    UNSAFE = "UNSAFE"
    UNDECIDED = "UNDECIDED"


@dataclass(frozen=True)
class SemanticAssessment:
    verdict: SemanticVerdict
    explanation: str = ""


class SemanticVerifier(Protocol):
    def assess(self, texts: tuple[str, ...]) -> SemanticAssessment: ...


class NullSemanticVerifier:
    """Phase-1 default: cannot decide; downstream must fail closed."""

    def assess(self, texts: tuple[str, ...]) -> SemanticAssessment:
        return SemanticAssessment(
            verdict=SemanticVerdict.UNDECIDED,
            explanation="no semantic model configured in Phase 1",
        )


class DeterministicKeywordVerifier:
    """Deterministic test double: flags exact banned substrings (case-insensitive)."""

    BANNED = (
        "guaranteed profit",
        "wire transfer only",
        "ignore previous instructions",
        "send credentials",
    )

    def __init__(self, banned: tuple[str, ...] = BANNED) -> None:
        self._banned = tuple(b.lower() for b in banned)

    def assess(self, texts: tuple[str, ...]) -> SemanticAssessment:
        joined = " \n ".join(texts).lower()
        for phrase in self._banned:
            if phrase in joined:
                return SemanticAssessment(
                    verdict=SemanticVerdict.UNSAFE,
                    explanation=f"banned pattern present: {phrase!r}",
                )
        return SemanticAssessment(
            verdict=SemanticVerdict.SAFE, explanation="no banned pattern present"
        )


def semantic_rule(verifier: SemanticVerifier) -> FunctionRule:
    """Adapt any SemanticVerifier into a RazorGuard rule (fail-closed)."""

    def _view(ctx: EvaluationContext) -> RuleResult:
        texts = tuple(i.display_name.value.text for i in ctx.checkout.line_items)
        assessment = verifier.assess(texts)
        if assessment.verdict == SemanticVerdict.SAFE:
            return RuleResult(rule_id="semantic.verifier", outcome=RuleOutcome.PASS)
        if assessment.verdict == SemanticVerdict.UNSAFE:
            return RuleResult(
                rule_id="semantic.verifier",
                outcome=RuleOutcome.FAIL,
                reason_codes=("SEMANTIC_UNSAFE",),
                explanation=assessment.explanation,
            )
        return RuleResult(
            rule_id="semantic.verifier",
            outcome=RuleOutcome.UNKNOWN,
            reason_codes=("SEMANTIC_UNDECIDED",),
            explanation=assessment.explanation,
        )

    return FunctionRule("semantic.verifier", _view)
