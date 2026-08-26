"""P3-M41: Security Lab — Phase-3 SEMANTIC scenario suite (synthetic only).

Each scenario drives the REAL policy rule + fusion over a FAKE scorer
(no model download, no network). Expected outcomes encode trust semantics:

- injected product text can never raise an ALLOW;
- disguised renewals are caught by calibrated contradiction thresholds;
- safe lookalikes stay ALLOW/CHALLENGE-free (false-positive guard);
- deterministic CHALLENGE never becomes ALLOW just because semantics PASS.
"""

from dataclasses import dataclass

from razormesh_api.semantic_verifier import (
    DeterministicDecision,
    SemanticVerdict,
    apply_threshold_policy,
    fuse,
)

TAU_BLOCK = 0.36
TAU_ENTAIL = 0.40


@dataclass(frozen=True)
class SemanticScenario:
    scenario_id: str
    family: str
    description: str
    deterministic: DeterministicDecision
    p_entailment: float
    p_neutral: float
    p_contradiction: float
    expect_final: str


SCENARIOS: tuple[SemanticScenario, ...] = (
    SemanticScenario(
        "sem-injection-price-hike",
        "injection_resistance",
        "Product text tries to redefine the budget; verifier sees high contradiction.",
        DeterministicDecision.ALLOW,
        0.05,
        0.05,
        0.90,
        "BLOCK",
    ),
    SemanticScenario(
        "sem-disguised-renewal",
        "trial_renewal_trap",
        "'Free concierge continues at ₹499/month' against a no-recurring authorization.",
        DeterministicDecision.ALLOW,
        0.10,
        0.10,
        0.80,
        "BLOCK",
    ),
    SemanticScenario(
        "sem-safe-lookalike-title",
        "safe_lookalike",
        "Aggressive marketing title, benign terms; must NOT be blocked.",
        DeterministicDecision.ALLOW,
        0.75,
        0.20,
        0.05,
        "ALLOW",
    ),
    SemanticScenario(
        "sem-hard-challenge-stays",
        "policy_supremacy",
        "Deterministic CHALLENGE with perfect semantic PASS stays CHALLENGE.",
        DeterministicDecision.CHALLENGE,
        0.99,
        0.005,
        0.005,
        "CHALLENGE",
    ),
    SemanticScenario(
        "sem-hard-block-supreme",
        "policy_supremacy",
        "Deterministic BLOCK cannot be lifted even by perfect entailment.",
        DeterministicDecision.BLOCK,
        1.00 - 1e-6,
        1e-7,
        1e-7,
        "BLOCK",
    ),
)


def run_semantic_scenarios(
    records: tuple[SemanticScenario, ...] = SCENARIOS,
) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for s in records:
        action = apply_threshold_policy(
            p_entailment=s.p_entailment,
            p_neutral=s.p_neutral,
            p_contradiction=s.p_contradiction,
            tau_block=TAU_BLOCK,
            tau_entail=TAU_ENTAIL,
        )
        verdict = SemanticVerdict(
            action=action,
            p_entailment=s.p_entailment,
            p_neutral=s.p_neutral,
            p_contradiction=s.p_contradiction,
            model_id="semantic-lab-fake-scorer",
            policy_version="lab",
        )
        final = fuse(s.deterministic, verdict)
        results.append(
            {
                "scenario_id": s.scenario_id,
                "family": s.family,
                "passed": final.value == s.expect_final,
                "final": final.value,
                "expected": s.expect_final,
            }
        )
    return results
