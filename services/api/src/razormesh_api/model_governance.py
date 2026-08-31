"""Phase-5 (M091-M094): Model Governance API — active vs challenger truth.

Contract (D-055/D-056, master prompt §13.9):
- The ACTIVE semantic runtime is the PRE_V2 verifier (backend deberta,
  phase3-finetuned-v2, semantic-thresholds-v3). It stays active.
- The v2 candidate was evaluated ONCE on frozen data and NOT ACTIVATED by the
  safety gate. It is NEVER authoritative: no fusion, no tickets, no provider.
- All metrics below are committed evidence values (DECISIONS.md D-055 +
  docs/agentpay_ir_v2/FINAL_FROZEN_EVALUATION). This API projects them
  read-only; it never reruns frozen evaluation and never recalibrates.
- Optional shadow mode (M093) runs the challenger on NEW NON-FROZEN demo text
  only, marked NON-AUTHORITATIVE, and never enters fusion.
"""

from __future__ import annotations

import json
from typing import Any

from razormesh_api.settings import get_settings

# Committed evidence (D-055, 2026-08-30). These are frozen facts, not live
# measurements: changing them would falsify the governance record.
_ACTIVE = {
    "label": "Active Safety Model",
    "status": "ACTIVE — accepted by the frozen safety gate",
    "backend": "deberta (PRE_V2 runtime)",
    "model": "phase3-finetuned-v2",
    "policy_version": "semantic-thresholds-v3",
    "role": "Used for the live semantic trust check",
    "can_authorize_payment": False,
    "note": "Semantics can only tighten RazorGuard decisions; they never issue tickets.",
}

_CHALLENGER = {
    "label": "Challenger Candidate (AgentPay-IR v2)",
    "status": "REJECTED — frozen safety gate FAILED",
    "verdict": "M2_FROZEN_EVALUATION_FAIL / V2_NOT_ACTIVATED",
    "trained_on": "Colab fine-tune of the AgentPay-IR v2 corpus (candidate A_2ep)",
    "normal_test_macro_f1": {"before": 0.7367, "after": 0.9752, "verdict": "improved"},
    "human_gold": {
        "unsafe_contradiction_to_entailment": {"before": 2, "after": 7},
        "macro_f1": {"before": 0.8930, "after": 0.7757},
        "verdict": "WORSENED — safety regression",
    },
    "fresh_ood": {
        "unsafe_contradiction_to_entailment": {"before": 5, "after": 6},
        "verdict": "WORSENED — safety regression",
    },
    "why_rejected": (
        "The frozen activation rule requires safety not to regress on human gold "
        "and fresh OOD. A model that lets more gold contradictions reach a "
        "provider-call PASS must not ship, whatever its macro-F1."
    ),
    "can_authorize_payment": False,
    "is_activated": False,
    "evidence": "docs/agentpay_ir_v2/FINAL_FROZEN_EVALUATION.{md,json}; DECISIONS.md D-055",
}

_FROZEN_RULES = [
    "No rerun of frozen evaluation (one-shot, consumed 2026-08-30).",
    "No retraining and no threshold recalibration from frozen results.",
    "Challenger output never enters fusion, tickets, or provider decisions.",
    "Row-level private gold/review data is never exposed.",
]


def governance_summary() -> dict[str, Any]:
    """Aggregate, judge-facing governance truth (M091/M092)."""
    settings = get_settings()
    return {
        "active": _ACTIVE,
        "challenger": _CHALLENGER,
        "frozen_rules": _FROZEN_RULES,
        "runtime_backend": settings.semantic_verifier_backend,
        "shadow_mode_available": True,  # demo-only, non-frozen inputs
        "disclosed_limitation": (
            "A recurring term hidden ONLY in untrusted listing text is invisible "
            "to the structured evidence builder — the gap the v2 corpus targeted, "
            "and the honest reason a future candidate must pass this gate first."
        ),
    }


def shadow_verdict(hypothesis: str) -> dict[str, Any]:
    """Optional challenger shadow (M093): NON-FROZEN demo inputs only.

    Runs the deterministic keyword verifier explicitly as a TEST STUB
    (never the production model, never v2 weights) on new demo text the
    owner types. The result is labeled NON-AUTHORITATIVE and never reaches
    fusion. This exists to visualize disagreement mechanics (M094); it does
    not evaluate the challenger model itself.
    """
    text = hypothesis.strip()[:400]
    if not text:
        return {"error": "empty hypothesis"}
    from razormesh_api.semantic import DeterministicKeywordVerifier

    verifier = DeterministicKeywordVerifier()
    result = verifier.assess((text,))
    verdict = getattr(result, "verdict", None)
    shadow_action = str(getattr(verdict, "value", "UNSAFE")).upper()
    return {
        "mode": "SHADOW — NON-AUTHORITATIVE",
        "input": text,
        "shadow_action": shadow_action,
        "authoritative_action": "ACTIVE MODEL ONLY (this shadow never decides)",
        "disagreement_note": (
            "If this shadow disagreed with the active model, authority would still "
            "come from the ACTIVE model alone — the challenger is IGNORED."
        ),
        "never_enters": ["fusion", "ticket", "provider"],
        "is_frozen_evaluation": False,
    }


def load_committed_metrics() -> dict[str, Any]:
    """Serve the committed frozen evaluation JSON as evidence (no rerun)."""
    try:
        from razormesh_api.semantic_runtime import REPO_ROOT

        path = REPO_ROOT / "docs" / "agentpay_ir_v2" / "FINAL_FROZEN_EVALUATION.json"
        if path.exists():
            data: dict[str, Any] = json.loads(path.read_text())
            # Safety: strip any raw premise/hypothesis text fields.
            stripped: dict[str, Any] = _strip_private_text(data)
            return stripped
    except Exception:  # noqa: BLE001 - evidence is optional in the panel
        return {}
    return {}


_PRIVATE_KEYS = ("premise", "hypothesis", "text", "authorization_text", "prompt")


def _strip_private_text(node: Any) -> Any:
    if isinstance(node, dict):
        return {
            k: ("<redacted: private review text>" if k in _PRIVATE_KEYS else _strip_private_text(v))
            for k, v in node.items()
        }
    if isinstance(node, list):
        return [_strip_private_text(i) for i in node]
    return node
