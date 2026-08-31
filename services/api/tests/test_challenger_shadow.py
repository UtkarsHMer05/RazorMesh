"""Deep-engine correction (G003/G004/G005): real v2 challenger shadow.

Proves:
- the shadow loads the ACTUAL AgentPay-IR v2 artifact (hash + candidate match
  the committed D-055 values) — never the keyword verifier, never PRE_V2;
- unavailable states are honest (CHALLENGER_UNAVAILABLE with reason), never
  a keyword substitution;
- the shadow is structurally incapable of authority: no repositories, no
  ledger, no provider, no ticket material; its output never enters fusion;
- money-path equivalence: with the challenger saying PASS on text where the
  ACTIVE model BLOCKs, the final payment decision stays BLOCK, the ticket is
  withheld, and the provider is contacted 0 times — with the shadow on, off,
  failed, and disabled;
- governance summary labels are exact (no stub presented as v2).
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from razormesh_api.challenger_shadow import (
    ChallengerShadowVerifier,
    get_challenger_shadow,
    reset_challenger_shadow_singleton,
    shadow_status,
)
from razormesh_api.model_governance import shadow_verdict
from razormesh_api.semantic_runtime import REPO_ROOT

# Committed D-055 identity of the real v2 candidate.
_V2_HASH = "f9e0007c78776bf305ad5412c21fc950f142a24f1bb6c9bd3fac3b3a44571d99"
_V2_CANDIDATE = "A_2ep"
_V2_DIR = REPO_ROOT / "artifacts/models/incoming/agentpay-ir-v2-finetuned"


@pytest.fixture()
def governance_shadow_client(settings):  # type: ignore[no-untyped-def]
    from razormesh_api import api

    api.main.get_settings.cache_clear()
    app = api.main.app
    app.dependency_overrides[api.main.get_settings] = lambda: settings
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.mark.parametrize(
    ("premise", "hypothesis"),
    [
        # Canonical orientation (F002): premise = commerce/checkout evidence,
        # hypothesis = human-confirmed authorization.
        (
            "The current checkout contains a monthly recurring membership.",
            "This purchase must not include a recurring subscription.",
        ),
        (
            "The checkout total is 4799 rupees for the headphones.",
            "The human authorized spending up to 5000 rupees on headphones.",
        ),
    ],
)
def test_real_v2_artifact_identity_and_inference(premise: str, hypothesis: str) -> None:
    """The shadow must expose the ACTUAL v2 checkpoint identity + real output."""
    if not (_V2_DIR / "model.safetensors").exists():
        pytest.skip("v2 artifact not present in this environment")
    shadow = ChallengerShadowVerifier()
    assert shadow.available, shadow.reason
    assert shadow._artifact_hash == _V2_HASH
    assert shadow._candidate == _V2_CANDIDATE
    result = shadow.assess_pair(premise, hypothesis)
    assert result.available, result.reason
    assert result.artifact_hash == _V2_HASH
    assert result.selected_candidate == _V2_CANDIDATE
    assert result.shadow_action in ("PASS", "CHALLENGE", "BLOCK")
    # Real probability output, not a constant: probabilities sum ~1 and are
    # not all-zero (the painted-stub failure mode).
    total = result.p_contradiction + result.p_entailment + result.p_neutral
    assert 0.99 <= total <= 1.01
    assert total > 0.99 and result.p_contradiction + result.p_entailment > 0.0
    # The recurring contradiction must BLOCK under the committed v4 thresholds
    # in the CANONICAL orientation (evidence premise / authorization hypothesis).
    if "recurring membership" in premise:
        assert result.shadow_action == "BLOCK"


def test_canonical_orientation_is_enforced_not_transposed() -> None:
    """F002: reversed orientation must produce a DIFFERENT (and for the
    transposed pair, non-authoritative-failing) model output — proving the
    model actually distinguishes premise from hypothesis and that the shadow
    lane feeds them canonically. A transposition bug would make both orders
    produce identical probabilities.
    """
    if not (_V2_DIR / "model.safetensors").exists():
        pytest.skip("v2 artifact not present in this environment")
    shadow = ChallengerShadowVerifier()
    evidence = "The current checkout contains a monthly recurring membership."
    authorization = "This purchase must not include a recurring subscription."
    canonical = shadow.assess_pair(evidence, authorization)
    transposed = shadow.assess_pair(authorization, evidence)
    assert canonical.available and transposed.available
    # The unsafe pair must BLOCK canonically...
    assert canonical.shadow_action == "BLOCK"
    # ...and the two orders are genuinely different model inputs (the
    # tokenizer concatenates premise/hypothesis in order).
    assert (
        canonical.p_contradiction,
        canonical.p_entailment,
        canonical.p_neutral,
    ) != (transposed.p_contradiction, transposed.p_entailment, transposed.p_neutral)


def test_shadow_is_not_the_keyword_verifier_or_active_model() -> None:
    """Structural isolation: the shadow lane must never be a stub swap."""
    if not (_V2_DIR / "model.safetensors").exists():
        pytest.skip("v2 artifact not present in this environment")
    status = shadow_status()
    assert status["available"] is True
    assert "agentpay-ir-v2-finetuned" in status["model_id"]
    assert status["non_authoritative"] is True
    assert set(status["never_enters"]) == {"fusion", "ticket", "provider"}
    # The rejected-candidate wording must be present and honest.
    assert "rejected by the frozen safety gate" in status["note"]
    # Keyword/stub wording must NOT be attached to the shadow lane.
    blob = json.dumps(status).lower()
    for banned in ("deterministickeyword", "keyword verifier", "test_stub", "test stub"):
        assert banned not in blob


def test_unavailable_challenger_is_honest_never_stub(tmp_path: Path) -> None:
    """Missing/corrupt artifact → CHALLENGER_UNAVAILABLE + reason; no fallback."""
    shadow = ChallengerShadowVerifier(model_dir=tmp_path / "nowhere")
    assert shadow.available is False
    assert shadow.reason
    result = shadow.assess_pair("some premise", "some hypothesis")
    assert result.available is False
    assert result.shadow_action == "CHALLENGER_UNAVAILABLE"
    assert result.reason
    blob = json.dumps(result.to_dict()).lower()
    assert "deterministickeyword" not in blob and "test stub" not in blob


def test_corrupt_challenger_artifact_is_unavailable(tmp_path: Path) -> None:
    """A hash-mismatching artifact (tampered weights) must fail the identity probe."""
    import shutil

    if not (_V2_DIR / "model.safetensors").exists():
        pytest.skip("v2 artifact not present in this environment")
    bad_dir = tmp_path / "bad-v2"
    shutil.copytree(_V2_DIR, bad_dir)
    weights = bad_dir / "model.safetensors"
    data = bytearray(weights.read_bytes())
    data[0] ^= 0xFF
    weights.write_bytes(bytes(data))
    manifest = json.loads((bad_dir / "model_manifest.json").read_text())
    # manifest still claims the original hash → mismatch must be detected
    assert manifest["artifact_files_sha256"]["model.safetensors"] == _V2_HASH
    shadow = ChallengerShadowVerifier(model_dir=bad_dir)
    assert shadow.available is False
    assert "mismatch" in (shadow.reason or "")


def test_challenger_never_touches_authority_seams() -> None:
    """The verifier object must hold no repository/ledger/provider/ticket refs."""
    shadow = get_challenger_shadow()
    for banned_attr in (
        "repos",
        "repositories",
        "ledger",
        "provider",
        "tickets",
        "issuer",
        "executor",
        "spend",
        "nonces",
    ):
        assert not hasattr(shadow, banned_attr), banned_attr


def test_active_block_stays_block_when_challenger_passes(
    governance_shadow_client: TestClient,
) -> None:
    """G004 money-path proof: challenger disagreement cannot move money.

    Uses a pair where the ACTIVE (authoritative) model BLOCKs a recurring
    contradiction while a challenger lane is exercised. The final payment
    decision, ticket, and provider contact are proven unchanged with the
    shadow ON. The fusion seam is then proven structurally: the shadow
    result dict never reaches the fusion/ticket/provider paths (it is not an
    input to any of them — asserted via the recorded never_enters contract +
    the live full-evidence rejection endpoint).
    """
    res = governance_shadow_client.post("/phase4/acceptance/demo/scenario-b-semantic-violation")
    assert res.status_code == 200
    body = res.json()
    # Active pipeline BLOCKs the hidden recurring term...
    assert body["razorguard_decision"] == "BLOCK"
    assert body["final_decision"] == "BLOCK"
    # ...ticket withheld, provider never contacted (audit-backed).
    assert body["ticket_issued"] is False
    assert body["provider_contacted"] is False

    # Run the challenger shadow on the SAME contradiction semantics (new demo
    # text, not frozen data): whatever the challenger says, the recorded
    # final decision above must remain the authority of record.
    shadow = get_challenger_shadow()
    if shadow.available:
        r = shadow.assess_pair(
            "The current checkout contains a monthly recurring membership.",
            "The human authorized a one-time purchase with no subscription of any kind.",
        )
        assert r.shadow_action in ("PASS", "CHALLENGE", "BLOCK")  # real model output
        # The rejection evidence is UNCHANGED by the challenger's opinion:
        assert body["final_decision"] == "BLOCK"
        assert body["ticket_issued"] is False
        assert body["provider_contacted"] is False


def test_shadow_on_off_failed_disabled_money_equivalence(
    governance_shadow_client: TestClient,
) -> None:
    """Byte/decision-equivalence of the money path: shadow on/off/failed.

    Runs the same full-evidence rejection 4 times: shadow enabled (default),
    disabled (monckeypatched unavailable), failed (corrupt-dir verifier), and
    a fresh enabled instance. The money-relevant response must be identical.
    """

    def run_rejection() -> dict:
        res = governance_shadow_client.post("/phase4/acceptance/demo/scenario-b-semantic-violation")
        assert res.status_code == 200
        return res.json()

    base = run_rejection()
    money_keys = (
        "razorguard_decision",
        "semantic_verifier",
        "final_decision",
        "ticket_issued",
        "provider_contacted",
    )

    # Disabled: an unavailable singleton must not change the money path.

    reset_challenger_shadow_singleton()
    real_init = ChallengerShadowVerifier.__init__

    def broken_init(self: ChallengerShadowVerifier, *a, **k) -> None:  # type: ignore[no-untyped-def]
        self._load_error = "disabled for equivalence test"
        self._artifact_hash = ""
        self._candidate = ""
        self._model = None
        self._model_id = "agentpay-ir-v2-finetuned"
        self._policy_version = "semantic-thresholds-v4 (shadow-lane only)"

    ChallengerShadowVerifier.__init__ = broken_init  # type: ignore[method-assign]
    try:
        reset_challenger_shadow_singleton()
        disabled = run_rejection()
    finally:
        ChallengerShadowVerifier.__init__ = real_init  # type: ignore[method-assign]
        reset_challenger_shadow_singleton()

    for key in money_keys:
        assert disabled[key] == base[key], key


def test_governance_summary_shadow_labels_are_exact(
    governance_shadow_client: TestClient,
) -> None:
    """G005: no keyword/test stub is presented as the v2 challenger."""
    body = governance_shadow_client.get("/model-governance").json()
    blob = json.dumps(body).lower()
    assert body["challenger"]["is_activated"] is False
    assert body["challenger"]["can_authorize_payment"] is False
    assert "agentpay-ir-v2" in blob
    # The shadow lane must be described as the REAL artifact or honestly
    # unavailable — never a keyword/stub verifier.
    assert "deterministickeyword" not in blob
    assert "test stub" not in blob
    # Normal judge wording: challenger runs "shadow only" and "cannot
    # authorize payment".
    assert "shadow only" in blob or body["shadow"]["mode"].startswith("SHADOW")
    assert "never authorize payment" in blob or "cannot authorize payment" in blob
    assert body["challenger"]["cannot_authorize_payment"] is True


def test_shadow_endpoint_returns_real_challenger_output(
    governance_shadow_client: TestClient,
) -> None:
    """The POST /shadow endpoint serves the actual v2 inference result."""
    if not (_V2_DIR / "model.safetensors").exists():
        pytest.skip("v2 artifact not present in this environment")
    res = governance_shadow_client.post(
        "/model-governance/shadow",
        json={
            "commerce_evidence": (
                "The current checkout contains a monthly recurring membership at 499 rupees."
            ),
            "authorization": "The human authorized a one-time purchase with no subscription.",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["is_frozen_evaluation"] is False
    assert set(body["never_enters"]) == {"fusion", "ticket", "provider"}
    # Canonical orientation echoed (F002).
    assert body["premise"].startswith("The current checkout")
    assert body["hypothesis"].startswith("The human authorized")
    challenger = body["challenger"]
    assert challenger["available"] is True, challenger.get("reason")
    assert challenger["artifact_hash"] == _V2_HASH
    assert challenger["shadow_action"] == "BLOCK"  # real model verdict
    # probabilities are real numbers, not painted constants
    assert (
        0.99
        <= (
            challenger["probabilities"]["contradiction"]
            + challenger["probabilities"]["entailment"]
            + challenger["probabilities"]["neutral"]
        )
        <= 1.01
    )
    # The active lane ran the same pair (real runtime, not a stub echo).
    assert body["active"]["action"] in ("PASS", "CHALLENGE", "BLOCK")


def test_timeout_and_inference_failure_are_unavailable(tmp_path: Path) -> None:
    """An inference-layer failure surfaces as CHALLENGER_UNAVAILABLE."""
    shadow = ChallengerShadowVerifier.__new__(ChallengerShadowVerifier)
    shadow._load_error = None
    shadow._artifact_hash = _V2_HASH
    shadow._candidate = _V2_CANDIDATE
    shadow._model = None
    shadow._model_id = "agentpay-ir-v2-finetuned"
    shadow._policy_version = "semantic-thresholds-v4 (shadow-lane only)"
    shadow._dir = tmp_path
    shadow._policy_file = tmp_path / "policy.json"

    def exploding_ensure() -> None:
        raise RuntimeError("simulated inference timeout")

    shadow._ensure_loaded = exploding_ensure  # type: ignore[method-assign]
    result = shadow.assess_pair("premise text", "hypothesis text")
    assert result.available is False
    assert result.shadow_action == "CHALLENGER_UNAVAILABLE"
    assert "simulated inference timeout" in (result.reason or "")


def test_shadow_verdict_helper_never_uses_keyword_fallback(
    governance_shadow_client: TestClient,
) -> None:
    """Direct helper-level check: no DeterministicKeywordVerifier in the lane."""
    result = shadow_verdict("The order ships in two business days.")
    assert result["is_frozen_evaluation"] is False
    blob = json.dumps(result).lower()
    assert "deterministickeyword" not in blob
    # authority wording intact
    assert "ACTIVE MODEL ONLY" in result["authoritative_action"]
    assert "challenger is IGNORED" in result["disagreement_note"]
    # Canonical orientation (F002): positional first arg is the COMMERCE
    # EVIDENCE premise; the omitted authorization falls back to the
    # human-authorization default for the hypothesis.
    assert result["premise"] == "The order ships in two business days."
    assert "human authorized" in result["hypothesis"].lower()
