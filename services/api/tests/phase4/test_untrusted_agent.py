"""Untrusted buyer-agent harness tests (M45)."""

from __future__ import annotations

from razormesh_api.protocol.untrusted_agent import (
    UntrustedAgentEvent,
    run_adversarial_scenario,
    run_normal_scenario,
    run_prompt_injection_scenario,
)


def test_normal_scenario_no_ticket_blocks():
    run = run_normal_scenario()
    assert run.final_decision == "BLOCK"
    # The complete_authorized_checkout step is recorded as blocked.
    last = next(s for s in run.steps if s.event == UntrustedAgentEvent.COMPLETE_AUTHORIZED_CHECKOUT)
    assert last.blocked is True
    assert last.reason == "missing_ticket_or_signature"


def test_adversarial_downgrade_blocked():
    run = run_adversarial_scenario()
    assert run.final_decision == "BLOCK"
    blocked = next(s for s in run.steps if s.event == UntrustedAgentEvent.BLOCKED_BY_FIREWALL)
    assert blocked.blocked is True
    assert "downgrade" in (blocked.reason or "")


def test_prompt_injection_scenario_records_block():
    run = run_prompt_injection_scenario()
    assert run.final_decision == "BLOCK"
    blocked = next(s for s in run.steps if s.event == UntrustedAgentEvent.BLOCKED_BY_FIREWALL)
    assert blocked.payload.get("merchant_injection_attempted") is True


def test_agent_run_serializable():
    import json
    run = run_normal_scenario()
    blob = json.dumps(run.to_dict(), default=str)
    assert "agent_id" in blob
    assert "final_decision" in blob


def test_agent_has_no_provider_secrets():
    # P4-S27: untrusted buyer agent has no provider/signing secrets.
    import inspect

    from razormesh_api.protocol import untrusted_agent

    src = inspect.getsource(untrusted_agent)
    # No provider keys, no signing keys, no DB credentials.
    assert "key_id=" not in src  # only fixtures have key ids
    assert "razorpay_key" not in src
    assert "RZP_KEY" not in src
    assert "api_key" not in src.lower()
    # The stub signature uses "k" — a literal stub key, not a real
    # signing private key. The source contains the literal string
    # '"k"' once; we accept that as a stub.
