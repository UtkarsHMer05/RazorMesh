"""P3-M16: human confirmation domain flow — the authority gate.

Proves P3-S03 mechanically: an AI-produced draft becomes durable authorization
ONLY through confirm_draft(); everything else (rejection, supersession,
clarification gating, provider failure) creates none. Concurrency, replay,
stale-draft, fail-closed money, and audit-chain properties are release-blocking.
"""

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest

from razormesh_api.clock import Clock
from razormesh_api.confirmation_service import (
    ConfirmationError,
    HumanConfirmationService,
)
from razormesh_api.domain.confirmation import DraftState
from razormesh_api.domain.ids import AgentId, DraftId, PrincipalId, new_ulid
from razormesh_api.domain.intent_draft import (
    Ambiguity,
    CompilerIntentPayload,
    HardConstraints,
    MoneyBound,
)
from razormesh_api.intent_compilation_service import CompilerOutcome
from razormesh_api.ledger import EvidenceLedger
from razormesh_api.persistence.models import (
    AuthorizationSpend,
    ExecutionAttempt,
)
from razormesh_api.persistence.repositories import Repositories
from razormesh_api.settings import get_settings

PRINCIPAL_HOLDER: dict[str, str] = {}


class _FixedClock(Clock):
    def __init__(self) -> None:
        self._now = datetime(2026, 8, 26, 12, 0, 0, tzinfo=UTC)

    def now_utc(self) -> datetime:
        self._now = self._now + timedelta(seconds=1)
        return self._now


@pytest.fixture()
def conf_env(tmp_path):  # type: ignore[no-untyped-def]
    from sqlalchemy import create_engine

    from razormesh_api.keys import DevSigningKeys
    from razormesh_api.persistence.db import create_session_factory

    engine = create_engine(get_settings().database_url, future=True)
    repos = Repositories(create_session_factory(engine))
    keys = DevSigningKeys(
        private_path=str(tmp_path / "p.pem"), public_path=str(tmp_path / "pub.pem")
    ).ensure()
    ledger = EvidenceLedger(repos)
    svc = HumanConfirmationService(repos, ledger, _FixedClock())
    # Fresh authorization LINEAGE per test: generation arithmetic and stale
    # checks must never see another test's contracts/drafts.
    principal_id = str(PrincipalId.generate())
    agent_id = str(AgentId.generate())
    PRINCIPAL_HOLDER["principal"] = principal_id
    yield repos, keys, ledger, svc, principal_id, agent_id
    # NOTE: audit_events is DB-protected append-only (S11) — never deleted.
    with repos.transaction() as s:
        from razormesh_api.persistence.models import IntentDraftRecord

        s.query(IntentDraftRecord).delete()
        s.query(ExecutionAttempt).delete()
        s.query(AuthorizationSpend).delete()


def _outcome_ok(**hard_kwargs) -> CompilerOutcome:  # type: ignore[no-untyped-def]
    payload = CompilerIntentPayload(
        schema_version="agentpay-intent-draft-v1",
        product_summary="wireless headphones",
        hard=HardConstraints(
            max_amount=MoneyBound(amount_minor=500000, currency="INR"),
            **hard_kwargs,
        ),
    )
    return CompilerOutcome(
        status="OK",
        payload=payload,
        attempts=1,
        error_code=None,
        detail=None,
        request_ids=("req-1",),
    )


def _record(svc, repos, principal: str, agent: str, **kwargs) -> DraftId:  # type: ignore[no-untyped-def]
    rec = svc.record_compilation(
        principal_id=PrincipalId(principal),
        agent_id=AgentId(agent),
        source_text_sha256="a" * 64,
        outcome=kwargs.pop("outcome", _outcome_ok()),
        **kwargs,
    )
    assert rec.draft_id is not None and rec.state is not None
    return rec.draft_id


def _spend_row(repos, intent_id: str):  # type: ignore[no-untyped-def]
    with repos.transaction() as s:
        row = s.get(AuthorizationSpend, intent_id)
        assert row is not None
        return row


# ---------------------------------------------------------------------------
# Recording semantics
# ---------------------------------------------------------------------------


def test_ok_without_ambiguities_lands_in_DRAFT(conf_env) -> None:  # type: ignore[no-untyped-def]
    repos, _keys, _ledger, svc, principal, agent = conf_env
    draft_id = _record(svc, repos, principal, agent)
    row = svc.get_draft(draft_id)
    assert row is not None and row.state == DraftState.DRAFT.value


def test_ambiguities_force_NEEDS_CLARIFICATION(conf_env) -> None:  # type: ignore[no-untyped-def]
    _repos, _keys, _ledger, svc, principal, agent = conf_env
    payload = CompilerIntentPayload(
        schema_version="agentpay-intent-draft-v1",
        product_summary="camera",
        ambiguities=(Ambiguity(question="Mirrorless or DSLR?", options=("m", "d")),),
    )
    outcome = CompilerOutcome("OK", payload, 1, None, None, ("r",))
    rec = svc.record_compilation(
        principal_id=PrincipalId(principal),
        agent_id=AgentId(agent),
        source_text_sha256="b" * 64,
        outcome=outcome,
    )
    assert rec.state == DraftState.NEEDS_CLARIFICATION
    row = svc.get_draft(rec.draft_id)
    assert row is not None
    with pytest.raises(ConfirmationError) as excinfo:
        svc.confirm_draft(draft_id=rec.draft_id, confirmation_nonce="n1", actor="human")
    assert excinfo.value.code == "DRAFT_NOT_CONFIRMABLE"


def test_failed_compilation_creates_no_draft_but_audits(conf_env) -> None:  # type: ignore[no-untyped-def]
    repos, _keys, _ledger, svc, principal, agent = conf_env
    outcome = CompilerOutcome("FAILED", None, 2, "SCHEMA_INVALID_AFTER_REPAIR", "bad", ("r",))
    rec = svc.record_compilation(
        principal_id=PrincipalId(principal),
        agent_id=AgentId(agent),
        source_text_sha256="c" * 64,
        outcome=outcome,
    )
    assert rec.draft_id is None and rec.state is None
    with repos.transaction() as s:
        count = (
            s.query(_draft_model()).filter_by(principal_id=PRINCIPAL_HOLDER["principal"]).count()
        )
        assert count == 0
    types = _event_types(repos)
    assert "INTENT_COMPILE_FAILED" in types
    assert EvidenceLedger(repos).verify().valid


def test_fresh_compile_supersedes_open_drafts(conf_env) -> None:  # type: ignore[no-untyped-def]
    repos, _keys, _ledger, svc, principal, agent = conf_env
    first = _record(svc, repos, principal, agent)
    ambiguous = CompilerOutcome(
        "OK",
        CompilerIntentPayload(
            schema_version="agentpay-intent-draft-v1",
            product_summary="camera",
            ambiguities=(Ambiguity(question="Which mount?", options=("ef",)),),
        ),
        1,
        None,
        None,
        ("r2",),
    )
    rec = svc.record_compilation(
        principal_id=PrincipalId(principal),
        agent_id=AgentId(agent),
        source_text_sha256="d" * 64,
        outcome=ambiguous,
    )
    assert rec.superseded_draft_ids == (first,)
    stale = svc.get_draft(first)
    assert stale is not None and stale.superseded_by == str(rec.draft_id)

    with pytest.raises(ConfirmationError) as excinfo:
        svc.confirm_draft(draft_id=first, confirmation_nonce="n", actor="human")
    assert excinfo.value.code == "DRAFT_STALE"

    fresh = svc.get_draft(rec.draft_id)
    assert fresh is not None and fresh.state in {
        DraftState.DRAFT.value,
        DraftState.NEEDS_CLARIFICATION.value,
    }


def _draft_model():  # type: ignore[no-untyped-def]
    from razormesh_api.persistence.models import IntentDraftRecord

    return IntentDraftRecord


def _event_types(repos, draft_id: str | None = None) -> list[str]:  # type: ignore[untyped-def]

    from razormesh_api.persistence.models import AuditEvent as LedgerRow

    with repos.transaction() as s:
        rows = [(r.event_type, r.metadata_json) for r in s.query(LedgerRow).all()]
    if draft_id is None:
        return [t for t, _ in rows]
    return [
        t
        for t, payload in rows
        if (isinstance(payload, dict) and payload.get("draft_id") == draft_id)
        or (
            t == "INTENT_DRAFT_SUPERSEDED"
            and isinstance(payload, dict)
            and (
                payload.get("draft_id") == draft_id
                or payload.get("superseded_draft_id") == draft_id
            )
        )
    ]


# ---------------------------------------------------------------------------
# Confirmation → authority materialization
# ---------------------------------------------------------------------------


def test_confirm_creates_generation_one_with_conservative_terms(conf_env) -> None:  # type: ignore[no-untyped-def]
    repos, _keys, _ledger, svc, principal, agent = conf_env
    draft_id = _record(
        svc,
        repos,
        principal,
        agent,
        outcome=_outcome_ok(brand_allowlist=("Sony", "BoAt"), quantity_max=3),
    )
    result = svc.confirm_draft(
        draft_id=draft_id, confirmation_nonce=f"nonce-{new_ulid()}", actor="human"
    )
    assert result.replayed is False and result.generation == 1

    row_contract = repos.intents.get(result.intent_id)
    assert row_contract is not None
    assert row_contract.max_total_minor == 500000
    # conservative defaults: aggregate==cap, threshold==cap, recurring forbidden
    assert row_contract.aggregate_budget_minor == 500000
    assert row_contract.approval_threshold_minor == 500000
    assert row_contract.recurring_allowed is False  # human never allowed recurrence
    assert row_contract.authorization_generation == 1
    brand_dump = row_contract.brand_restriction or {}
    brands = {str(b).lower() for b in brand_dump.get("brands", [])}
    assert brands == {"sony", "boat"}
    assert row_contract.expires_at > row_contract.authorized_at

    row = svc.get_draft(draft_id)
    assert row is not None
    assert row.state == DraftState.CONFIRMED.value and row.intent_id == str(result.intent_id)
    assert "INTENT_CONFIRMED" in _event_types(repos, str(draft_id))


def test_replay_same_nonce_is_idempotent_no_new_authority(conf_env) -> None:  # type: ignore[no-untyped-def]
    repos, _keys, _ledger, svc, principal, agent = conf_env
    draft_id = _record(svc, repos, principal, agent)
    nonce = f"nonce-{new_ulid()}"
    first = svc.confirm_draft(draft_id=draft_id, confirmation_nonce=nonce, actor="human")
    again = svc.confirm_draft(draft_id=draft_id, confirmation_nonce=nonce, actor="human")
    assert again.replayed is True
    assert (again.intent_id, again.generation) == (first.intent_id, first.generation)
    contract = repos.intents.get(first.intent_id)
    assert contract is not None and contract.authorization_generation == 1


def test_replay_with_different_nonce_is_rejected(conf_env) -> None:  # type: ignore[no-untyped-def]
    repos, _keys, _ledger, svc, principal, agent = conf_env
    draft_id = _record(svc, repos, principal, agent)
    svc.confirm_draft(draft_id=draft_id, confirmation_nonce="nonce-A", actor="human")
    with pytest.raises(ConfirmationError) as excinfo:
        svc.confirm_draft(draft_id=draft_id, confirmation_nonce="nonce-B", actor="human")
    assert excinfo.value.code == "CONFIRMATION_REPLAY_MISMATCH"


def test_second_confirmation_supersedes_generation_reusing_intent(conf_env) -> None:  # type: ignore[no-untyped-def]
    repos, _keys, _ledger, svc, principal, agent = conf_env
    d1 = _record(svc, repos, principal, agent)
    r1 = svc.confirm_draft(draft_id=d1, confirmation_nonce=f"n-{new_ulid()}", actor="human")
    # a fresh compile supersedes nothing terminal; it opens its own draft
    d2 = _record(svc, repos, principal, agent, outcome=_outcome_ok())
    r2 = svc.confirm_draft(draft_id=d2, confirmation_nonce=f"n-{new_ulid()}", actor="human")
    assert r2.generation == r1.generation + 1
    assert r2.intent_id == r1.intent_id  # same lineage identity
    contract = repos.intents.get(r1.intent_id)
    assert contract is not None and contract.authorization_generation == 2


def test_confirm_missing_money_fails_closed_and_creates_nothing(conf_env) -> None:  # type: ignore[no-untyped-def]
    repos, _keys, _ledger, svc, principal, agent = conf_env
    poor = CompilerOutcome(
        "OK",
        CompilerIntentPayload(schema_version="agentpay-intent-draft-v1", product_summary="mystery"),
        1,
        None,
        None,
        ("r",),
    )
    draft_id = _record(svc, repos, principal, agent, outcome=poor)
    with pytest.raises(ConfirmationError) as excinfo:
        svc.confirm_draft(draft_id=draft_id, confirmation_nonce=f"n-{new_ulid()}", actor="human")
    assert excinfo.value.code == "DRAFT_MISSING_MONEY"
    with repos.transaction() as s:
        from razormesh_api.persistence.models import IntentContract as Row

        count = s.query(Row).filter_by(principal_id=PRINCIPAL_HOLDER["principal"]).count()
        assert count == 0
    row = svc.get_draft(draft_id)
    assert row is not None and row.state == DraftState.DRAFT.value  # unchanged


def test_unsupported_currency_fails_closed(conf_env) -> None:  # type: ignore[no-untyped-def]
    repos, _keys, _ledger, svc, principal, agent = conf_env
    weird = _outcome_ok()
    from razormesh_api.domain.intent_draft import MoneyBound as MB

    payload = CompilerIntentPayload(
        schema_version="agentpay-intent-draft-v1",
        product_summary="gadget",
        hard=HardConstraints(max_amount=MB(amount_minor=100, currency="XYZ")),
    )
    outcome = CompilerOutcome("OK", payload, 1, None, None, ("r",))
    draft_id = _record(svc, repos, principal, agent, outcome=outcome)
    del weird
    with pytest.raises(ConfirmationError) as excinfo:
        svc.confirm_draft(draft_id=draft_id, confirmation_nonce=f"n-{new_ulid()}", actor="human")
    assert excinfo.value.code == "DRAFT_UNSUPPORTED_CURRENCY"


def test_invalid_nonces_rejected(conf_env) -> None:  # type: ignore[no-untyped-def]
    repos, _keys, _ledger, svc, principal, agent = conf_env
    draft_id = _record(svc, repos, principal, agent)
    for bad in ("", "n" * 129):
        with pytest.raises(ConfirmationError) as excinfo:
            svc.confirm_draft(draft_id=draft_id, confirmation_nonce=bad, actor="human")
        assert excinfo.value.code == "INVALID_NONCE"
    with pytest.raises(ConfirmationError) as missing:
        svc.confirm_draft(draft_id=DraftId(f"drf_{new_ulid()}"), confirmation_nonce="n", actor="h")
    assert missing.value.code == "DRAFT_NOT_FOUND"


# ---------------------------------------------------------------------------
# Rejection
# ---------------------------------------------------------------------------


def test_reject_is_terminal_idempotent_and_audited(conf_env) -> None:  # type: ignore[no-untyped-def]
    repos, _keys, _ledger, svc, principal, agent = conf_env
    draft_id = _record(svc, repos, principal, agent)
    state1 = svc.reject_draft(draft_id=draft_id, actor="human")
    state2 = svc.reject_draft(draft_id=draft_id, actor="human")
    assert state1 == state2 == DraftState.REJECTED
    with pytest.raises(ConfirmationError) as excinfo:
        svc.confirm_draft(draft_id=draft_id, confirmation_nonce="n", actor="human")
    assert excinfo.value.code == "DRAFT_NOT_CONFIRMABLE"
    types = _event_types(repos, str(draft_id))
    assert types.count("INTENT_REJECTED") == 1  # second reject was a no-op


def test_cannot_reject_after_confirmation(conf_env) -> None:  # type: ignore[no-untyped-def]
    repos, _keys, _ledger, svc, principal, agent = conf_env
    draft_id = _record(svc, repos, principal, agent)
    svc.confirm_draft(draft_id=draft_id, confirmation_nonce=f"n-{new_ulid()}", actor="human")
    with pytest.raises(ConfirmationError) as excinfo:
        svc.reject_draft(draft_id=draft_id, actor="human")
    assert excinfo.value.code == "DRAFT_NOT_REJECTABLE"


# ---------------------------------------------------------------------------
# Supersession vs committed spend
# ---------------------------------------------------------------------------


def test_new_cap_below_committed_spend_refused(conf_env) -> None:  # type: ignore[no-untyped-def]
    repos, _keys, _ledger, svc, principal, agent = conf_env
    d1 = _record(svc, repos, principal, agent)
    r1 = svc.confirm_draft(draft_id=d1, confirmation_nonce=f"n-{new_ulid()}", actor="human")

    # Simulate durable spend at the current cap (as an executed attempt would).
    with repos.transaction() as s:
        s.add(
            AuthorizationSpend(
                intent_id=str(r1.intent_id),
                authorized_minor=500000,
                reserved_minor=0,
                committed_minor=400000,
                version=3,
                updated_at=datetime.now(UTC),
            )
        )

    smaller = CompilerOutcome(
        "OK",
        CompilerIntentPayload(
            schema_version="agentpay-intent-draft-v1",
            product_summary="cheaper thing",
            hard=HardConstraints(max_amount=MoneyBound(amount_minor=100000, currency="INR")),
        ),
        1,
        None,
        None,
        ("r",),
    )
    d2 = _record(svc, repos, principal, agent, outcome=smaller)
    with pytest.raises(ConfirmationError) as excinfo:
        svc.confirm_draft(draft_id=d2, confirmation_nonce=f"n-{new_ulid()}", actor="human")
    assert excinfo.value.code == "DRAFT_BELOW_COMMITTED_SPEND"


# ---------------------------------------------------------------------------
# Concurrency: one lineage, simultaneous confirmations of the SAME draft
# ---------------------------------------------------------------------------


def test_concurrent_same_nonce_confirm_yields_single_authority(conf_env) -> None:  # type: ignore[no-untyped-def]
    repos, _keys, _ledger, svc, principal, agent = conf_env
    draft_id = _record(svc, repos, principal, agent)
    nonce = f"nonce-{new_ulid()}"

    def worker(_i: int):  # type: ignore[no-untyped-def]
        try:
            return svc.confirm_draft(draft_id=draft_id, confirmation_nonce=nonce, actor="human")
        except ConfirmationError as exc:
            return exc  # loser must be a CONTROLLED error, never corruption

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(worker, range(8)))

    successes = [r for r in results if not isinstance(r, ConfirmationError)]
    errors = [r for r in results if isinstance(r, ConfirmationError)]
    assert len(successes) >= 1
    ids = {(r.intent_id, r.generation) for r in successes}
    assert len(ids) == 1  # ONE authority identity regardless of interleaving
    for err in errors:
        assert err.code in {"CONFIRMATION_REPLAY_MISMATCH", "DRAFT_NOT_CONFIRMABLE"}

    with repos.transaction() as s:
        from razormesh_api.persistence.models import IntentContract as Row

        rows = s.query(Row).filter_by(principal_id=PRINCIPAL_HOLDER["principal"]).all()
        assert len(rows) == 1
        assert rows[0].authorization_generation == 1
    assert EvidenceLedger(repos).verify().valid


# ---------------------------------------------------------------------------
# Raw human text is never stored
# ---------------------------------------------------------------------------


def test_no_raw_text_persistence(conf_env) -> None:  # type: ignore[no-untyped-def]
    secret_phrase = "my-secret-nano-text-xyzzy"
    _repos, _keys, _ledger, svc, principal, agent = conf_env
    outcome = _outcome_ok()
    rec = svc.record_compilation(
        principal_id=PrincipalId(principal),
        agent_id=AgentId(agent),
        source_text_sha256=hashlib.sha256(secret_phrase.encode()).hexdigest(),
        outcome=outcome,
    )
    row = svc.get_draft(rec.draft_id)
    assert row is not None
    dumped = json.dumps(row.payload)
    assert secret_phrase not in dumped
    assert row.source_text_sha256 == hashlib.sha256(secret_phrase.encode()).hexdigest()
