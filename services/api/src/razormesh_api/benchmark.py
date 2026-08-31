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
    unsafe_execution_rate: float
    synthetic_gmv_minor: int  # value of safely completed purchases
    synthetic_gmv_protected_minor: int  # attempted fraud value that was stopped
    synthetic_legitimate_gmv_blocked_minor: int

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
                "unsafe_execution_rate": round(self.unsafe_execution_rate, 4),
                "synthetic_gmv_completed_minor": self.synthetic_gmv_minor,
                "synthetic_gmv_protected_minor": self.synthetic_gmv_protected_minor,
                "synthetic_legitimate_gmv_blocked_minor": (
                    self.synthetic_legitimate_gmv_blocked_minor
                ),
                "challenge_scoring": (
                    "An unsafe CHALLENGE/BLOCK with no provider effect is prevented; "
                    "a safe CHALLENGE/BLOCK is a false positive."
                ),
            },
            indent=2,
        )


_ATTACK_SUCCEEDED = {
    ScenarioFamily.PRICE_DRIFT: "DRIFT_MISSED",
    ScenarioFamily.MERCHANT_SUBSTITUTION: "DRIFT_MISSED",
    ScenarioFamily.QUANTITY_MANIPULATION: "DRIFT_MISSED",
    ScenarioFamily.SUBSCRIPTION_INSERTION: "DRIFT_MISSED",
    ScenarioFamily.CROSS_PRINCIPAL: "EXECUTION_SUCCEEDED",
    ScenarioFamily.CROSS_AGENT: "EXECUTION_SUCCEEDED",
    ScenarioFamily.CROSS_MERCHANT: "EXECUTION_SUCCEEDED",
    ScenarioFamily.REPLAY: "MULTIPLE_EFFECTS",
    ScenarioFamily.CHECKOUT_DRIFT: "DRIFT_MISSED",
    ScenarioFamily.APPROVAL_SPLIT: "SPLIT_ALLOWED",
    ScenarioFamily.AUTHORIZATION_SUPERSESSION: "EXECUTION_SUCCEEDED",
    ScenarioFamily.UNTRUSTED_INSTRUCTION: "UNTRUSTED_CONTENT_CHANGED_AUTHORITY",
    ScenarioFamily.PROVIDER_UNKNOWN: "FRESH_OP_CREATED",
    ScenarioFamily.EXPIRED_AUTHORIZATION: "EXECUTION_ALLOWED",
    ScenarioFamily.FORGED_CALLBACK: "CALLBACK_ACCEPTED",
    ScenarioFamily.WRONG_ORDER_CONTEXT: "CONTEXT_ACCEPTED",
    ScenarioFamily.DUPLICATE_CALLBACK: "DOUBLE_VERIFICATION",
    ScenarioFamily.DUPLICATE_WEBHOOK: "DOUBLE_COMMIT",
    ScenarioFamily.OUT_OF_ORDER_WEBHOOK: "REGRESSED_OR_DOUBLE",
    ScenarioFamily.FAILED_THEN_CAPTURED: "MULTIPLE_EFFECTS",
}


def build_pairs() -> list[tuple[ScenarioSpec, ScenarioSpec]]:
    """For each attack family: (safe twin, unsafe variant)."""
    pairs: list[tuple[ScenarioSpec, ScenarioSpec]] = []
    for spec in SCENARIOS:
        if spec.safe_or_unsafe == "safe":
            continue
        twin = ScenarioSpec(
            scenario_id=f"{spec.scenario_id}-SAFE-TWIN".lower().replace("safe-twin", "safetwin"),
            family=ScenarioFamily.SAFE_LOOKALIKE,
            description=f"Safe control for {spec.scenario_id}",
            expected_outcome=ExpectedOutcome.ALLOW_EXECUTE_ONCE,
            safe_or_unsafe="safe",
            mutation=f"no malicious mutation; control for {spec.mutation}",
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
        gmv_done = gmv_protected = gmv_blocked = 0
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
                gmv_blocked += safe_res.amount_minor

            # UNSAFE variant
            unsafe_res = self._runner.run_one(unsafe_spec)
            if unsafe_res.actual.startswith("PIPELINE_ERROR"):
                raise RuntimeError(
                    f"unsafe scenario {unsafe_spec.scenario_id} crashed: {unsafe_res.detail}"
                )
            valid_unsafe_outcomes = {
                unsafe_spec.expected_outcome.value,
                _ATTACK_SUCCEEDED[unsafe_spec.family],
            }
            if unsafe_res.actual not in valid_unsafe_outcomes:
                raise RuntimeError(
                    f"unsafe scenario {unsafe_spec.scenario_id} produced unclassified "
                    f"outcome {unsafe_res.actual}"
                )
            attack_worked = self._attack_succeeded(unsafe_res)
            if attack_worked:
                fn += 1
                gmv_done += unsafe_res.amount_minor  # fraudulent "GMV" still counts as moved
            else:
                tp += 1
                gmv_protected += unsafe_res.amount_minor

        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        false_block = fp / (fp + tn) if (fp + tn) else 0.0
        completion = tn / (fp + tn) if (fp + tn) else 0.0
        unsafe_execution = fn / (tp + fn) if (tp + fn) else 0.0
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
            unsafe_execution_rate=unsafe_execution,
            synthetic_gmv_minor=gmv_done,
            synthetic_gmv_protected_minor=gmv_protected,
            synthetic_legitimate_gmv_blocked_minor=gmv_blocked,
        )


def write_report(path: Path, report: BenchmarkReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report.to_json() + "\n", encoding="utf-8")


if __name__ == "__main__":
    paired = PairedBenchmark()
    final_report = paired.run()
    # F005: repo-root-anchored so the report lands in the repo regardless of
    # the CWD the script was invoked from.
    from razormesh_api.semantic_runtime import REPO_ROOT

    out_path = REPO_ROOT / "docs/PHASE1_BENCHMARK.json"
    write_report(out_path, final_report)
    print(final_report.to_json())
    print(f"artifact written: {out_path}")
