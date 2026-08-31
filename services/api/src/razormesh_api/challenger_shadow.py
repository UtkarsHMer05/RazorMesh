"""Deep-engine correction (G003/G004): real AgentPay-IR v2 challenger shadow.

Contract (master prompt §G003):
- Loads the ACTUAL fine-tuned AgentPay-IR v2 artifact (the exact rejected
  candidate A_2ep) — never a keyword verifier, never any other model.
- Runs ONLY on new, non-frozen demo pairs. The frozen one-shot evaluation is
  consumed (D-055); this module never touches frozen test/gold/OOD data and
  never computes benchmark metrics.
- NON_AUTHORITATIVE = True, always. Output NEVER enters fusion, ticket
  issuance, or provider decisions. It is display-only evidence.
- Fails safely: any load/inference failure surfaces as CHALLENGER_UNAVAILABLE
  with an honest reason — never a substitution, never a silent fallback.

Isolation design (G004): the shadow holds no repositories, no ledger, no
provider client, and does NOT route through the production policy loader
(`load_threshold_policy` is a production wiring gate; the v4 policy was never
wired and truthfully carries no gold_validation_status). Instead the shadow
reads the committed v4 thresholds (D-055 provenance table: v2's runtime policy
is semantic-thresholds-v4, calibrated on the FINAL corpus validation split
only, before any frozen contact) and enforces the policy's own model_sha256
against the actual weights. No threshold is tuned here.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from razormesh_api.semantic_runtime import resolve_repo_path
from razormesh_api.semantic_verifier import apply_threshold_policy
from razormesh_api.settings import get_settings

# The exact rejected candidate artifact (D-055: ZIP sha256 4c933eec…,
# candidate A_2ep, model.safetensors sha256 f9e0007c…).
_V2_DIR = Path("artifacts/models/incoming/agentpay-ir-v2-finetuned")

# v2's documented runtime policy (FINAL_FROZEN_EVALUATION provenance table).
# Committed pre-freeze calibration; read-only here, never recalibrated.
_V2_POLICY = Path("data/phase3/policy/semantic_thresholds_v4.json")

NON_AUTHORITATIVE = True
NEVER_ENTERS = ("fusion", "ticket", "provider")

_MAX_TEXT_LENGTH = 512


@dataclass(frozen=True)
class ChallengerShadowResult:
    available: bool
    shadow_action: str  # PASS / CHALLENGE / BLOCK — the v2 model's own labels
    p_contradiction: float
    p_entailment: float
    p_neutral: float
    artifact_hash: str
    selected_candidate: str
    model_id: str
    policy_version: str
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "shadow_action": self.shadow_action,
            "probabilities": {
                "contradiction": self.p_contradiction,
                "entailment": self.p_entailment,
                "neutral": self.p_neutral,
            },
            "artifact_hash": self.artifact_hash,
            "selected_candidate": self.selected_candidate,
            "model_id": self.model_id,
            "policy_version": self.policy_version,
            "reason": self.reason,
        }


class ChallengerShadowVerifier:
    """Isolated inference path over the real (rejected) v2 checkpoint.

    Deliberately shares NO state with the production verifier path: separate
    lazy-loaded model instance, separate policy reader. Nothing in this class
    can reach RazorGuard, the fusion seam, ticket issuance, the ledger, or
    the provider.
    """

    def __init__(self, model_dir: Path | None = None, policy_path: Path | None = None) -> None:
        self._dir = resolve_repo_path(model_dir or _V2_DIR)
        self._policy_file = resolve_repo_path(policy_path or _V2_POLICY)
        self._model: Any = None
        self._tokenizer: Any = None
        self._torch: Any = None
        self._idx_contra: int | None = None
        self._idx_entail: int | None = None
        self._idx_neutral: int | None = None
        self._tau_block = 0.0
        self._tau_entail = 0.0
        self._load_error: str | None = None
        self._artifact_hash = ""
        self._candidate = ""
        self._model_id = "agentpay-ir-v2-finetuned"
        self._policy_version = "semantic-thresholds-v4 (shadow-lane only)"
        self._probe_identity()

    # -- availability ---------------------------------------------------
    @property
    def available(self) -> bool:
        return self._load_error is None

    @property
    def reason(self) -> str | None:
        return self._load_error

    def _fail(self, exc: Exception) -> None:
        self._load_error = f"{type(exc).__name__}: {exc}"

    def _probe_identity(self) -> None:
        """Hash the weights + verify manifest/policy identity, up front.

        Any missing/corrupt piece marks the challenger UNAVAILABLE honestly.
        """
        try:
            import hashlib

            weights = self._dir / "model.safetensors"
            if not weights.exists():
                raise FileNotFoundError(f"v2 weights missing at {weights}")
            manifest = json.loads((self._dir / "model_manifest.json").read_text())
            expected = (manifest.get("artifact_files_sha256") or {}).get("model.safetensors")
            if not isinstance(expected, str) or not expected:
                raise ValueError("v2 manifest lacks model.safetensors sha256")
            digest = hashlib.sha256(weights.read_bytes()).hexdigest()
            if digest != expected:
                raise ValueError("v2 artifact hash mismatch — challenger unavailable")
            # The v4 policy must attest the SAME weights it was calibrated for.
            policy = json.loads(self._policy_file.read_text())
            if policy.get("model_sha256") != digest:
                raise ValueError("v4 policy model_sha256 does not match the v2 artifact")
            selected = policy.get("selected") or {}
            self._tau_block = float(selected["tau_block"])
            self._tau_entail = float(selected["tau_entail"])
            if not (0.0 <= self._tau_block <= 1.0 and 0.0 <= self._tau_entail <= 1.0):
                raise ValueError("v4 policy taus out of range")
            self._artifact_hash = digest
            self._candidate = str(manifest.get("selected_candidate") or "")
        except Exception as exc:  # noqa: BLE001 - honest unavailability, never a fallback
            self._fail(exc)
            self._artifact_hash = ""
            self._candidate = ""

    def _ensure_loaded(self) -> None:
        """Lazy-load the real v2 weights+tokenizer (once per instance)."""
        if self._model is not None or self._load_error is not None:
            return
        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer

            tok = AutoTokenizer.from_pretrained(str(self._dir))
            mdl = AutoModelForSequenceClassification.from_pretrained(str(self._dir))
            mdl.eval()
            # Label map is read from the ARTIFACT (P3-M38 discipline): the
            # index→label projection is data-driven, never hard-coded.
            lm_path = self._dir / "label_map.json"
            label_map = (
                {int(k): v for k, v in json.loads(lm_path.read_text()).items()}
                if lm_path.exists()
                else {}
            )
            if not label_map:
                raise ValueError("v2 artifact lacks label_map.json")
            self._idx_contra = next(i for i, v in label_map.items() if v == "contradiction")
            self._idx_entail = next(i for i, v in label_map.items() if v == "entailment")
            self._idx_neutral = next(i for i, v in label_map.items() if v == "neutral")
            self._torch = torch
            self._tokenizer = tok
            self._model = mdl
        except Exception as exc:  # noqa: BLE001 - honest unavailability, never a fallback
            self._fail(exc)

    # -- inference ------------------------------------------------------
    def assess_pair(self, premise: str, hypothesis: str) -> ChallengerShadowResult:
        """Run the real v2 model on ONE new demo pair (never frozen data)."""
        premise = premise.strip()[:_MAX_TEXT_LENGTH]
        hypothesis = hypothesis.strip()[:_MAX_TEXT_LENGTH]
        if not premise or not hypothesis:
            return self._unavailable(reason="empty premise/hypothesis")
        try:
            self._ensure_loaded()
            if self._model is None or self._load_error is not None:
                return self._unavailable(reason=self._load_error or "challenger not loaded")
            feats = self._tokenizer(
                premise,
                hypothesis,
                truncation=True,
                max_length=256,
                padding=True,
                return_tensors="pt",
            )
            with self._torch.no_grad():
                probs = self._torch.softmax(self._model(**feats).logits, -1)[0]
            assert self._idx_contra is not None
            assert self._idx_entail is not None
            assert self._idx_neutral is not None
            p_contra = float(probs[self._idx_contra])
            p_entail = float(probs[self._idx_entail])
            p_neutral = float(probs[self._idx_neutral])
            action = apply_threshold_policy(
                p_entailment=p_entail,
                p_neutral=p_neutral,
                p_contradiction=p_contra,
                tau_block=self._tau_block,
                tau_entail=self._tau_entail,
            )
            return ChallengerShadowResult(
                available=True,
                shadow_action=str(action.value),
                p_contradiction=p_contra,
                p_entailment=p_entail,
                p_neutral=p_neutral,
                artifact_hash=self._artifact_hash,
                selected_candidate=self._candidate,
                model_id=self._model_id,
                policy_version=self._policy_version,
            )
        except Exception as exc:  # noqa: BLE001 - honest unavailability, never a fallback
            return self._unavailable(reason=f"{type(exc).__name__}: {exc}")

    def _unavailable(self, reason: str | None = None) -> ChallengerShadowResult:
        return ChallengerShadowResult(
            available=False,
            shadow_action="CHALLENGER_UNAVAILABLE",
            p_contradiction=0.0,
            p_entailment=0.0,
            p_neutral=0.0,
            artifact_hash=self._artifact_hash or "",
            selected_candidate=self._candidate or "",
            model_id=self._model_id,
            policy_version=self._policy_version,
            reason=reason or self._load_error or "challenger unavailable",
        )


# Per-process singleton: the 738 MB v2 weights load at most once per backend
# process. Deliberately separate from the production verifier cache so the
# two lanes can never share an instance.
_SHADOW_SINGLETON: ChallengerShadowVerifier | None = None


def get_challenger_shadow() -> ChallengerShadowVerifier:
    global _SHADOW_SINGLETON
    if _SHADOW_SINGLETON is None:
        _SHADOW_SINGLETON = ChallengerShadowVerifier()
    return _SHADOW_SINGLETON


def reset_challenger_shadow_singleton() -> None:
    """Test hook: drop the singleton so tests can point at fixture artifacts."""
    global _SHADOW_SINGLETON
    _SHADOW_SINGLETON = None


def shadow_status() -> dict[str, Any]:
    """Honest capability + identity report (no inference)."""
    settings = get_settings()
    shadow = get_challenger_shadow()
    return {
        "mode": "SHADOW — NON-AUTHORITATIVE",
        "non_authoritative": NON_AUTHORITATIVE,
        "never_enters": list(NEVER_ENTERS),
        "available": shadow.available,
        "reason": shadow.reason,
        "artifact_dir": str(_V2_DIR),
        "artifact_hash": shadow._artifact_hash,
        "selected_candidate": shadow._candidate or "A_2ep",
        "model_id": "agentpay-ir-v2-finetuned (candidate A_2ep)",
        "policy_version": "semantic-thresholds-v4 (shadow-lane only)",
        "active_backend": settings.semantic_verifier_backend,
        "is_frozen_evaluation": False,
        "note": (
            "The REAL fine-tuned AgentPay-IR v2 checkpoint runs here on new "
            "demo pairs only. It was rejected by the frozen safety gate "
            "(D-055) and is never authoritative: no fusion, no tickets, no "
            "provider. Frozen evaluation data is never used."
        ),
    }
