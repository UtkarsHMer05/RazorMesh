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

    @property
    def policy_version(self) -> str:
        version: str = self._policy["policy_version"]
        return version

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        import torch  # type: ignore[import-not-found]
        from transformers import (  # type: ignore[import-not-found]
            AutoModelForSequenceClassification,
            AutoTokenizer,
        )

        tok = AutoTokenizer.from_pretrained(str(self._model_dir))
        mdl = AutoModelForSequenceClassification.from_pretrained(str(self._model_dir))
        mdl.eval()
        self._torch = torch
        self._tokenizer = tok
        self._model = mdl

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
        # cross-encoder/nli-deberta-v3-base project-space order: C, E, N
        return float(probs[0]), float(probs[1]), float(probs[2])

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
