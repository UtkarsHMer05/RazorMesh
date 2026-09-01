"""S002/F011: WHY SEMANTIC AI MATTERS — fully real-engine tightening.

Proves the demo contract honestly (master prompt S002):
- a NEW NON-FROZEN transaction is created per run through the real mission
  engine and driven through the REAL deterministic RazorGuard machinery
  (CheckoutService.propose/authorize) — its ALLOW is the real rule engine's
  verdict, and the ticket it genuinely MINTS proves the structured lane alone
  would move money;
- the ACTIVE PRE_V2 model (not a stub) produces the semantic BLOCK on the
  demo's new non-frozen pairs at runtime, in canonical orientation;
- the real `fuse` seam yields BLOCK (semantic only tightens);
- after the fused BLOCK the ticket is WITHHELD and provider calls are 0;
- the real revalidation gate is exercised and reported;
- fixture provenance is explicit: NEW_DEMO_FIXTURE, non-frozen, never used
  for model selection or calibration, and its text appears in no frozen set;
- if the model cannot run, the demo fails closed — never a painted result.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from conftest import wipe_business_tables
from razormesh_api.api.main import app
from razormesh_api.catalog import seed_catalog
from razormesh_api.persistence.db import create_session_factory
from razormesh_api.persistence.repositories import Repositories
from razormesh_api.semantic_only_demo import NEW_DEMO_FIXTURE, run_semantic_only_demo


@pytest.fixture()
def repos(settings):  # type: ignore[no-untyped-def]
    engine = create_engine(settings.database_url, future=True)
    r = Repositories(create_session_factory(engine))
    wipe_business_tables(engine)
    seed_catalog(r)
    yield r
    wipe_business_tables(engine)


@pytest.fixture()
def client(settings, repos):  # type: ignore[no-untyped-def]
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


def test_real_razorguard_allows_and_mints_ticket_then_semantic_blocks(repos: Repositories) -> None:
    """S002 core: the REAL deterministic machinery ALLOWS the structured
    transaction (and genuinely mints a ticket — proof structure alone would
    move money); the REAL active model BLOCKs; real fusion BLOCKs; ticket
    WITHHELD; provider calls 0."""
    result = run_semantic_only_demo(repos)
    assert result["honest"] is True, result["story"]

    # 1) The deterministic lane is the REAL rule engine over a fresh
    #    transaction — and it genuinely minted an ExecutionTicket.
    detail = result["structured_lane_detail"]
    assert detail["razorguard"] == "ALLOW"
    assert detail["ticket_would_mint"] is True, (
        "the real CheckoutService.authorize must actually mint the ticket on "
        "ALLOW — that is the whole point of the demo"
    )
    assert detail["revalidation_gate"] == "PASS"

    # 2) The demo transaction is real, fresh, non-frozen.
    txn = result["fixture"]["demo_transaction"]
    assert txn["intent_id"].startswith("intent_")
    assert txn["checkout_id"].startswith("chk_")
    assert txn["fresh_per_run"] is True

    # 3) Every demonstration row: real semantic BLOCK, real fusion BLOCK,
    #    ticket WITHHELD, provider 0.
    demo = result["demonstration"]
    assert len(demo) >= 2
    for row in demo:
        assert row["razorguard"] == "ALLOW"  # the real rule engine's verdict
        assert row["semantic"] == "BLOCK", row
        assert row["probabilities"]["contradiction"] > 0.9, row["probabilities"]
        assert row["fusion"] == "BLOCK"
        assert row["ticket"] == "WITHHELD"
        assert row["provider_calls"] == 0

    # 4) The runtime identity is the ACTIVE PRE_V2 production runtime.
    assert result["runtime"]["model_id"] == "phase3-finetuned-v2"
    assert result["runtime"]["policy_version"] == "semantic-thresholds-v3"
    assert result["runtime"]["fail_closed"] is False


def test_real_razorguard_invocation_is_provable(repos: Repositories) -> None:
    """The RazorGuard ALLOW is recorded by the real pipeline: a DECISION
    event + a TICKET_ISSUED event exist for the demo transaction's intent —
    proving the real authorize path ran (not an approximation)."""
    from sqlalchemy import select

    from razormesh_api.persistence.models import AuditEvent

    result = run_semantic_only_demo(repos)
    intent_id = result["fixture"]["demo_transaction"]["intent_id"]
    with repos.transaction() as session:
        events = (
            session.execute(
                select(AuditEvent.event_type).where(AuditEvent.intent_id == intent_id)
            )
            .scalars()
            .all()
        )
    assert "DECISION_RECORDED" in events, events
    assert "TICKET_ISSUED" in events, (
        "the real structured-lane authorization mints a ticket — audit proves it"
    )


def test_two_runs_use_fresh_transactions(repos: Repositories) -> None:
    """Each run is a NEW NON-FROZEN transaction (never a cached/replayed one)."""
    r1 = run_semantic_only_demo(repos)
    r2 = run_semantic_only_demo(repos)
    assert (
        r1["fixture"]["demo_transaction"]["intent_id"]
        != r2["fixture"]["demo_transaction"]["intent_id"]
    )


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
    assert body["structured_lane_detail"]["ticket_would_mint"] is True
    assert all(r["fusion"] == "BLOCK" for r in body["demonstration"])
    assert all(r["ticket"] == "WITHHELD" for r in body["demonstration"])
    assert all(r["provider_calls"] == 0 for r in body["demonstration"])


def test_demo_fails_closed_without_model(
    repos: Repositories, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If the active model cannot run, the demo surfaces the failure —
    never a painted BLOCK."""

    def broken_verify(self, *, premise: str, hypothesis: str):  # type: ignore[no-untyped-def]
        raise RuntimeError("simulated model failure")

    from razormesh_api.semantic_verifier import DebertaNLISemanticVerifier

    monkeypatch.setattr(DebertaNLISemanticVerifier, "verify", broken_verify)
    with pytest.raises(RuntimeError):
        run_semantic_only_demo(repos)
