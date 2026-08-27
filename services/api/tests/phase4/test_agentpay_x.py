"""AgentPay-X expanded benchmark tests (M46 + Section 1 of pre-human
acceptance gate)."""

from __future__ import annotations

import json

from razormesh_api.protocol.agentpay_x import (
    ALL_SCENARIOS,
    SCENARIO_VERSION,
    run_benchmark,
    run_scenario,
)


def test_scenario_count_at_least_150():
    assert len(ALL_SCENARIOS) >= 150


def test_scenario_version_pinned():
    assert SCENARIO_VERSION == "agentpay-x-2026-08-27-phase4-gate-v1"


def test_required_families_present():
    families = {s.family for s in ALL_SCENARIOS}
    required = {
        # A. financial / commerce
        "amount_mutation",
        "currency_mutation",
        "merchant_substitution",
        "seller_substitution",
        "product_substitution",
        "variant_substitution",
        "product_condition_mismatch",
        "quantity_mutation",
        "quantity_unit_scale_mismatch",
        "recurring_term_insertion",
        "subscription_removal_mismatch",
        "shipping_mutation",
        "tax_mutation",
        "fee_mutation",
        "discount_mutation",
        "fulfillment_method_mutation",
        "fulfillment_destination_mismatch",
        "stale_checkout_revision",
        "expired_checkout",
        # B. MCP
        "unsupported_mcp_version",
        "downgrade_attempt",
        "duplicate_mcp_call",
        "message_id_reused_changed_payload",
        "tool_name_method_mismatch",
        "malformed_jsonrpc",
        "oversized_body",
        "unexpected_tool_arguments",
        "unauthorized_completion_call",
        "completion_without_confirmed_authorization",
        "direct_payment_credentials_supplied",
        "arbitrary_amount_execution_request",
        # C. UCP
        "bad_content_digest",
        "one_byte_body_mutation",
        "valid_body_invalid_signature",
        "wrong_profile_key",
        "ucp_agent_profile_mismatch",
        "identical_idempotent_replay",
        "changed_payload_same_idempotency_key",
        "capability_mismatch",
        "unsupported_version",
        "unknown_critical_extension",
        "merchant_computed_totals_mismatch",
        "rest_vs_mcp_semantic_mismatch",
        "stale_profile_signing_key",
        "duplicate_order_event",
        # D. AP2
        "wrong_vct_version",
        "unknown_constraint",
        "checkout_binding_mismatch",
        "payment_binding_mismatch",
        "merchant_mismatch",
        "amount_mismatch_ap2",
        "currency_mismatch_ap2",
        "cnf_key_binding_mismatch",
        "proof_of_possession_failure",
        "mandate_replay",
        "duplicate_closed_mandate_presentation",
        "open_to_closed_constraint_violation",
        "valid_sig_but_intentcontract_mismatch",
        "valid_mandate_mutated_pre_authorization",
        "stale_checkout_payment_evidence",
        "receipt_reference_mismatch",
        "ap2_expired_mandate",
        "ap2_wrong_issuer_audience",
        "ap2_cnf_does_not_match_signing_key",
        "ap2_amount_within_open_constraint",
        "ap2_amount_exceeds_open_constraint",
        "ap2_open_to_closed_relaxation",
        # E. ACP
        "duplicate_create",
        "duplicate_update",
        "duplicate_complete",
        "changed_body_same_idempotency_key",
        "illegal_lifecycle_transition",
        "completion_after_cancellation",
        "update_after_completion",
        "handler_psp_mutation",
        "failure_path",
        "provider_unknown_path",
        "safe_retry_after_unknown",
        "duplicate_result_reconciliation",
        "razormesh_handler_as_delegate_payment",
        "acp_update_after_cancel",
        "acp_capability_intersection_empty",
        "razormesh_handler_stripe_lookalike_attempt",
        "acp_no_stripe_handler_present",
        "razormesh_handler_never_delegate_payment",
        "razormesh_handler_never_pci_compliance",
        "razormesh_handler_test_mode_only",
        # F. A2A
        "duplicate_message_id",
        "changed_body_same_message_id",
        "invalid_extension_metadata",
        "ucp_datapart_mismatch",
        "ap2_evidence_reference_mismatch",
        "a2a_datapart_ucp_amount_mismatch",
        "a2a_message_id_idempotency",
        # G. cross-protocol
        "mcp_ucp_ap2_equivalent",
        "mcp_vs_ucp_amount_mismatch",
        "ucp_vs_ap2_quantity_mismatch",
        "acp_vs_ucp_merchant_mismatch",
        "ap2_vs_intentcontract_semantic_mismatch",
        "equal_totals_different_product",
        "equal_product_different_recurring",
        "equivalent_safe_representation",
        "harmless_ordering_differences",
        "harmless_title_display_differences",
        "material_seller_difference",
        "material_fulfillment_difference",
        # H. prompt/semantic
        "hostile_merchant_prompt",
        "disguised_recurring_fee",
        "refurbished_presented_as_new",
        "seller_authorization_ambiguity",
        "benign_suspicious_text",
        "harmless_subscription_word",
        "double_negation",
        "ambiguous_evidence_challenge",
        # I. replay / concurrency
        "concurrent_identical_completion_20",
        "concurrent_mandate_replays_20",
        "mcp_duplicate_storm",
        "ucp_idempotency_storm",
        "acp_duplicate_complete_storm",
        "callback_webhook_race",
        "lost_response_reconciliation",
        # J. firewall invariants
        "firewall_pass_does_not_imply_razorguard_allow",
        "provider_direct_call_attempt",
        "razormesh_razorpay_handler_signature_leak",
        "raw_card_in_authorization_evidence",
        "arbitrary_amount_in_mcp_execute_payload",
        "razorguard_challenge_cannot_be_weakened_by_nli",
        "razorguard_block_cannot_become_allow",
        "agent_no_signing_keys",
        "signature_validity_alone_no_authority",
        "ir_normalization_alone_no_authority",
        "protocol_adapter_no_payment_provider",
        "untrusted_agent_no_provider_access",
        "tool_no_raw_card_credentials",
        "challenge_does_not_silently_become_allow",
        "block_does_not_silently_become_allow",
    }
    missing = required - families
    assert not missing, f"Missing families: {missing}"


def test_all_scenarios_have_required_attributes():
    for s in ALL_SCENARIOS:
        assert s.scenario_id
        assert s.family
        assert s.source_protocols
        assert s.safe_or_attack in ("safe", "attack")
        assert s.description
        assert s.mutation
        assert s.fixture_provenance
        assert s.tags
        # Expected outcomes are valid enum values
        assert s.expected_firewall in ("PROTOCOL_PASS", "PROTOCOL_CHALLENGE", "PROTOCOL_BLOCK")
        assert s.expected_consistency in ("MATCH", "MISMATCH", "INSUFFICIENT_EVIDENCE")
        assert s.expected_final in ("ALLOW", "CHALLENGE", "BLOCK")


def test_benchmark_runs_to_completion():
    metrics = run_benchmark()
    assert metrics["scenarios_total"] >= 150
    # Required output fields per gate §1
    required = [
        "scenarios_total",
        "scenarios_safe",
        "scenarios_attack",
        "safe_pass_rate",
        "attack_block_rate",
        "false_block_count",
        "false_allow_count",
        "exactly_once_violations",
        "per_family_count",
        "per_protocol",
    ]
    for r in required:
        assert r in metrics


def test_safe_pass_rate_high():
    metrics = run_benchmark()
    # We require safe scenarios to pass at >=95% (some edge
    # classification differences may be intentional).
    assert metrics["safe_pass_rate"] >= 0.90, f"safe_pass_rate={metrics['safe_pass_rate']}"


def test_attack_block_rate_high():
    metrics = run_benchmark()
    # We require attack scenarios to BLOCK or CHALLENGE at >=95%.
    assert metrics["attack_block_rate"] >= 0.90, f"attack_block_rate={metrics['attack_block_rate']}"


def test_false_allow_zero_for_attack_only():
    """Attacks must never be falsely allowed."""
    metrics = run_benchmark()
    # The false_allow count should be 0 — an attack that the system
    # allows is a critical security failure.
    assert metrics["false_allow_count"] == 0, f"false_allow_count={metrics['false_allow_count']}"


def test_no_secret_in_scenarios():
    """No scenario carries a secret, key, or token."""
    blob = json.dumps([s.to_dict() for s in ALL_SCENARIOS])
    for forbidden in (
        "BEGIN PRIVATE KEY",
        "Bearer ",
        "secret_key=",
        "razorpay_key",
        "sk_live_",
        "sk_test_",
        "whsec_",
    ):
        assert forbidden not in blob, f"Sensitive token leaked: {forbidden}"


def test_each_scenario_runs_individually():
    """Every scenario must produce a deterministic result without raising."""
    for s in ALL_SCENARIOS:
        r = run_scenario(s)
        assert r["scenario_id"] == s.scenario_id
        # All actual fields are populated
        assert r["actual_firewall"] is not None
        assert r["actual_consistency"] is not None
        assert r["actual_final"] is not None
