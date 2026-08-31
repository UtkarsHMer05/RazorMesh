"""Phase-5 (M091-M094) + deep-engine correction (G003-G005): Model Governance.

Contract (D-055/D-056, master prompt §13.9 + correction G003/G004/G005):
- The ACTIVE semantic runtime is the PRE_V2 verifier (backend deberta,
  phase3-finetuned-v2, semantic-thresholds-v3). It stays active.
- The v2 candidate was evaluated ONCE on frozen data and NOT ACTIVATED by the
  safety gate. It is NEVER authoritative: no fusion, no tickets, no provider.
- All metrics below are committed evidence values (DECISIONS.md D-055 +
  docs/agentpay_ir_v2/FINAL_FROZEN_EVALUATION). This API projects them
  read-only; it never reruns frozen evaluation and never recalibrates.
- Shadow mode (G003) runs the ACTUAL fine-tuned v2 checkpoint
  (ChallengerShadowVerifier) on NEW NON-FROZEN demo text only, marked
  NON-AUTHORITATIVE, and never enters fusion/tickets/provider. If the real
  artifact cannot load, the shadow reports CHALLENGER_UNAVAILABLE honestly —
  the keyword verifier is never substituted for the challenger.
"""

from __future__ import annotations

import json
from typing import Any

from razormesh_api.challenger_shadow import (
    ChallengerShadowVerifier,
    get_challenger_shadow,
    shadow_status,
)
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
    "shadow_runs": "the ACTUAL fine-tuned v2 checkpoint (candidate A_2ep)",
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
    "shadow_only": "shadow only — can never authorize payment",
    "can_authorize_payment": False,
    "cannot_authorize_payment": True,
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
    """Aggregate, judge-facing governance truth (M091/M092 + G005)."""
    settings = get_settings()
    return {
        "active": _ACTIVE,
        "challenger": _CHALLENGER,
        "shadow": shadow_status(),
        "frozen_rules": _FROZEN_RULES,
        "runtime_backend": settings.semantic_verifier_backend,
        # Truthful availability (F014): the shadow lane runs only when the real
        # v2 artifact actually loaded (hash+manifest verified). A fresh clone
        # without the 738 MB artifact reports CHALLENGER_UNAVAILABLE honestly
        # — never a hardcoded True.
        "shadow_mode_available": get_challenger_shadow().available,
        "shadow_unavailable_reason": (
            "Verified v2 model artifact not present at the configured path "
            "— shadow lane unavailable."
            if not get_challenger_shadow().available
            else None
        ),
        "shadow_artifact_dir": settings.semantic_model_path_v2,
        "disclosed_limitation": (
            "A recurring term hidden ONLY in untrusted listing text is invisible "
            "to the structured evidence builder — the gap the v2 corpus targeted, "
            "and the honest reason a future candidate must pass this gate first."
        ),
    }


# Canonical NLI orientation (F002, matches semantic_evidence.py + the frozen
# corpus): PREMISE = the CURRENT sanitized commerce/checkout evidence,
# HYPOTHESIS = the human-confirmed authorization. This is NEW demo text authored
# for the demo — never a row from frozen test/gold/OOD data.
_DEFAULT_DEMO_PREMISE = (
    "The current checkout contains a one-time purchase of wireless headphones "
    "with a total of 4799 rupees and no renewal after purchase."
)
_DEFAULT_DEMO_AUTHORIZATION = (
    "The human authorized a one-time purchase of headphones for at most "
    "5000 rupees with no subscription of any kind."
)


def shadow_verdict(
    commerce_evidence: str | None = None, *, authorization: str | None = None
) -> dict[str, Any]:
    """Challenger shadow (G003): the REAL v2 checkpoint, NON-AUTHORITATIVE.

    Runs the actual fine-tuned AgentPay-IR v2 artifact (candidate A_2ep) on
    new demo text only, in the CANONICAL orientation used by both the frozen
    corpus and the production evidence builder:

        premise     = current commerce/checkout EVIDENCE  (what the cart says)
        hypothesis  = human-confirmed AUTHORIZATION        (what the human said)

    If the artifact cannot load or inference fails, the result is
    CHALLENGER_UNAVAILABLE with the honest reason — the keyword verifier is
    NEVER substituted for the challenger. The active PRE_V2 model runs the
    same pair so the panel can show real agreement/disagreement; authority
    always comes from the active model alone.
    """
    premise = (commerce_evidence or _DEFAULT_DEMO_PREMISE).strip()[:512]
    hypothesis = (authorization or _DEFAULT_DEMO_AUTHORIZATION).strip()[:400]
    if not premise or not hypothesis:
        return {"error": "empty commerce evidence or authorization text"}

    shadow: ChallengerShadowVerifier = get_challenger_shadow()
    challenger = shadow.assess_pair(premise, hypothesis)

    # Active model on the same pair: the live PRE_V2 runtime decision lane.
    active: dict[str, Any]
    try:
        from razormesh_api.semantic_runtime import (
            MODEL_DIR,
            POLICY_PATH,
            get_semantic_verifier,
            resolve_repo_path,
        )

        verifier = get_semantic_verifier(
            model_dir=resolve_repo_path(MODEL_DIR), policy_path=resolve_repo_path(POLICY_PATH)
        )
        verdict = verifier.verify(premise=premise, hypothesis=hypothesis)
        active = {
            "action": str(verdict.action.value),
            "p_contradiction": verdict.p_contradiction,
            "p_entailment": verdict.p_entailment,
            "p_neutral": verdict.p_neutral,
            "model_id": verdict.model_id,
            "policy_version": verdict.policy_version,
        }
    except Exception as exc:  # noqa: BLE001 - active lane status is report-only
        active = {"action": "UNAVAILABLE", "reason": f"{type(exc).__name__}: {exc}"}

    disagree = (
        challenger.available
        and active.get("action") not in (None, "UNAVAILABLE")
        and challenger.shadow_action != active.get("action")
    )
    return {
        "mode": "SHADOW — NON-AUTHORITATIVE",
        "orientation": "premise=commerce evidence · hypothesis=human authorization",
        "premise": premise,
        "hypothesis": hypothesis,
        "input": hypothesis,  # convenience for legacy UI
        "challenger": challenger.to_dict(),
        "active": active,
        "disagreement": bool(disagree),
        "shadow_action": challenger.shadow_action,  # convenience for legacy UI
        "authoritative_action": "ACTIVE MODEL ONLY (this shadow never decides)",
        "disagreement_note": (
            "The challenger and the active model disagree here. Authority still "
            "comes from the ACTIVE model alone — the challenger is IGNORED."
            if disagree
            else "If the shadow disagreed with the active model, authority would still "
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
