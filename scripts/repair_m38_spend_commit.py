#!/usr/bin/env python3
"""P2-M38 one-time guarded repair: commit payment #2's stranded reservation.

Root cause (fixed in code the same milestone): webhooks._reducer() built the
ProviderStateReducer WITHOUT a SpendManager, so when the payment.captured
webhook settled attempt exa_01M0TFCS608MSJ59GHHVJ5NP8E to SUCCEEDED, the
executor's _settle() skipped the spend block and the reservation stayed
reserved_minor=239800 / committed_minor=0. The same defect left provider_name
at its column default 'mock' for a real Razorpay execution.

This script repairs ONLY that specific, evidence-identified attempt:
- asserts the exact attempt id, state, amount and Razorpay correlation;
- converts reserved -> committed via the regular SpendManager.commit()
  (row-locked, versioned), idempotent (a re-run finds reserved=0 and stops);
- corrects provider_name to 'razorpay' (the razorpay order/payment ids on the
  row prove the provider);
- appends one tamper-evident audit event describing the repair.

Prints no secrets. Run:
  uv run --project services/api python scripts/repair_m38_spend_commit.py
"""

from __future__ import annotations

ATTEMPT_ID = "exa_01M0TFCS608MSJ59GHHVJ5NP8E"
EXPECTED_ORDER = "order_TThUuhmUinebAX"
EXPECTED_PAYMENT = "pay_TThVaPlcLqu4XE"
EXPECTED_AMOUNT = 239800


def main() -> int:
    from razormesh_api.ledger import EvidenceLedger
    from razormesh_api.persistence.db import create_db_engine, create_session_factory
    from razormesh_api.persistence.models import ExecutionAttempt
    from razormesh_api.persistence.repositories import Repositories
    from razormesh_api.settings import Settings
    from razormesh_api.spend import SpendManager

    settings = Settings()
    repos = Repositories(
        create_session_factory(create_db_engine(settings.database_url))
    )

    with repos.transaction() as session:
        attempt = session.get(ExecutionAttempt, ATTEMPT_ID, with_for_update=True)
        if attempt is None:
            print(f"no attempt {ATTEMPT_ID} — nothing to repair (wiped?)")
            return 1
        guards = {
            "state == SUCCEEDED": attempt.state == "SUCCEEDED",
            "order id matches": attempt.razorpay_order_id == EXPECTED_ORDER,
            "payment id matches": attempt.razorpay_payment_id == EXPECTED_PAYMENT,
            "amount matches": attempt.amount_minor == EXPECTED_AMOUNT,
        }
        if not all(guards.values()):
            print("GUARDS FAILED — refusing to repair:", guards)
            return 2
        intent_id = attempt.intent_id
        checkout_id = attempt.checkout_id
        ticket_id = attempt.ticket_id
        already_committed = attempt.provider_name == "razorpay"

    spend = SpendManager(repos)
    from razormesh_api.domain.ids import IntentId

    row_before = None
    with repos.transaction() as session:
        from razormesh_api.persistence.models import AuthorizationSpend

        row_before = session.get(AuthorizationSpend, str(intent_id))
        if row_before is None:
            print("no spend row — nothing to repair")
            return 1
        print(
            f"before: reserved={row_before.reserved_minor} "
            f"committed={row_before.committed_minor} version={row_before.version}"
        )
        if row_before.reserved_minor < EXPECTED_AMOUNT:
            if row_before.committed_minor >= EXPECTED_AMOUNT:
                print("already repaired (committed already reflects the amount)")
                return 0
            print("unexpected spend state — refusing")
            return 3

    if row_before.reserved_minor >= EXPECTED_AMOUNT:
        spend.commit(IntentId(intent_id), EXPECTED_AMOUNT)

    with repos.transaction() as session:
        attempt = session.get(ExecutionAttempt, ATTEMPT_ID, with_for_update=True)
        if attempt is not None and attempt.provider_name != "razorpay":
            attempt.provider_name = "razorpay"

    EvidenceLedger(repos).append(
        event_type="M38_SPEND_COMMIT_REPAIR",
        actor="ops-one-time-repair",
        intent_id=str(intent_id),
        checkout_id=str(checkout_id),
        ticket_id=str(ticket_id),
        payload={
            "execution_attempt_id": ATTEMPT_ID,
            "razorpay_order_id": EXPECTED_ORDER,
            "razorpay_payment_id": EXPECTED_PAYMENT,
            "amount_minor": EXPECTED_AMOUNT,
            "reason": (
                "webhook reducer executor was constructed without a SpendManager; "
                "captured-event settlement skipped reserved->committed. "
                "Code fixed in the same milestone; this repairs the one affected row."
            ),
            "provider_name_corrected_to": "razorpay"
            if not already_committed
            else "unchanged",
        },
    )

    with repos.transaction() as session:
        from razormesh_api.persistence.models import AuthorizationSpend

        row_after = session.get(AuthorizationSpend, str(intent_id))
        assert row_after is not None
        print(
            f"after:  reserved={row_after.reserved_minor} "
            f"committed={row_after.committed_minor} version={row_after.version}"
        )
    print("repair complete; audit event M38_SPEND_COMMIT_REPAIR appended")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
