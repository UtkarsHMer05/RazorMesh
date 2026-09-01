"""M46: security lab API — executes the synthetic scenario suite on demand.

Everything here is LOCAL and SYNTHETIC: fixture catalog, fixture authorization,
mock provider. No real systems are contacted and no offensive tooling exists;
the "attacks" are the same structured scenario mutations used for the M43/M44
evaluation, replayed for interactive inspection with their evidence.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from razormesh_api.evaluation import AdversarialRunner
from razormesh_api.persistence.repositories import Repositories
from razormesh_api.scenarios import SCENARIOS
from razormesh_api.settings import Settings, get_settings

router = APIRouter(prefix="/security-lab", tags=["security-lab"])


def _runner(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AdversarialRunner:
    from razormesh_api.persistence.db import create_db_engine

    return AdversarialRunner(create_db_engine(settings.database_url))


def _repos(runner: AdversarialRunner) -> Repositories:
    return runner.repositories


@router.get("/why-semantic-ai")
def why_semantic_ai(
    runner: Annotated[AdversarialRunner, Depends(_runner)],
) -> dict[str, Any]:
    """S002/F011: WHY SEMANTIC AI MATTERS — fully real engines end to end.

    A NEW NON-FROZEN transaction is created per run and driven through the
    REAL deterministic RazorGuard machinery (CheckoutService.propose/
    authorize — the buyer flow's own path), which genuinely ALLOWS the
    structured facts and mints an ExecutionTicket; the REAL active semantic
    model then reads the demo's sanitized commerce evidence against the human
    authorization in canonical orientation; the REAL conservative fusion BLOCK
    withholds the ticket, and the provider is contacted zero times. Nothing
    is painted.
    """
    from razormesh_api.semantic_only_demo import run_semantic_only_demo

    return run_semantic_only_demo(_repos(runner))


@router.get("/scenarios")
def list_scenarios() -> dict[str, Any]:
    return {
        "count": len(SCENARIOS),
        "note": "Synthetic local scenarios only; executed against the mock provider.",
        "scenarios": [
            {
                "scenario_id": s.scenario_id,
                "family": s.family.value,
                "description": s.description,
            }
            for s in SCENARIOS
        ],
    }


@router.post("/run")
def run_suite(runner: Annotated[AdversarialRunner, Depends(_runner)]) -> dict[str, Any]:
    """Seed isolated synthetic fixtures and execute the suite through the real pipeline."""
    results = []
    for res in runner.run_all():
        results.append(
            {
                "scenario_id": res.scenario_id,
                "family": res.family.value,
                "actual": res.actual,
                "passed": res.passed,
                "detail": res.detail,
                "amount_minor": res.amount_minor,
            }
        )

    # Step-by-step evidence: durable ledger trail from the last scenario run.
    ledger_events = [
        {
            "seq": e.seq,
            "event_type": e.event_type,
            "actor": e.actor,
            "hash_head": e.current_event_hash[:16],
        }
        for e in runner.repositories.audit.list_recent(12)
    ]

    return {
        "note": "All scenarios are synthetic and execute locally against the mock provider.",
        "total": len(results),
        "passed": sum(1 for r in results if r["passed"]),
        "results": results,
        "evidence_tail": ledger_events,
    }
