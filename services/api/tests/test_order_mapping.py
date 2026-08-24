"""P2-M14: internal->Razorpay order correlation contract tests."""

import pytest

from razormesh_api.providers.razorpay import (
    _NOTE_VALUE_MAX,
    build_order_correlation,
    parse_order_correlation,
)


def _ids() -> dict[str, str]:
    return {
        "execution_attempt_id": "exa_01M0T4WJ8ZQ3V5N7K9C2XBYDPE",
        "intent_id": "int_01M0T4WJ8ZQ3V5N7K9C2XBYDPF",
        "checkout_id": "chk_01M0T4WJ8ZQ3V5N7K9C2XBYDPG",
        "decision_id": "dec_01M0T4WJ8ZQ3V5N7K9C2XBYDPH",
        "ticket_id": "tk_01M0T4WJ8ZQ3V5N7K9C2XBYDPJ",
    }


def test_receipt_within_official_limit_and_traceable() -> None:
    receipt, _notes = build_order_correlation(**_ids(), authorization_generation=1)
    # official Orders limit: receipt <= 40 chars (R-013)
    assert len(receipt) <= 40
    assert receipt == f"r_{_ids()['execution_attempt_id']}"
    assert receipt.startswith("r_exa_")


def test_notes_within_official_limits_and_no_pii_or_secrets() -> None:
    _, notes = build_order_correlation(**_ids(), authorization_generation=7)
    assert len(notes) <= 15  # official limit: max 15 pairs
    for key, value in notes.items():
        assert len(key) <= _NOTE_VALUE_MAX
        assert len(value) <= _NOTE_VALUE_MAX
    joined = str(notes).lower()
    for forbidden in ("secret", "key_secret", "webhook", "signature", "email", "phone"):
        assert forbidden not in joined


def test_traceability_round_trip_preserves_all_references() -> None:
    ids = _ids()
    receipt, notes = build_order_correlation(**ids, authorization_generation=3)
    parsed = parse_order_correlation(notes)
    assert parsed["intent_id"] == ids["intent_id"]
    assert parsed["checkout_id"] == ids["checkout_id"]
    assert parsed["decision_id"] == ids["decision_id"]
    assert parsed["ticket_id"] == ids["ticket_id"]
    assert notes["authorization_generation"] == "3"
    assert receipt  # and receipt alone identifies the execution attempt


def test_oversized_attempt_id_rejected() -> None:
    ids = _ids()
    ids["execution_attempt_id"] = "x" * 45
    with pytest.raises(ValueError):
        build_order_correlation(**ids, authorization_generation=1)
