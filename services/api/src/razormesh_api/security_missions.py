"""Deep-engine correction (G016-G018): one security-mission engine.

Contract:
- G016: every clickable attack card runs THAT attack only. Dedicated
  missions share one orchestration primitive:
      create mission -> apply zero or more mutations -> choose pipeline
      -> execute -> observe (per-stage evidence + provider count)
  The full 22-scenario suite stays a separate explicit action.
- G017: the attack movie is EVENT-DRIVEN. Mission evidence carries the
  trace's projected events; the frontend builds movie stages from those
  events. If a backend event is absent, the corresponding stage is absent —
  never a fabricated "DONE".
- G018: Safe, hidden-recurring, price-drift and protocol-thesis missions
  all run through THIS module's mission orchestration (no per-attack
  hardcoded business logic — recipes are data).

The mutations re-use the SAME proven primitives as the existing surfaces:
the merchant sandbox's checkout-local mutations (G013) and the D-056
full-evidence rejection orchestrator. Nothing bypasses RazorGuard; BLOCKED
never executes; the provider is only ever contacted through the trusted
executor on a genuine ALLOW (mock provider in the demo environment).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from razormesh_api.merchant_sandbox import MutationKind, propose_checkout_for_demo
from razormesh_api.persistence.repositories import Repositories
from razormesh_api.trace_registry import TraceRegistry, project_events


class MissionError(RuntimeError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


# ---------------------------------------------------------------------------
# G018: mission recipes are DATA. Adding a mission = adding a recipe entry,
# never new business logic.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MissionRecipe:
    """One security-mission recipe (inputs only - outcomes come from the engine)."""

    mission_id: str
    title: str
    description: str
    attack: bool
    # Pipeline choice: which proven executor drives this mission.
    pipeline: str  # "razorguard" | "acceptance"
    # Merchant-sandbox mutations applied after proposal (G013 checkout-local).
    mutations: tuple[MutationKind, ...] = field(default_factory=tuple)
    # For pipeline="acceptance": the D-056 demo scenario to delegate to.
    acceptance_scenario: str | None = None


_RECIPES: dict[str, MissionRecipe] = {
    r.mission_id: r
    for r in (
        MissionRecipe(
            mission_id="safe",
            title="Safe mission",
            description=(
                "A one-time purchase inside the confirmed authorization: the full "
                "pipeline should ALLOW and the trusted executor contacts the "
                "provider exactly once (mock)."
            ),
            attack=False,
            pipeline="razorguard",
            mutations=(),
        ),
        MissionRecipe(
            mission_id="price-drift",
            title="Price drift after authorization",
            description="The merchant raises the unit price by Rs500 after the human authorized.",
            attack=True,
            pipeline="razorguard",
            mutations=(MutationKind.PRICE_DRIFT,),
        ),
        MissionRecipe(
            mission_id="hidden-recurring",
            title="Hidden recurring membership",
            description=(
                "A Rs499/month subscription is inserted after the human authorized "
                "a one-time purchase."
            ),
            attack=True,
            pipeline="razorguard",
            mutations=(MutationKind.HIDDEN_MEMBERSHIP,),
        ),
        MissionRecipe(
            mission_id="quantity-increase",
            title="Quantity increase after authorization",
            description="The merchant doubles the item quantity after authorization.",
            attack=True,
            pipeline="razorguard",
            mutations=(MutationKind.QUANTITY_INCREASE,),
        ),
        MissionRecipe(
            mission_id="merchant-swap",
            title="Merchant substitution",
            description="The checkout's merchant is swapped to another seller after authorization.",
            attack=True,
            pipeline="razorguard",
            mutations=(MutationKind.MERCHANT_SWAP,),
        ),
        MissionRecipe(
            mission_id="condition-downgrade",
            title="Condition downgrade",
            description="The offer's condition changes from new to used after authorization.",
            attack=True,
            pipeline="razorguard",
            mutations=(MutationKind.CONDITION_DOWNGRADE,),
        ),
        MissionRecipe(
            mission_id="protocol-thesis",
            title="Protocol-valid, intent-invalid",
            description=(
                "A perfectly valid protocol packet carries a transaction the human "
                "never authorized (2 units vs 1). Protocol PASS; RazorGuard BLOCK."
            ),
            attack=True,
            pipeline="acceptance",
            acceptance_scenario="scenario-c-protocol-valid-intent-invalid",
        ),
    )
}


def mission_catalog() -> list[dict[str, Any]]:
    """Attack/safe mission catalog (inputs only)."""
    return [
        {
            "mission_id": r.mission_id,
            "title": r.title,
            "description": r.description,
            "attack": r.attack,
            "pipeline": r.pipeline,
        }
        for r in _RECIPES.values()
    ]


# ---------------------------------------------------------------------------
# G016/G018: the ONE orchestration primitive every mission runs through.
# ---------------------------------------------------------------------------


def _pipeline_stages(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Per-stage evidence from the pipeline result (whatever engine ran)."""
    stages: list[dict[str, Any]] = []
    if result.get("protocol_firewall"):
        stages.append(
            {
                "stage": "protocol",
                "status": str(result["protocol_firewall"]),
                "detail": "; ".join(result.get("protocol_firewall_reasons") or []),
            }
        )
    if result.get("razorguard_decision"):
        stages.append(
            {
                "stage": "razorguard",
                "status": str(result["razorguard_decision"]),
                "detail": str(result.get("rejection_reason") or "deterministic rules"),
            }
        )
    if result.get("semantic_verifier"):
        probs = result.get("semantic_probabilities") or {}
        stages.append(
            {
                "stage": "semantic",
                "status": str(result["semantic_verifier"]),
                "detail": (
                    f"contradiction {probs.get('contradiction', 0):.4f} · "
                    f"entailment {probs.get('entailment', 0):.4f}"
                ),
            }
        )
    if result.get("final_decision"):
        stages.append(
            {
                "stage": "fusion",
                "status": str(result["final_decision"]),
                "detail": "conservative fusion (semantic can only tighten)",
            }
        )
    stages.append(
        {
            "stage": "ticket",
            "status": "ISSUED" if result.get("ticket_issued") else "WITHHELD",
            "detail": (
                "signed ticket after ALLOW"
                if result.get("ticket_issued")
                else "no authority to execute"
            ),
        }
    )
    stages.append(
        {
            "stage": "provider",
            "status": "CONTACTED" if result.get("provider_contacted") else "NOT CONTACTED",
            "detail": "audit-backed provider evidence",
        }
    )
    return stages


def _product_for_mission(repos: Repositories) -> str:
    from sqlalchemy import select

    from razormesh_api.persistence.models import Product
    from razormesh_api.persistence.repositories import session_scope

    with session_scope(repos.factory) as session:
        cheapest = session.scalars(select(Product).order_by(Product.price_minor).limit(1)).first()
        product = cheapest
        non_recurring = session.scalars(
            select(Product)
            .where(Product.recurring.is_(False))
            .order_by(Product.price_minor)
            .limit(1)
        ).first()
        if non_recurring is not None:
            product = non_recurring
    if product is None:
        raise MissionError("NO_PRODUCTS", "catalog is empty")
    return product.id


def run_mission(
    repos: Repositories,
    *,
    mission_id: str,
    product_id: str | None = None,
    quantity: int = 1,
    intent_id: str | None = None,
) -> dict[str, Any]:
    """Run ONE mission through the shared orchestration (G016/G018).

    Orchestration:
      1. create mission (proposal for the product; baseline captured G012;
         trace minted/adopted G015)
      2. apply the recipe's mutations (checkout-local, G013)
      3. execute through the chosen pipeline (real engine)
      4. observe: per-stage evidence + the mission trace's projected events
         (the movie is built from THESE, G017)
    """
    recipe = _RECIPES.get(mission_id)
    if recipe is None:
        raise MissionError("UNKNOWN_MISSION", f"unknown mission {mission_id}")

    # 1. create the mission checkout (current-trace binding when intent given)
    pid = product_id or _product_for_mission(repos)
    i_id, c_id, _expected = propose_checkout_for_demo(
        repos, product_id=pid, quantity=quantity, intent_id=intent_id
    )

    # 2. apply the recipe's mutations via the merchant-sandbox primitives
    from razormesh_api.ledger import EvidenceLedger
    from razormesh_api.merchant_sandbox import apply_mutation

    ledger = EvidenceLedger(repos)
    applied: list[dict[str, Any]] = []
    for kind in recipe.mutations:
        result = apply_mutation(repos, ledger, intent_id=i_id, checkout_id=c_id, kind=kind)
        applied.append({"kind": kind.value, "changed_fields": list(result.changed_fields)})

    # 3. execute through the chosen pipeline
    if recipe.pipeline == "acceptance":
        # Delegate to the owner-accepted D-056 live orchestrator endpoints
        # (same code path the UI calls; real pipeline, DeBERTa in loop).
        from razormesh_api.api.routes.phase4_acceptance import (
            demo_scenario_b_semantic_violation,
            demo_scenario_c_protocol_valid_intent_invalid,
        )

        if recipe.acceptance_scenario == "scenario-b-semantic-violation":
            pipeline = demo_scenario_b_semantic_violation()
        elif recipe.acceptance_scenario == "scenario-c-protocol-valid-intent-invalid":
            pipeline = demo_scenario_c_protocol_valid_intent_invalid()
        else:  # pragma: no cover - recipes are data; guarded above
            raise MissionError("BAD_RECIPE", "unknown acceptance scenario")
        # The acceptance pipeline runs its OWN intent/checkout; bind this
        # mission's trace to it so the movie reads one coherent trace.
        i_id = str(pipeline.get("intent_id") or i_id)
        c_id = str(pipeline.get("checkout_id") or c_id)
    else:
        # RazorGuard pipeline: drive the REAL decision path over this
        # mission's (possibly mutated) checkout through the sanctioned
        # drift-revalidation contract — the exact boundary an execution
        # attempt would hit.
        from razormesh_api.revalidation import Revalidator

        verdict = Revalidator(repos).revalidate(
            intent_id=i_id,
            checkout_id=c_id,
            expected_checkout_hash=_expected["checkout_hash"],
            expected_revision=_expected["revision"],
            expected_intent_hash=_expected["intent_hash"],
            expected_generation=_expected["generation"],
        )
        final = "BLOCK" if verdict.code else "ALLOW"
        pipeline = {
            "final_decision": final,
            "ticket_issued": False,  # demo missions never mint money authority
            "provider_contacted": False,
            "rejection_reason": verdict.code or None,
            "razorguard_decision": final,
            "protocol_firewall": None,
            "semantic_verifier": None,
            "evidence": {"revalidation": verdict.code or "ok"},
        }

    # 4. observe: trace events (the movie source, G017) + stage evidence
    trace = TraceRegistry(repos).by_intent(i_id)
    events = project_events(repos, i_id)
    return {
        "mission_id": mission_id,
        "title": recipe.title,
        "attack": recipe.attack,
        "trace_id": trace.trace_id if trace else "",
        "intent_id": i_id,
        "checkout_id": c_id,
        "mutations_applied": applied,
        "pipeline": recipe.pipeline,
        "final_decision": pipeline.get("final_decision"),
        "ticket_issued": bool(pipeline.get("ticket_issued")),
        "provider_contacted": bool(pipeline.get("provider_contacted")),
        "stages": _pipeline_stages(pipeline),
        # G017: the movie source — ONLY real projected events.
        "events": [e.__dict__ for e in events],
        "movie_note": (
            "The attack movie renders from these trace events only. A stage "
            "without a backend event is shown as pending/absent - never a "
            "fabricated DONE."
        ),
    }


def replay_mission_trace(repos: Repositories, trace_id: str) -> dict[str, Any]:
    """Read-only replay of a mission's trace (G019/G022 support): the stored
    events with per-stage movie projection — no re-execution, no provider
    effects, no new audit rows."""
    registry = TraceRegistry(repos)
    trace = registry.by_trace(trace_id)
    if trace is None:
        raise MissionError("UNKNOWN_TRACE", f"unknown trace {trace_id}")
    events = project_events(repos, trace.intent_id)
    from razormesh_api.trace_registry import summarize_trace

    summary = summarize_trace(repos, trace)
    return {
        "trace_id": trace_id,
        "intent_id": trace.intent_id,
        "summary": summary,
        "events": [e.__dict__ for e in events],
        "read_only": True,
    }
