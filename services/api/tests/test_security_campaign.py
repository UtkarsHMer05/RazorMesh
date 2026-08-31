"""Phase-5 (M074-M077) acceptance: AgentPay-X live campaign + taxonomy.

Proves: canonical engine only (counters verbatim from run_benchmark), no
fabricated 191/191 claims, per-case explorer from real metadata, read-only
case replay agreeing with the recorded result, attack taxonomy complete.
"""

from fastapi.testclient import TestClient


def test_campaign_summary_is_canonical(security_campaign_client: TestClient) -> None:
    res = security_campaign_client.get("/security-campaign/summary")
    assert res.status_code == 200
    s = res.json()
    assert s["total"] == 191
    assert s["safe_total"] == 37
    assert s["attack_total"] == 154
    # The canonical gate's headline rates (from run_benchmark itself):
    assert s["safe_pass"] == 1.0
    assert s["attack_block"] == 1.0
    assert s["false_allows"] == 0
    assert s["false_blocks"] == 0
    assert s["exactly_once_violations"] == 0
    assert s["benchmark_version"] == "agentpay-x-2026-08-27-phase4-gate-v1"


def test_taxonomy_covers_every_scenario(security_campaign_client: TestClient) -> None:
    res = security_campaign_client.get("/security-campaign/families")
    fams = res.json()["families"]
    total = sum(f["count"] for f in fams)
    assert total == 191, "every registered scenario must appear in the taxonomy"
    # Safe families exist and attacks dominate, matching the registry.
    assert sum(f["attack"] for f in fams) == 154
    assert sum(f["safe"] for f in fams) == 37
    for f in fams:
        assert f["count"] == f["safe"] + f["attack"]


def test_case_explorer_filters_by_family_and_outcome(
    security_campaign_client: TestClient,
) -> None:
    all_cases = security_campaign_client.get("/security-campaign/cases").json()
    assert all_cases["count"] == 191
    first = all_cases["cases"][0]
    assert first["scenario_id"].startswith("AX-")
    assert first["mutation"]
    assert first["actual_final"] in ("ALLOW", "CHALLENGE", "BLOCK")

    fam = security_campaign_client.get(
        "/security-campaign/cases", params={"family": "amount_mutation"}
    ).json()
    assert fam["count"] > 0
    assert all(c["family"] == "amount_mutation" for c in fam["cases"])

    blocked = security_campaign_client.get(
        "/security-campaign/cases", params={"outcome": "BLOCK"}
    ).json()
    assert blocked["count"] > 0
    assert all(c["actual_final"] == "BLOCK" for c in blocked["cases"])


def test_case_replay_is_read_only_and_agrees(security_campaign_client: TestClient) -> None:
    cases = security_campaign_client.get(
        "/security-campaign/cases", params={"family": "amount_mutation"}
    ).json()["cases"]
    target = cases[0]["scenario_id"]
    res = security_campaign_client.get(f"/security-campaign/case/{target}/replay")
    assert res.status_code == 200
    replay = res.json()
    assert replay["read_only"] is True
    by_stage = {s["stage"]: s["status"] for s in replay["stages"]}
    assert by_stage["protocol"] == cases[0]["actual_firewall"]
    assert by_stage["razorguard"] == cases[0]["actual_final"]
    assert by_stage["provider"] == "NOT CONTACTED"
    assert by_stage["ticket"] == "WITHHELD" if cases[0]["actual_final"] == "BLOCK" else True


def test_unknown_scenario_is_404(security_campaign_client: TestClient) -> None:
    assert security_campaign_client.get("/security-campaign/case/AX-ZZZ/replay").status_code == 404


def test_no_raw_payloads_or_keys_leak(security_campaign_client: TestClient) -> None:
    for path in (
        "/security-campaign/summary",
        "/security-campaign/families",
        "/security-campaign/cases?family=amount_mutation",
    ):
        blob = str(security_campaign_client.get(path).json())
        for banned in ("BEGIN PRIVATE KEY", "rzp_live_", "key_secret"):
            assert banned not in blob
