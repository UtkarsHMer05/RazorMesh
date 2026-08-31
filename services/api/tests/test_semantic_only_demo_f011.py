"""F011: WHY SEMANTIC AI MATTERS — real-model semantic-only tightening.

Proves the demo contract honestly:
- the ACTIVE PRE_V2 model (not a stub) produces the semantic BLOCK on the new
  non-frozen fixture pairs at runtime;
- the deterministic lane ALLOWs the same structured facts;
- the real `fuse` seam yields BLOCK (semantic only tightens);
- ticket WITHHELD and provider calls 0;
- fixture provenance is explicit: NEW_DEMO_FIXTURE, non-frozen, never used
  for model selection or calibration;
- if the model cannot run, the demo fails closed — never a painted result.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from razormesh_api.api.main import app
from razormesh_api.semantic_only_demo import NEW_DEMO_FIXTURE, run_semantic_only_demo


@pytest.fixture()
def client(settings):  # type: ignore[no-untyped-def]
    import razormesh_api.api.main as api_main

    api_main.get_settings.cache_clear()
    app.dependency_overrides[api_main.get_settings] = lambda: settings
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_fixture_provenance_is_explicit() -> None:
    assert NEW_DEMO_FIXTURE["provenance"] == "NEW_DEMO_FIXTURE"
    assert NEW_DEMO_FIXTURE["frozen"] is False
    assert NEW_DEMO_FIXTURE["used_for_model_selection"] is False
    assert NEW_DEMO_FIXTURE["used_for_threshold_calibration"] is False
    assert "premise=commerce evidence" in NEW_DEMO_FIXTURE["canonical_orientation"]
    for pair in NEW_DEMO_FIXTURE["pairs"]:
        # canonical orientation: premise is commerce evidence, hypothesis is
        # the human authorization.
        assert "renews" in pair["premise"] or "recurring membership" in pair["premise"]
        assert "must not" in pair["hypothesis"]


def test_real_model_semantic_only_tightening() -> None:
    """The REAL active model BLOCKs where the deterministic rules ALLOW."""
    result = run_semantic_only_demo()
    assert result["honest"] is True, result["story"]

    demo = result["demonstration"]
    assert len(demo) >= 2
    for row in demo:
        # Deterministic lane: the structured facts carry no violation.
        assert row["razorguard"] == "ALLOW"
        # REAL semantic verdict (computed at runtime by the active model).
        assert row["semantic"] == "BLOCK", row
        assert row["probabilities"]["contradiction"] > 0.9, row["probabilities"]
        # The real fusion seam: semantic can only tighten.
        assert row["fusion"] == "BLOCK"
        # The money path: no authority, no provider contact.
        assert row["ticket"] == "WITHHELD"
        assert row["provider_calls"] == 0

    # The runtime identity is the ACTIVE PRE_V2 production runtime.
    assert result["runtime"]["model_id"] == "phase3-finetuned-v2"
    assert result["runtime"]["policy_version"] == "semantic-thresholds-v3"
    assert result["runtime"]["fail_closed"] is False


def test_demo_fixture_is_not_frozen_data() -> None:
    """The demo pairs must not appear in the frozen evaluation sets."""
    import json

    from razormesh_api.semantic_runtime import REPO_ROOT

    corpus_roots = [
        REPO_ROOT / "data" / "phase3" / "dataset" / "frozen_v2",
        REPO_ROOT / "data" / "agentpay_ir_v2" / "corpus",
    ]
    for root in corpus_roots:
        if not root.exists():
            continue
        for file in root.rglob("*.jsonl"):
            for line in file.read_text().splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                blob = json.dumps(row)
                for pair in NEW_DEMO_FIXTURE["pairs"]:
                    premise = pair["premise"]
                    hypothesis = pair["hypothesis"]
                    # no row-level copy of the demo text in any frozen set
                    assert premise not in blob, (file, pair["pair_id"])
                    assert hypothesis not in blob, (file, pair["pair_id"])


def test_api_route_serves_real_verdicts(client: TestClient) -> None:
    res = client.get("/security-lab/why-semantic-ai")
    assert res.status_code == 200
    body = res.json()
    assert body["label"] == "WHY SEMANTIC AI MATTERS"
    assert body["honest"] is True
    assert body["fixture"]["non_frozen"] is True
    assert body["fixture"]["not_used_for_model_selection"] is True
    assert all(r["fusion"] == "BLOCK" for r in body["demonstration"])


def test_demo_fails_closed_without_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """If the active model cannot run, the demo surfaces the failure —
    never a painted BLOCK."""

    def broken_verify(self, *, premise: str, hypothesis: str):  # type: ignore[no-untyped-def]
        raise RuntimeError("simulated model failure")

    from razormesh_api.semantic_verifier import DebertaNLISemanticVerifier

    monkeypatch.setattr(DebertaNLISemanticVerifier, "verify", broken_verify)
    with pytest.raises(RuntimeError):
        run_semantic_only_demo()
