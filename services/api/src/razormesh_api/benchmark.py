"""M44: paired safe/unsafe benchmark with TP/FP/TN/FN and synthetic GMV.

Every attack family is paired with a SAFE twin that differs ONLY in the
malicious dimension. Each case runs through the real pipeline (M43) and is
classified:

- ground truth: the pair label (safe case vs unsafe case)
- system behaviour: did money move? (execution completed)

    unsafe + blocked/challenged -> TP     safe + executed        -> TN
    unsafe + executed           -> FN     safe + blocked         -> FP

Metrics: precision, recall, F1, false-block rate, safe-completion rate, and
SYNTHETIC GMV (clearly labelled; local fixture prices only).
"""

import json
from dataclasses import dataclass
from pathlib import Path

from razormesh_api.evaluation import AdversarialRunner, ScenarioResult
from razormesh_api.scenarios import (
    SCENARIOS,
    ExpectedOutcome,
    ScenarioFamily,
    ScenarioSpec,
)


@dataclass(frozen=True)
class CaseRecord:
    pair_id: str
    is_unsafe_case: bool
    scenario_id: str
    executed: bool
    amount_minor: int


@dataclass(frozen=True)
class BenchmarkReport:
    pairs: int
    tp: int
    fp: int
    tn: int
    fn: int
    precision: float
    recall: float
    f1: float
    false_block_rate: float
    safe_completion_rate: float
    synthetic_gmv_minor: int  # value of safely completed purchases
    synthetic_gmv_protected_minor: int  # attempted fraud value that was stopped

    def to_json(self) -> str:
        return json.dumps(
            {
                "label": "SYNTHETIC Phase-1 local benchmark (fixture data only)",
                "pairs": self.pairs,
                "confusion": {"TP": self.tp, "FP": self.fp, "TN": self.tn, "FN": self.fn},
                "precision": round(self.precision, 4),
                "recall": round(self.recall, 4),
                "f1": round(self.f1, 4),
                "false_block_rate": round(self.false_block_rate, 4),
                "safe_completion_rate": round(self.safe_completion_rate, 4),
                "synthetic_gmv_completed_minor": self.synthetic_gmv_minor,
                "synthetic_gmv_protected_minor": self.synthetic_gmv_protected_minor,
            },
            indent=2,
        )


_ATTACK_SUCCEEDED = {
    ScenarioFamily.CONTEXT_SWAP: "EXECUTION_SUCCEEDED",
    ScenarioFamily.REPLAY: "MULTIPLE_EFFECTS",
    ScenarioFamily.CHECKOUT_DRIFT: "DRIFT_MISSED",
    ScenarioFamily.APPROVAL_SPLIT: "SPLIT_ALLOWED",
    ScenarioFamily.PROVIDER_UNKNOWN: "FRESH_OP_CREATED",
    ScenarioFamily.EXPIRED_AUTHORIZATION: "EXECUTION_ALLOWED",
}


def build_pairs() -> list[tuple[ScenarioSpec, ScenarioSpec]]:
    """For each attack family: (safe twin, unsafe variant)."""
    baseline = next(s for s in SCENARIOS if s.family == ScenarioFamily.SAFE_BASELINE)
    pairs: list[tuple[ScenarioSpec, ScenarioSpec]] = []
    for spec in SCENARIOS:
        if spec.family == ScenarioFamily.SAFE_BASELINE:
            continue
        twin = ScenarioSpec(
            scenario_id=f"{spec.scenario_id}-SAFE-TWIN".lower().replace("safe-twin", "safetwin"),
            family=baseline.family,
            description=f"Safe control for {spec.scenario_id}",
            expected_outcome=ExpectedOutcome.ALLOW_EXECUTE_ONCE,
            replay_count=1,
            split_parts=1,
        )
        pairs.append((twin, spec))
    return pairs


class PairedBenchmark:
    def __init__(self, runner: AdversarialRunner | None = None) -> None:
        self._runner = runner or AdversarialRunner()

    @staticmethod
    def _attack_succeeded(result: ScenarioResult) -> bool:
        return result.actual == _ATTACK_SUCCEEDED[result.family]

    def run(self) -> BenchmarkReport:
        tp = fp = tn = fn = 0
        gmv_done = gmv_protected = 0
        pairs_count = 0

        for safe_spec, unsafe_spec in build_pairs():
            pairs_count += 1

            # SAFE control
            safe_res = self._runner.run_one(safe_spec)
            safe_executed = safe_res.actual == "ALLOW_EXECUTE_ONCE"
            if safe_executed:
                tn += 1
                gmv_done += safe_res.amount_minor
            else:
                fp += 1

            # UNSAFE variant
            unsafe_res = self._runner.run_one(unsafe_spec)
            attack_worked = self._attack_succeeded(unsafe_res)
            if attack_worked:
                fn += 1
                gmv_done += unsafe_res.amount_minor  # fraudulent "GMV" still counts as moved
            else:
                tp += 1
                if not safe_executed:
                    pass
                gmv_protected += unsafe_res.amount_minor

        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        false_block = fp / (fp + tn) if (fp + tn) else 0.0
        completion = tn / (fp + tn) if (fp + tn) else 0.0
        return BenchmarkReport(
            pairs=pairs_count,
            tp=tp,
            fp=fp,
            tn=tn,
            fn=fn,
            precision=precision,
            recall=recall,
            f1=f1,
            false_block_rate=false_block,
            safe_completion_rate=completion,
            synthetic_gmv_minor=gmv_done,
            synthetic_gmv_protected_minor=gmv_protected,
        )


def write_report(path: Path, report: BenchmarkReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report.to_json() + "\n", encoding="utf-8")
