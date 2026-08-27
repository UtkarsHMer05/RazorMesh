"""Untrusted buyer-agent harness tests (M45 / Section 9 of
pre-human acceptance gate).

Scenarios (per gate §9):
- benign purchase scenario
- hostile merchant-content scenario
- prompt-injection-like scenario
- changed-price scenario
- subscription insertion scenario

The untrusted agent must remain on the safe tool surface and must
not reach the payment provider or signing secrets.
"""

from __future__ import annotations

import inspect

from razormesh_api.protocol.untrusted_agent import (
    UntrustedAgentEvent,
    run_adversarial_scenario,
    run_changed_price_scenario,
    run_normal_scenario,
    run_prompt_injection_scenario,
    run_subscription_insertion_scenario,
)


def test_normal_scenario_no_ticket_blocks():
    run = run_normal_scenario()
    assert run.final_decision == "BLOCK"
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


def test_changed_price_scenario_blocked():
    run = run_changed_price_scenario()
    assert run.final_decision == "BLOCK"
    blocked = next(s for s in run.steps if s.event == UntrustedAgentEvent.BLOCKED_BY_FIREWALL)
    assert blocked.payload.get("commitment_mismatch") is True


def test_subscription_insertion_scenario_blocked():
    run = run_subscription_insertion_scenario()
    assert run.final_decision == "BLOCK"
    blocked = next(s for s in run.steps if s.event == UntrustedAgentEvent.BLOCKED_BY_FIREWALL)
    assert blocked.payload.get("razorguard_challenge") == "human_says_no_subscription"


def test_agent_run_serializable():
    import json
    run = run_normal_scenario()
    blob = json.dumps(run.to_dict(), default=str)
    assert "agent_id" in blob
    assert "final_decision" in blob


def test_agent_has_no_provider_secrets():
    from razormesh_api.protocol import untrusted_agent
    src = inspect.getsource(untrusted_agent)
    assert "razorpay_key" not in src
    assert "RZP_KEY" not in src
    assert "api_key" not in src.lower()
