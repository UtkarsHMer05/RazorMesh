"""P2-M47: performance baseline artifact is present, parseable and honest.

The artifact must keep local compute SEPARATE from provider/network timing,
carry sample sizes and the Test Mode caveat. Values are environment-dependent
and are therefore never asserted numerically here.
"""

import json
from pathlib import Path

ARTIFACT = Path(__file__).resolve().parents[3] / "docs" / "PHASE2_PERFORMANCE.json"


def test_phase2_performance_artifact_structure() -> None:
    assert ARTIFACT.exists(), "run scripts/rzp_perf_phase2.py to generate the baseline"
    data = json.loads(ARTIFACT.read_text())

    ctx = data["context"]
    assert "NOT production capacity" in ctx["label"]
    assert "Test Mode" in ctx["test_mode_caveat"]
    assert ctx["platform"]

    # Local compute section: sample sizes recorded for every entry.
    for name, entry in data["local"].items():
        assert entry["n"] >= 1, name
        for key in ("mean_ms", "p50_ms", "p95_ms", "min_ms", "max_ms"):
            assert key in entry, (name, key)

    # Callback verification is pure compute: microseconds-scale sanity bound.
    assert data["local"]["callback_hmac_verify"]["p95_ms"] < 5

    # Provider section distinguishes real Test Mode network calls.
    provider = data["provider"]
    assert provider["mode"] in {"REAL_RAZORPAY_TEST_MODE", "SKIPPED_MOCK_SELECTOR"}
    if provider["mode"] == "REAL_RAZORPAY_TEST_MODE":
        assert provider["sample_n"] >= 1
        assert "no checkout/payment performed" in provider["note"]

    # Human timing must be labeled as non-system evidence.
    assert "NOT system performance" in data["human_reference"]["caveat"]
