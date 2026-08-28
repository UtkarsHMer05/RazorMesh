"""P3-M38/M40: SemanticVerifier + conservative fusion (the security core).

`SemanticAction` mirrors the master prompt: PASS / CHALLENGE / BLOCK.
`ThresholdPolicy` loads the calibrated manifest (P3-M37) and applies the
frozen action rule as a PURE function.

`DebertaNLISemanticVerifier` wraps the local model behind a scorer seam:
- model weights load LAZILY and once;
- ANY failure (missing weights, runtime error) fails CLOSED to CHALLENGE
  with an explicit reason — never silent ALLOW (P3-S08);
- the verifier holds no payment client, no repositories, no network
  capability beyond local weight loading (P3-S06/S16).

`fuse()` implements D-039 conservative fusion: semantics may only STRICTEN a
deterministic RazorGuard decision. The exhaustive matrix + Hypothesis
property test in tests/test_semantic_fusion.py make this release-blocking.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any


class SemanticAction(StrEnum):
    PASS = "PASS"  # noqa: S105 - decision label, not a secret
    CHALLENGE = "CHALLENGE"
    BLOCK = "BLOCK"


class DeterministicDecision(StrEnum):
    ALLOW = "ALLOW"
    CHALLENGE = "CHALLENGE"
    BLOCK = "BLOCK"


@dataclass(frozen=True)
class SemanticVerdict:
    action: SemanticAction
    p_entailment: float
    p_neutral: float
    p_contradiction: float
    model_id: str
    policy_version: str
    fail_closed: bool = False
    reason: str | None = None


def apply_threshold_policy(
    p_entailment: float,
    p_neutral: float,
    p_contradiction: float,
    *,
    tau_block: float,
    tau_entail: float,
) -> SemanticAction:
    """Frozen rule from P3-M37 calibration (order matters)."""
    if p_contradiction >= tau_block:
        return SemanticAction.BLOCK
    if p_entailment >= tau_entail:
        return SemanticAction.PASS
    return SemanticAction.CHALLENGE


def load_threshold_policy(path: Path) -> dict[str, Any]:
    manifest: dict[str, Any] = json.loads(path.read_text())
    assert (
        manifest.get("gold_validation_status") == "PENDING_GOLD_VALIDATION"
        or manifest.get("gold_validation_status") == "GOLD_VALIDATED"
    ), "policy manifest missing honest validation status"
    selected = manifest["selected"]
    assert 0.0 <= selected["tau_block"] <= 1.0
    assert 0.0 <= selected["tau_entail"] <= 1.0
    return manifest


def fuse(deterministic: DeterministicDecision, semantic: SemanticVerdict) -> DeterministicDecision:
    """D-039: semantics may only STRICTEN. Never loosens BLOCK/CHALLENGE."""
    if deterministic is DeterministicDecision.BLOCK:
        return DeterministicDecision.BLOCK
    if deterministic is DeterministicDecision.CHALLENGE:
        # only a semantic BLOCK escalates; PASS/CHALLENGE keep the challenge
        return (
            DeterministicDecision.BLOCK
            if semantic.action is SemanticAction.BLOCK
            else DeterministicDecision.CHALLENGE
        )
    # deterministic ALLOW:
    if semantic.action is SemanticAction.BLOCK:
        return DeterministicDecision.BLOCK
    if semantic.action is SemanticAction.CHALLENGE:
        return DeterministicDecision.CHALLENGE
    return DeterministicDecision.ALLOW


class DebertaNLISemanticVerifier:
    """Production verifier: lazy local model + frozen thresholds + fail-closed."""

    def __init__(
        self,
        *,
        model_dir: Path,
        policy_path: Path,
        scorer: Callable[[str, str], tuple[float, float, float]] | None = None,
    ) -> None:
        self._model_dir = model_dir
        self._scorer = scorer
        self._policy = load_threshold_policy(policy_path)
        sel = self._policy["selected"]
        self._tau_block = float(sel["tau_block"])
        self._tau_entail = float(sel["tau_entail"])
        self._model_id = self._policy["model"]
        self._policy_version = self._policy["policy_version"]
        self._model: Any = None
        self._tokenizer: Any = None
        self._torch: Any = None
        self._idx_contra: int | None = None
        self._idx_entail: int | None = None
        self._idx_neutral: int | None = None

    @property
    def policy_version(self) -> str:
        version: str = self._policy["policy_version"]
        return version

    @property
    def model_version(self) -> str:
        """Short non-secret artifact identifier (correction brief §15/§21)."""
        return str(self._policy.get("model") or self._model_dir.name)

    def _verify_artifact_integrity(self) -> None:
        """If a model_manifest.json ships with the artifact, enforce its hash.

        A manifest with a mismatching model SHA-256 must fail closed (correction
        brief §15/§20): the load raises and ``verify`` converts that into a
        CHALLENGE verdict rather than running tampered weights.
        """
        manifest_path = self._model_dir / "model_manifest.json"
        if not manifest_path.exists():
            return
        manifest = json.loads(manifest_path.read_text())
        weights = self._model_dir / "model.safetensors"
        expected = manifest.get("model_sha256")
        if not isinstance(expected, str) or not expected:
            raise ValueError("model_manifest.json missing model_sha256")
        import hashlib

        digest = hashlib.sha256(weights.read_bytes()).hexdigest()
        if digest != expected:
            raise ValueError(f"model artifact hash mismatch: manifest={expected} actual={digest}")

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        import torch
        from transformers import (
            AutoModelForSequenceClassification,
            AutoTokenizer,
        )

        self._verify_artifact_integrity()
        tok = AutoTokenizer.from_pretrained(str(self._model_dir))
        mdl = AutoModelForSequenceClassification.from_pretrained(str(self._model_dir))
        mdl.eval()
        self._torch = torch
        self._tokenizer = tok
        self._model = mdl
        # Read label_map from artifact (P3-M38) so the index→label projection
        # is data-driven, never hard-coded. Fall back to the policy manifest
        # if the artifact has no label_map.json (legacy/zero-shot baseline).
        label_map = self._read_label_map()
        self._idx_contra = next((i for i, v in label_map.items() if v == "contradiction"), 0)
        self._idx_entail = next((i for i, v in label_map.items() if v == "entailment"), 1)
        self._idx_neutral = next((i for i, v in label_map.items() if v == "neutral"), 2)

    def _read_label_map(self) -> dict[int, str]:
        lm_path = self._model_dir / "label_map.json"
        if lm_path.exists():
            raw = json.loads(lm_path.read_text())
            return {int(k): v for k, v in raw.items()}
        manifest_lm = self._policy.get("label_map")
        if manifest_lm:
            return {int(k): v for k, v in manifest_lm.items()}
        # Legacy fallback: cross-encoder/nli-deberta-v3-base baseline order.
        return {0: "contradiction", 1: "entailment", 2: "neutral"}

    def _score_local(self, premise: str, hypothesis: str) -> tuple[float, float, float]:
        self._ensure_loaded()
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
        return (
            float(probs[self._idx_contra]),
            float(probs[self._idx_entail]),
            float(probs[self._idx_neutral]),
        )

    def verify(self, *, premise: str, hypothesis: str) -> SemanticVerdict:
        try:
            if self._scorer is not None:
                pc, pe, pn = self._scorer(premise, hypothesis)
            else:
                self._ensure_loaded()
                pc, pe, pn = self._score_local(premise, hypothesis)
        except Exception as exc:  # noqa: BLE001 - fail closed on ANY failure
            return SemanticVerdict(
                action=SemanticAction.CHALLENGE,
                p_entailment=0.0,
                p_neutral=0.0,
                p_contradiction=0.0,
                model_id=self._model_id,
                policy_version=self._policy_version,
                fail_closed=True,
                reason=f"{type(exc).__name__}",
            )
        action = apply_threshold_policy(
            p_entailment=pe,
            p_neutral=pn,
            p_contradiction=pc,
            tau_block=self._tau_block,
            tau_entail=self._tau_entail,
        )
        return SemanticVerdict(
            action=action,
            p_entailment=pe,
            p_neutral=pn,
            p_contradiction=pc,
            model_id=self._model_id,
            policy_version=self._policy_version,
        )
