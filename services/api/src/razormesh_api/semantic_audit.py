"""P3-M44: tamper-evident audit events for every AI decision step.

`record_semantic_verification` appends SEMANTIC_VERIFICATION_RUN
(model/policy/probabilities/fail-closed flag) and `record_policy_fusion`
appends POLICY_FUSION_DECIDED (deterministic decision, semantic action, final,
stricten-only invariant echo). Payloads carry identifiers and numbers ONLY —
never raw premise/hypothesis text (P3-S20 secret/trust hygiene; untrusted
commerce text must not enter the ledger through the semantic path).
"""

from razormesh_api.ledger import EvidenceLedger
from razormesh_api.semantic_verifier import (
    DeterministicDecision,
    SemanticVerdict,
    fuse,
)


def record_semantic_verification(
    *,
    ledger: EvidenceLedger,
    intent_id: str,
    attempt_id: str,
    verdict: SemanticVerdict,
    actor: str = "semantic-verifier",
) -> None:
    ledger.append(
        event_type="SEMANTIC_VERIFICATION_RUN",
        actor=actor,
        intent_id=intent_id,
        payload={
            "execution_attempt_id": attempt_id,
            "model_id": verdict.model_id,
            "policy_version": verdict.policy_version,
            "p_entailment": round(verdict.p_entailment, 6),
            "p_neutral": round(verdict.p_neutral, 6),
            "p_contradiction": round(verdict.p_contradiction, 6),
            "action": verdict.action.value,
            "fail_closed": verdict.fail_closed,
            "reason": verdict.reason,
            "text_stored": False,
        },
    )


def record_policy_fusion(
    *,
    ledger: EvidenceLedger,
    intent_id: str,
    attempt_id: str,
    deterministic: DeterministicDecision,
    verdict: SemanticVerdict,
    actor: str = "semantic-fusion",
) -> DeterministicDecision:
    final = fuse(deterministic, verdict)
    ledger.append(
        event_type="POLICY_FUSION_DECIDED",
        actor=actor,
        intent_id=intent_id,
        payload={
            "execution_attempt_id": attempt_id,
            "deterministic": deterministic.value,
            "semantic_action": verdict.action.value,
            "final": final.value,
            "invariant": "semantics only STRICTEN hard decisions",
        },
    )
    return final
