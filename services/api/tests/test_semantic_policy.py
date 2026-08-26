"""P3-M38/M40: semantic policy application + conservative fusion.

The fusion property test is RELEASE-BLOCKING: no semantic verdict may ever
loosen a deterministic RazorGuard decision.
"""

import json

import hypothesis
from hypothesis import strategies as st

from razormesh_api.semantic_verifier import (
    DeterministicDecision,
    SemanticAction,
    SemanticVerdict,
    apply_threshold_policy,
    fuse,
)


def test_threshold_policy_rule_matrix() -> None:
    f = apply_threshold_policy

    def case(p_e: float, p_n: float, p_c: float) -> SemanticAction:
        return f(p_e, p_n, p_c, tau_block=0.36, tau_entail=0.40)

    # contradiction at/above tau blocks regardless of entailment mass
    assert case(0.05, 0.00, 0.95) is SemanticAction.BLOCK
    assert case(0.60, 0.04, 0.36) is SemanticAction.BLOCK
    # entailment pass requires p_e >= tau and p_c < tau
    assert case(0.65, 0.30, 0.05) is SemanticAction.PASS
    # neither bar met -> CHALLENGE
    assert case(0.30, 0.35, 0.35) is SemanticAction.CHALLENGE


def _verdict(action: SemanticAction) -> SemanticVerdict:
    return SemanticVerdict(
        action=action,
        p_entailment=0.0,
        p_neutral=0.0,
        p_contradiction=0.0,
        model_id="test",
        policy_version="test",
    )


def test_fusion_matrix_exhaustive() -> None:
    det = list(DeterministicDecision)
    sem = list(SemanticAction)
    expected = {
        ("BLOCK", "PASS"): "BLOCK",
        ("BLOCK", "CHALLENGE"): "BLOCK",
        ("BLOCK", "BLOCK"): "BLOCK",
        ("CHALLENGE", "PASS"): "CHALLENGE",
        ("CHALLENGE", "CHALLENGE"): "CHALLENGE",
        ("CHALLENGE", "BLOCK"): "BLOCK",
        ("ALLOW", "PASS"): "ALLOW",
        ("ALLOW", "CHALLENGE"): "CHALLENGE",
        ("ALLOW", "BLOCK"): "BLOCK",
    }
    for d in det:
        for s in sem:
            out = fuse(d, _verdict(s))
            assert out.value == expected[(d.value, s.value)], (d, s, out)
            # THE invariant: never looser than the deterministic decision
            order = ["ALLOW", "CHALLENGE", "BLOCK"]
            assert order.index(out.value) >= order.index(d.value)


@hypothesis.given(
    det=st.sampled_from(list(DeterministicDecision)),
    p_e=st.floats(min_value=0, max_value=1),
    p_n=st.floats(min_value=0, max_value=1),
    p_c=st.floats(min_value=0, max_value=1),
    tb=st.floats(min_value=0.1, max_value=0.9),
    te=st.floats(min_value=0.1, max_value=0.9),
)
def test_property_semantics_never_loosen(det, p_e, p_n, p_c, tb, te) -> None:
    try:
        action = apply_threshold_policy(
            p_entailment=p_e,
            p_neutral=p_n,
            p_contradiction=p_c,
            tau_block=tb,
            tau_entail=te,
        )
    except Exception:  # noqa: BLE001 - invalid float combos skipped
        return
    v = SemanticVerdict(
        action=action,
        p_entailment=p_e,
        p_neutral=p_n,
        p_contradiction=p_c,
        model_id="t",
        policy_version="t",
    )
    order = ["ALLOW", "CHALLENGE", "BLOCK"]
    out = fuse(det, v)
    assert order.index(out.value) >= order.index(det.value)


def test_verifier_fail_closed_when_model_missing(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from razormesh_api.semantic_verifier import DebertaNLISemanticVerifier

    policy = {
        "model": "cross-encoder/nli-deberta-v3-base",
        "policy_version": "semantic-thresholds-v1",
        "selected": {"tau_block": 0.36, "tau_entail": 0.40},
        "gold_validation_status": "PENDING_GOLD_VALIDATION",
    }
    p = tmp_path / "policy.json"
    p.write_text(json.dumps(policy))
    v = DebertaNLISemanticVerifier(model_dir=tmp_path / "does-not-exist", policy_path=p)
    verdict = v.verify(premise="p text here", hypothesis="h text here")
    assert verdict.action is SemanticAction.CHALLENGE
    assert verdict.fail_closed is True
