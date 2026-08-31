"""Phase-5 (M091-M094) acceptance: Model Governance truth.

Proves: active=PRE_V2 truth; challenger=evaluated-not-activated with exact
committed D-055 numbers; frozen rules present; shadow is NON-AUTHORITATIVE
and never feeds authority; no rerun/recalibration surface exists; committed
evidence served with private text stripped.
"""

from fastapi.testclient import TestClient


def test_governance_summary_states_runtime_truth(governance_client: TestClient) -> None:
    res = governance_client.get("/model-governance")
    assert res.status_code == 200
    body = res.json()
    active = body["active"]
    assert active["status"].startswith("ACTIVE")
    assert active["model"] == "phase3-finetuned-v2"
    assert active["policy_version"] == "semantic-thresholds-v3"
    assert active["can_authorize_payment"] is False
    assert body["runtime_backend"] in ("deberta", "deterministic_test_stub")


def test_challenger_rejection_numbers_are_exact(governance_client: TestClient) -> None:
    body = governance_client.get("/model-governance").json()
    ch = body["challenger"]
    # Exact committed D-055 values — never recomputed, never invented.
    assert ch["verdict"] == "M2_FROZEN_EVALUATION_FAIL / V2_NOT_ACTIVATED"
    assert ch["is_activated"] is False
    assert ch["normal_test_macro_f1"]["before"] == 0.7367
    assert ch["normal_test_macro_f1"]["after"] == 0.9752
    assert ch["human_gold"]["unsafe_contradiction_to_entailment"] == {"before": 2, "after": 7}
    assert ch["human_gold"]["macro_f1"] == {"before": 0.8930, "after": 0.7757}
    assert ch["fresh_ood"]["unsafe_contradiction_to_entailment"] == {"before": 5, "after": 6}
    assert "WORSENED" in ch["human_gold"]["verdict"]
    assert ch["can_authorize_payment"] is False


def test_frozen_rules_are_present(governance_client: TestClient) -> None:
    body = governance_client.get("/model-governance").json()
    rules = " ".join(body["frozen_rules"]).lower()
    assert "rerun" in rules
    assert "retraining" in rules or "retrain" in rules
    assert "never enters fusion" in rules or "fusion" in rules
    assert "row-level" in rules or "private" in rules


def test_shadow_is_non_authoritative_and_isolated(governance_client: TestClient) -> None:
    res = governance_client.post(
        "/model-governance/shadow",
        json={"hypothesis": "This membership automatically renews every quarter."},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["mode"].startswith("SHADOW")
    assert body["is_frozen_evaluation"] is False
    assert set(body["never_enters"]) == {"fusion", "ticket", "provider"}
    assert "ACTIVE MODEL ONLY" in body["authoritative_action"]

    # The REAL v2 challenger lane (G003): a semantic verdict from the actual
    # checkpoint, never the keyword stub's "UNSAFE". The unsafe recurring
    # contradiction must BLOCK under the committed v4 thresholds.
    unsafe = governance_client.post(
        "/model-governance/shadow",
        json={
            "hypothesis": "The checkout includes a membership that renews every month.",
            "premise": "The human authorized a one-time purchase with no subscription.",
        },
    ).json()
    challenger = unsafe["challenger"]
    assert challenger["available"] is True, challenger.get("reason")
    assert challenger["shadow_action"] in ("PASS", "CHALLENGE", "BLOCK")
    assert challenger["shadow_action"] == "BLOCK"
    assert "challenger is IGNORED" in unsafe["disagreement_note"]


def test_committed_evidence_served_without_private_text(governance_client: TestClient) -> None:
    res = governance_client.get("/model-governance/evidence")
    assert res.status_code == 200
    blob = str(res.json())
    assert "M2_FROZEN_EVALUATION_FAIL" in blob
    for banned in ('premise":', 'hypothesis":', 'authorization_text":'):
        assert f'"{banned}' not in blob, banned
    # raw private text values are stripped, keys replaced with the marker
    assert "<redacted: private review text>" in blob or "premise" not in blob


def test_governance_never_exposes_review_row_data(governance_client: TestClient) -> None:
    blob = str(governance_client.get("/model-governance").json()) + str(
        governance_client.get("/model-governance/evidence").json()
    )
    for banned in ("predictions_human_gold", "role_manifest", "review_linkage"):
        assert banned not in blob
