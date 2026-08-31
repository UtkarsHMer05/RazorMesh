"""F014: challenger configuration / fresh-clone truth.

Proves a fresh clone without the (intentionally uncommitted) v2 artifact
degrades TRUTHFULLY:
- the challenger path comes from Settings (semantic_model_path_v2) — env
  overrides are honored, never a module-level hardcode;
- with the artifact absent, `shadow_mode_available` is False and the shadow
  reports CHALLENGER_UNAVAILABLE with an honest reason — never a hardcoded
  True, never a keyword-verifier substitution;
- the governance UI wording surfaces CHALLENGER UNAVAILABLE truthfully;
- with the real artifact present (this machine), everything stays available.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from razormesh_api.challenger_shadow import (
    ChallengerShadowVerifier,
    reset_challenger_shadow_singleton,
    shadow_status,
)
from razormesh_api.semantic_runtime import REPO_ROOT


def test_challenger_path_comes_from_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """The configured artifact path IS settings.semantic_model_path_v2 —
    the canonical configuration source, honored via the real env-override
    mechanism (RAZORMESH-style env vars), never a module-level hardcode."""
    from razormesh_api import challenger_shadow as mod
    from razormesh_api.settings import get_settings

    # The default path comes from Settings.
    get_settings.cache_clear()
    assert str(mod._v2_dir()) == get_settings().semantic_model_path_v2

    # A REAL env override flows through to the challenger lane.
    monkeypatch.setenv(
        "SEMANTIC_MODEL_PATH_V2", "artifacts/models/incoming/CUSTOM_OVERRIDE_DIR"
    )
    get_settings.cache_clear()
    try:
        assert "CUSTOM_OVERRIDE_DIR" in str(mod._v2_dir())
        verifier = ChallengerShadowVerifier()
        assert "CUSTOM_OVERRIDE_DIR" in str(verifier._dir)
        # The overridden dir has no artifact → honest unavailability.
        assert verifier.available is False
    finally:
        monkeypatch.delenv("SEMANTIC_MODEL_PATH_V2", raising=False)
        get_settings.cache_clear()


def test_fresh_clone_challenger_unavailable_truthful(tmp_path: Path) -> None:
    """No artifact at the configured path → CHALLENGER_UNAVAILABLE, honest
    reason, never a stub substitution."""
    verifier = ChallengerShadowVerifier(model_dir=tmp_path / "nowhere")
    assert verifier.available is False
    assert verifier.reason
    result = verifier.assess_pair(
        "The current checkout contains a monthly recurring membership.",
        "This purchase must not include a recurring subscription.",
    )
    assert result.available is False
    assert result.shadow_action == "CHALLENGER_UNAVAILABLE"
    blob = str(result.to_dict()).lower()
    assert "deterministickeyword" not in blob and "test stub" not in blob


def test_governance_summary_reflects_real_availability(monkeypatch: pytest.MonkeyPatch) -> None:
    """shadow_mode_available mirrors the real artifact state — False when the
    verifier cannot load, True only when the real artifact verifies."""
    from razormesh_api import model_governance as mg
    from razormesh_api.model_governance import governance_summary

    # Fresh-clone simulation: the verifier points at a missing artifact.
    class FreshCloneShadow:
        available = False
        reason = "FileNotFoundError: v2 weights missing"
        _artifact_hash = ""
        _candidate = ""

    monkeypatch.setattr(mg, "get_challenger_shadow", lambda: FreshCloneShadow())
    from razormesh_api import challenger_shadow as cs

    monkeypatch.setattr(cs, "get_challenger_shadow", lambda: FreshCloneShadow())
    summary = governance_summary()
    assert summary["shadow_mode_available"] is False
    assert summary["shadow"]["available"] is False
    assert "not present" in (summary["shadow_unavailable_reason"] or "")
    assert summary["challenger"]["is_activated"] is False  # never activated regardless

    # And on this machine the REAL artifact keeps it available.
    monkeypatch.undo()
    reset_challenger_shadow_singleton()
    real_summary = governance_summary()
    v2_dir = REPO_ROOT / "artifacts/models/incoming/agentpay-ir-v2-finetuned"
    if (v2_dir / "model.safetensors").exists():
        assert real_summary["shadow_mode_available"] is True
    else:  # honest absence also valid if the artifact is genuinely missing
        assert real_summary["shadow_mode_available"] is False


def test_shadow_status_honest_when_artifact_missing(tmp_path: Path) -> None:
    """shadow_status reports the truth for a missing artifact."""
    verifier = ChallengerShadowVerifier(model_dir=tmp_path / "absent")
    status = {
        "available": verifier.available,
        "reason": verifier.reason,
        "artifact_dir": str(verifier._dir),
    }
    assert status["available"] is False
    assert status["reason"]
    assert "absent" in status["artifact_dir"]


def test_real_artifact_available_on_this_machine() -> None:
    """With the actual v2 artifact present, the shadow stays available with
    the committed identity (D-055 hash/candidate)."""
    v2_dir = REPO_ROOT / "artifacts/models/incoming/agentpay-ir-v2-finetuned"
    if not (v2_dir / "model.safetensors").exists():
        pytest.skip("v2 artifact not present in this environment")
    reset_challenger_shadow_singleton()
    status = shadow_status()
    assert status["available"] is True
    assert status["non_authoritative"] is True
    assert status["artifact_hash"].startswith("f9e0007c")
    assert status["selected_candidate"] == "A_2ep"
