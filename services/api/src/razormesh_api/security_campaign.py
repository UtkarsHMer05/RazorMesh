"""Phase-5 (M074-M077): AgentPay-X live campaign API.

Contract:
- Runs the CANONICAL 191-case benchmark (run_benchmark + per-case results) —
  never a rewritten or weakened variant. The pytest gate remains the
  authoritative benchmark run; this API surfaces the same engine for the UI.
- Live counters derive from campaign data only (no fabricated 191/191).
- Case explorer: filter by family/outcome; per-case evidence comes from the
  recorded scenario + its real gate outcomes.
- Case replay: renders a case through the trace-style pipeline using recorded
  stage evidence — read-only, no provider effects, no new tickets.
"""

from __future__ import annotations

from typing import Any

from razormesh_api.protocol.agentpay_x import (
    ALL_SCENARIOS,
    SCENARIO_VERSION,
    run_benchmark,
    run_scenario,
)

_CACHE: dict[str, Any] | None = None


def _cached_campaign() -> dict[str, Any]:
    """Run (and cache) the CANONICAL benchmark, unmodified.

    Counters are taken verbatim from run_benchmark() so the UI can never
    diverge from the authoritative gate. run_benchmark is deterministic and
    pure-engine; caching one result per process only avoids recompute.
    """
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    metrics = run_benchmark()
    campaign = {
        "total": metrics["scenarios_total"],
        "safe_total": metrics["scenarios_safe"],
        "safe_pass": metrics["safe_pass_rate"],
        "attack_total": metrics["scenarios_attack"],
        "attack_block": metrics["attack_block_rate"],
        "challenge_count": metrics["challenge_count"],
        "challenge_actual": metrics["challenge_actual"],
        "false_allows": metrics["false_allow_count"],
        "false_blocks": metrics["false_block_count"],
        "exactly_once_violations": metrics["exactly_once_violations"],
        "all_passed": all(r["passed"] for r in metrics["results"]),
        "passed_count": sum(1 for r in metrics["results"] if r["passed"]),
        "benchmark_version": SCENARIO_VERSION,
        "results": metrics["results"],
    }
    _CACHE = campaign
    return campaign


def campaign_summary() -> dict[str, Any]:
    """Aggregate counters for the campaign UI (M075) — canonical values."""
    c = _cached_campaign()
    return {k: v for k, v in c.items() if k != "results"}


def campaign_cases(family: str | None = None, outcome: str | None = None) -> list[dict[str, Any]]:
    """Filterable case explorer feed (M076) — real case metadata only."""
    c = _cached_campaign()
    cases: list[dict[str, Any]] = []
    for r in c["results"]:
        scenario = next(s for s in ALL_SCENARIOS if s.scenario_id == r["scenario_id"])
        if family and r["family"] != family:
            continue
        if outcome and r["actual_final"] != outcome.upper():
            continue
        cases.append(
            {
                "scenario_id": r["scenario_id"],
                "family": r["family"],
                "safe_or_attack": r["safe_or_attack"],
                "description": scenario.description,
                "mutation": scenario.mutation,
                "source_protocols": scenario.source_protocols,
                "expected_firewall": r["expected_firewall"],
                "expected_consistency": r["expected_consistency"],
                "expected_final": r["expected_final"],
                "actual_firewall": r["actual_firewall"],
                "actual_consistency": r["actual_consistency"],
                "actual_final": r["actual_final"],
                "passed": r["passed"],
            }
        )
    return cases


def case_replay(scenario_id: str) -> dict[str, Any]:
    """Stage-by-stage evidence for one case (M077) — recorded, read-only.

    Renders the case through the trace-style pipeline using the recorded gate
    outcomes; re-running run_scenario for a single case is pure-engine and
    side-effect-free (no tickets, no provider, no audit mutation).
    """
    scenario = next((s for s in ALL_SCENARIOS if s.scenario_id == scenario_id), None)
    if scenario is None:
        raise KeyError(scenario_id)
    r = run_scenario(scenario)
    stages = [
        {
            "stage": "protocol",
            "title": "Protocol firewall",
            "status": r["actual_firewall"] or "—",
            "detail": f"source protocol {scenario.source_protocols[0]}",
        },
        {
            "stage": "consistency",
            "title": "Cross-protocol consistency",
            "status": r["actual_consistency"] or "—",
            "detail": f"mutation: {scenario.mutation}",
        },
        {
            "stage": "razorguard",
            "title": "Deterministic RazorGuard + fusion",
            "status": r["actual_final"] or "—",
            "detail": (
                "final decision over the canonical commitment"
                if r["actual_consistency"] == "MATCH"
                else "mismatched commitment fails closed"
            ),
        },
        {
            "stage": "ticket",
            "title": "Execution ticket",
            "status": "WITHHELD" if r["actual_final"] == "BLOCK" else "EVIDENCE-ONLY",
            "detail": ("benchmark harness: no ticket is minted for replayed cases"),
        },
        {
            "stage": "provider",
            "title": "Provider boundary",
            "status": "NOT CONTACTED",
            "detail": "the benchmark never contacts the provider",
        },
    ]
    return {
        "scenario_id": scenario.scenario_id,
        "family": scenario.family,
        "safe_or_attack": scenario.safe_or_attack,
        "description": scenario.description,
        "expected_final": r["expected_final"],
        "actual_final": r["actual_final"],
        "passed": r["passed"],
        "stages": stages,
        "read_only": True,
    }


def attack_families() -> list[dict[str, Any]]:
    """Attack taxonomy (M064) mapped from the real scenario registry."""
    families: dict[str, dict[str, Any]] = {}
    for s in ALL_SCENARIOS:
        f = families.setdefault(
            s.family,
            {"family": s.family, "count": 0, "safe": 0, "attack": 0, "examples": []},
        )
        f["count"] += 1
        f["safe" if s.safe_or_attack == "safe" else "attack"] += 1
        if len(f["examples"]) < 3 and s.safe_or_attack == "attack":
            f["examples"].append({"id": s.scenario_id, "description": s.description})
    return sorted(families.values(), key=lambda fam: str(fam["family"]))
