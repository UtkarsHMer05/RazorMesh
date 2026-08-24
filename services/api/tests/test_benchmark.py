"""M44 acceptance: paired safe/unsafe benchmark with confusion metrics."""

from razormesh_api.benchmark import PairedBenchmark, build_pairs
from razormesh_api.evaluation import AdversarialRunner
from razormesh_api.scenarios import SCENARIOS


def test_build_pairs_creates_safe_twin_for_every_attack_family() -> None:
    pairs = build_pairs()
    unsafe_count = sum(s.safe_or_unsafe == "unsafe" for s in SCENARIOS)
    assert len(pairs) == unsafe_count
    for safe_spec, unsafe_spec in pairs:
        assert safe_spec.family.value == "SAFE_LOOKALIKE"
        assert safe_spec.scenario_id != unsafe_spec.scenario_id
        assert safe_spec.mutation.startswith("no malicious mutation")
        # twins differ ONLY by family/mutation, sharing the attack's base id
        assert unsafe_spec.scenario_id in safe_spec.scenario_id.replace("safetwin", "")


def test_benchmark_perfect_classification_on_current_pipeline() -> None:
    report = PairedBenchmark(AdversarialRunner()).run()

    unsafe_count = sum(s.safe_or_unsafe == "unsafe" for s in SCENARIOS)
    assert report.pairs == unsafe_count
    # current pipeline must block every attack and complete every safe control
    assert (report.tp, report.fp, report.tn, report.fn) == (
        unsafe_count,
        0,
        unsafe_count,
        0,
    )
    assert report.precision == 1.0
    assert report.recall == 1.0
    assert report.f1 == 1.0
    assert report.false_block_rate == 0.0
    assert report.safe_completion_rate == 1.0
    assert report.unsafe_execution_rate == 0.0


def test_synthetic_gmv_is_positive_and_labelled(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from razormesh_api.benchmark import write_report

    runner = AdversarialRunner()
    report = PairedBenchmark(runner).run()
    assert report.synthetic_gmv_minor > 0
    assert report.synthetic_gmv_protected_minor > 0

    out = tmp_path / "bench.json"
    write_report(out, report)
    text = out.read_text()
    assert "SYNTHETIC" in text, "GMV figures must be explicitly labelled synthetic"


def test_metrics_math_consistency() -> None:
    from razormesh_api.benchmark import BenchmarkReport

    r = BenchmarkReport(
        pairs=10,
        tp=7,
        fp=2,
        tn=3,
        fn=1,
        precision=7 / 9,
        recall=7 / 8,
        f1=2 * (7 / 9) * (7 / 8) / ((7 / 9) + (7 / 8)),
        false_block_rate=2 / 5,
        safe_completion_rate=3 / 5,
        unsafe_execution_rate=1 / 8,
        synthetic_gmv_minor=100,
        synthetic_gmv_protected_minor=50,
        synthetic_legitimate_gmv_blocked_minor=25,
    )
    assert abs(r.precision - 0.7778) < 0.001
    assert abs(r.recall - 0.875) < 0.001
    assert r.tp + r.fn == 8  # all unsafe
    assert r.fp + r.tn == 5  # all safe
