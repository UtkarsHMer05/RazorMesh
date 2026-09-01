"""R002 (extends S002/F011): WHY SEMANTIC AI MATTERS — real engines, real
AUTHORITY ORDER.

The security statement under test is now literally:
    semantic BLOCK prevents ticket creation.

Proven per run:
 1. the REAL deterministic engine (DecisionEngine.decide at the pre-issuance
    seam — the same evaluation the authorize stage performs) was invoked;
 2. its verdict on the structured facts is ALLOW;
 3. the REAL active PRE_V2 model runs (runtime identity reported);
 4. canonical NLI orientation (premise = commerce evidence, hypothesis =
    human authorization);
 5. the semantic result is engine-produced (probabilities sum to 1, high
    contradiction);
 6. the REAL fuse(ALLOW, BLOCK) returns BLOCK;
 7. the ticket-issuance function was NEVER called (authorize() is not part
    of the demo path — proven by absence of both its audit events and rows);
 8. ticket count does not increase across the demo;
 9. execution-attempt count does not increase;
10. provider-call count remains 0 (unchanged);
11. two runs use fresh NEW/NON-FROZEN transactions;
12. frozen test/gold/OOD files are untouched (fixture text absent).
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select

from conftest import wipe_business_tables
from razormesh_api.api.main import app
from razormesh_api.catalog import seed_catalog
from razormesh_api.persistence.db import create_session_factory
from razormesh_api.persistence.models import (
    AuditEvent,
    ExecutionAttempt,
    ExecutionTicket,
    IntentContract,
)
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


def _counts(repos: Repositories) -> dict[str, int]:
    with repos.transaction() as session:
        return {
            "tickets": int(
                session.scalar(select(func.count()).select_from(ExecutionTicket)) or 0
            ),
            "attempts": int(
                session.scalar(select(func.count()).select_from(ExecutionAttempt)) or 0
            ),
        }


def test_r002_authority_order_end_to_end(repos: Repositories) -> None:
    """The full security statement: semantic BLOCK prevents ticket creation."""
    before = _counts(repos)
    result = run_semantic_only_demo(repos)
    after = _counts(repos)
    assert result["honest"] is True, result["story"]

    # (1)+(2) REAL deterministic engine ALLOW on structured facts.
    detail = result["structured_lane_detail"]
    assert detail["razorguard"] == "ALLOW"
    assert detail["policy_version"], "real engine reports its policy version"

    # (3)+(4)+(5) REAL PRE_V2 model, canonical orientation, engine output.
    assert result["runtime"]["model_id"] == "phase3-finetuned-v2"
    assert result["runtime"]["policy_version"] == "semantic-thresholds-v3"
    assert "premise=commerce evidence" in result["fixture"]["orientation"]

    demo = result["demonstration"]
    assert len(demo) >= 2
    for row in demo:
        assert row["razorguard"] == "ALLOW"
        assert row["semantic"] == "BLOCK", row
        probs = row["probabilities"]
        total = sum(probs.values())
        assert 0.99 <= total <= 1.01  # engine-produced, not painted
        assert probs["contradiction"] > 0.9
        # (6) real fuse → BLOCK; (7) ticket NOT ISSUED; attempts NOT CREATED;
        # provider 0.
        assert row["fusion"] == "BLOCK"
        assert row["ticket"] == "NOT ISSUED", row
        assert row["execution_attempt"] == "NOT CREATED", row
        assert row["provider_calls"] == 0

    # (8)+(9)+(10) durable counts unchanged: no ticket, no attempt, no call.
    assert after["tickets"] == before["tickets"], "ticket count must not grow"
    assert after["attempts"] == before["attempts"], "attempt count must not grow"
    proof = result["authority_proof"]
    assert proof["ticket_minted"] is False
    assert proof["tickets_before"] == proof["tickets_after"]
    assert proof["attempts_before"] == proof["attempts_after"]
    assert proof["provider_calls_before"] == proof["provider_calls_after"]

    # The demo transaction is real and fresh.
    txn = result["fixture"]["demo_transaction"]
    assert txn["intent_id"].startswith("intent_")
    assert txn["checkout_id"].startswith("chk_")
    assert txn["fresh_per_run"] is True


def test_r002_no_ticket_or_authorize_events_for_demo_txn(repos: Repositories) -> None:
    """The issuance function was NEVER called for the demo transaction: its
    audit trail shows a proposal but NO DECISION_RECORDED / TICKET_ISSUED /
    TICKET_WITHHELD from authorize(), and no ticket/attempt rows exist."""
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
        tickets_for_intent = int(
            session.scalar(
                select(func.count())
                .select_from(ExecutionTicket)
                .where(ExecutionTicket.intent_id == intent_id)
            )
            or 0
        )
    # The proposal ran (CHECKOUT_PROPOSED via the mission engine)…
    assert "CHECKOUT_PROPOSED" in events, events
    # …but the issuance path never did:
    assert "DECISION_RECORDED" not in events, (
        "authorize() ran for the demo transaction — R002 violated"
    )
    assert "TICKET_ISSUED" not in events, (
        "a ticket was minted for the demo transaction — R002 violated"
    )
    assert tickets_for_intent == 0, "no ticket row may exist for the demo intent"


def test_r002_two_runs_fresh_transactions(repos: Repositories) -> None:
    """(11) Each run is a NEW NON-FROZEN transaction (never cached/replayed)."""
    before = _counts(repos)
    r1 = run_semantic_only_demo(repos)
    r2 = run_semantic_only_demo(repos)
    assert (
        r1["fixture"]["demo_transaction"]["intent_id"]
        != r2["fixture"]["demo_transaction"]["intent_id"]
    )
    assert (
        r1["fixture"]["demo_transaction"]["checkout_id"]
        != r2["fixture"]["demo_transaction"]["checkout_id"]
    )
    # Neither run minted anything.
    assert _counts(repos) == before


def test_r002_fixture_not_frozen_data() -> None:
    """(12) The demo pairs appear in no frozen set; the fixture is
    NEW/NON-FROZEN and never used for selection or calibration."""
    assert NEW_DEMO_FIXTURE["provenance"] == "NEW_DEMO_FIXTURE"
    assert NEW_DEMO_FIXTURE["frozen"] is False
    assert NEW_DEMO_FIXTURE["used_for_model_selection"] is False
    assert NEW_DEMO_FIXTURE["used_for_threshold_calibration"] is False
    assert "premise=commerce evidence" in NEW_DEMO_FIXTURE["canonical_orientation"]

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
                blob = line
                for pair in NEW_DEMO_FIXTURE["pairs"]:
                    assert pair["premise"] not in blob, (file, pair["pair_id"])
                    assert pair["hypothesis"] not in blob, (file, pair["pair_id"])


def test_r002_api_route_serves_authority_order(client: TestClient) -> None:
    res = client.get("/security-lab/why-semantic-ai")
    assert res.status_code == 200
    body = res.json()
    assert body["label"] == "WHY SEMANTIC AI MATTERS"
    assert body["honest"] is True
    assert body["fixture"]["non_frozen"] is True
    assert body["fixture"]["not_used_for_model_selection"] is True
    for row in body["demonstration"]:
        assert row["razorguard"] == "ALLOW"
        assert row["semantic"] == "BLOCK"
        assert row["fusion"] == "BLOCK"
        assert row["ticket"] == "NOT ISSUED"
        assert row["execution_attempt"] == "NOT CREATED"
        assert row["provider_calls"] == 0
    assert body["authority_proof"]["ticket_minted"] is False
    assert json.dumps(body), "response is JSON-serializable"


def test_r002_demo_fails_closed_without_model(
    repos: Repositories, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If the active model cannot run, the demo surfaces the failure — and
    still mints nothing."""

    def broken_verify(self, *, premise: str, hypothesis: str):  # type: ignore[no-untyped-def]
        raise RuntimeError("simulated model failure")

    from razormesh_api.semantic_verifier import DebertaNLISemanticVerifier

    monkeypatch.setattr(DebertaNLISemanticVerifier, "verify", broken_verify)
    before = _counts(repos)
    with pytest.raises(RuntimeError):
        run_semantic_only_demo(repos)
    assert _counts(repos) == before, "fail-closed run mints nothing"


def test_r002_intent_row_exists_but_unticketed(repos: Repositories) -> None:
    """The demo transaction is durable (real intent row) yet completely
    unticketed — structured evidence, no authority artifacts."""
    result = run_semantic_only_demo(repos)
    intent_id = result["fixture"]["demo_transaction"]["intent_id"]
    with repos.transaction() as session:
        row = session.get(IntentContract, intent_id)
    assert row is not None, "the demo transaction is real and durable"
    assert result["authority_proof"]["tickets_after"] == result[
        "authority_proof"
    ]["tickets_before"]
