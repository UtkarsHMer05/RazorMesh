"""P3-M40/M41/M46 corrected: semantic runtime adapter for Phase-4.

This module bridges the fine-tuned DeBERTa NLI verifier (``semantic_verifier``)
into the Phase-4 acceptance orchestrator's semantic stage. It replaces the
Phase-1 ``assess(texts)`` seam with pair-based verification that mirrors what
the ``SemanticEvidenceBuilder`` and the frozen AgentPay-IR corpus define.

Flow:
    intent + checkout + catalog facts
        -> SemanticEvidenceBuilder.build_pairs()
        -> DebertaNLISemanticVerifier.verify() per pair
        -> aggregate pair verdicts (conservative)
        -> fuse with deterministic RazorGuard decision
        -> record audit events

Fail-closed: any model/configuration failure results in CHALLENGE with
``fail_closed=True``, never a silent ALLOW or keyword-verifier fallback.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

from razormesh_api.domain.checkout import CheckoutEnvelope
from razormesh_api.domain.intent import IntentContract
from razormesh_api.ledger import EvidenceLedger
from razormesh_api.semantic_audit import (
    record_policy_fusion,
    record_semantic_verification,
)
from razormesh_api.semantic_evidence import CommerceEvidence, EvidencePair, build_pairs
from razormesh_api.semantic_verifier import (
    DebertaNLISemanticVerifier,
    DeterministicDecision,
    SemanticAction,
    SemanticVerdict,
    fuse,
)

POLICY_PATH = Path("data/phase3/policy/semantic_thresholds_v3.json")
MODEL_DIR = Path("artifacts/models/incoming/phase3-finetuned-v2")

# AgentPay-IR v2 candidate artifact location (post-Colab). INACTIVE backend
# option: `deberta_v2` resolves to this directory ONLY when the artifact exists
# there; otherwise the option fails CLOSED exactly like a missing deberta model
# (never a keyword substitution, never a silent downgrade to the v2 artifact
# that is not there). Activation requires the human-returned artifact plus a
# recorded manifest-hash verification (see docs/agentpay_ir_v2/).
MODEL_DIR_V2 = Path("artifacts/models/incoming/agentpay-ir-v2-finetuned")

# Repo root, derived from this file's source location so RELATIVE model/policy
# paths resolve identically no matter which CWD the backend process was started
# from (repo-root `make dev-api`, `services/api` pytest, etc.). Correction
# brief §15: a correct artifact at the configured path must actually load; a
# path misresolved against the process CWD would silently fail closed instead.
REPO_ROOT = Path(__file__).resolve().parents[4]


def resolve_repo_path(path: Path | str) -> Path:
    """Resolve a configured artifact/policy path against the repo root."""
    p = Path(path)
    return p if p.is_absolute() else REPO_ROOT / p


# Per-process verifier + artifact-hash caches (correction brief §15): the
# 738 MB DeBERTa weights load exactly once per backend process, never per
# request. Keyed by resolved (model_dir, policy_path) so tests can point at
# throwaway fixture artifacts without colliding with the production cache.
_VERIFIER_CACHE: dict[tuple[str, str], DebertaNLISemanticVerifier] = {}
_ARTIFACT_HASH_CACHE: dict[str, str] = {}


def clear_semantic_verifier_cache() -> None:
    """Test/diagnostic hook: drop cached verifiers and artifact hashes."""
    _VERIFIER_CACHE.clear()
    _ARTIFACT_HASH_CACHE.clear()


def get_semantic_verifier(*, model_dir: Path, policy_path: Path) -> DebertaNLISemanticVerifier:
    """Return the process-wide verifier for this (model, policy) pair."""
    key = (str(model_dir.resolve()), str(policy_path.resolve()))
    verifier = _VERIFIER_CACHE.get(key)
    if verifier is None:
        verifier = DebertaNLISemanticVerifier(model_dir=model_dir, policy_path=policy_path)
        _VERIFIER_CACHE[key] = verifier
    return verifier


def artifact_sha256(model_dir: Path) -> str:
    """SHA-256 of the artifact's model.safetensors, computed once per process."""
    weights = model_dir / "model.safetensors"
    key = str(weights.resolve())
    digest = _ARTIFACT_HASH_CACHE.get(key)
    if digest is None:
        import hashlib

        digest = hashlib.sha256(weights.read_bytes()).hexdigest()
        _ARTIFACT_HASH_CACHE[key] = digest
    return digest


@dataclass(frozen=True)
class SemanticRuntimeOutcome:
    final_decision: DeterministicDecision
    semantic_action: SemanticAction
    p_contradiction: float
    p_entailment: float
    p_neutral: float
    model_id: str
    policy_version: str
    fail_closed: bool
    reason: str | None
    pair_count: int = 0
    duration_ms: float = 0.0
    model_version: str = ""
    model_artifact_hash: str = ""
    semantic_backend: str = "deberta"


def _collect_facts(intent: IntentContract) -> tuple[str, ...]:
    """Extract brand allowlist from the intent."""
    if intent.brand_restriction:
        return tuple(intent.brand_restriction.brands)
    return ()


def _build_evidence_from_checkout(
    intent: IntentContract, envelope: CheckoutEnvelope
) -> list[CommerceEvidence]:
    """Build one CommerceEvidence per line item, using intent constraints."""
    evidences: list[CommerceEvidence] = []
    for item in envelope.line_items:
        brand = item.display_name.value.text if item.display_name else None
        evidences.append(
            CommerceEvidence(
                item_title=item.display_name.value.text if item.display_name else "item",
                price_minor=item.unit_price.amount_minor if item.unit_price else None,
                currency=item.unit_price.currency if item.unit_price else None,
                brand=brand,
                condition=item.condition,
                seller_name=str(envelope.merchant_id),
                recurring_terms=envelope.has_recurring_terms(),
                shipping_included=(
                    envelope.shipping.amount_minor == 0 if envelope.shipping else None
                ),
            )
        )
    return evidences


def _aggregate(verdicts: list[SemanticVerdict]) -> SemanticAction:
    """Conservative: any BLOCK -> BLOCK; else any CHALLENGE -> CHALLENGE; else PASS."""
    has_block = any(v.action is SemanticAction.BLOCK for v in verdicts)
    has_challenge = any(v.action is SemanticAction.CHALLENGE for v in verdicts)
    if has_block:
        return SemanticAction.BLOCK
    if has_challenge:
        return SemanticAction.CHALLENGE
    return SemanticAction.PASS


def run_semantic_runtime(
    *,
    intent: IntentContract,
    envelope: CheckoutEnvelope,
    deterministic: DeterministicDecision,
    intent_id: str,
    attempt_id: str,
    ledger: EvidenceLedger,
    model_dir: Path | None = None,
    policy_path: Path | None = None,
    semantic_backend: str = "deberta",
) -> SemanticRuntimeOutcome:
    """Run the full semantic verification + fusion pipeline.

    Returns a ``SemanticRuntimeOutcome`` with the final fused decision. The
    decision is already recorded to the audit ledger.
    """
    policy_path = resolve_repo_path(policy_path or POLICY_PATH)
    model_dir = resolve_repo_path(model_dir or MODEL_DIR)
    started = datetime.now(UTC)
    pair_count = 0
    duration_ms = 0.0

    # 1) Build evidence pairs from the confirmed intent + checkout.
    brands = _collect_facts(intent)
    # §17: the condition pair exists only when the human actually constrained
    # condition. An intent with no condition_restriction has no condition
    # hypothesis to verify; emitting one anyway would map unknown evidence to
    # NEUTRAL -> CHALLENGE for every legitimately permissive authorization.
    allowed_conditions = (
        tuple(sorted(intent.condition_restriction.allowed_conditions))
        if intent.condition_restriction is not None
        else None
    )
    evidences = _build_evidence_from_checkout(intent, envelope)
    # Server-authoritative checkout total for the budget aspect: the corpus
    # ``price_constraint`` template states the FINAL tax-inclusive total, and
    # that is what a budget ceiling actually constrains.
    final_total_minor = (
        sum(i.unit_price.amount_minor * i.quantity for i in envelope.line_items)
        + envelope.tax.amount_minor
        + envelope.shipping.amount_minor
        + envelope.fees.amount_minor
    )
    all_pairs: list[EvidencePair] = []
    for evidence in evidences:
        all_pairs.extend(
            build_pairs(
                replace(evidence, final_total_minor=final_total_minor),
                max_amount_minor=intent.max_total.amount_minor,
                currency=intent.currency,
                recurring_forbidden=not intent.recurring_allowed,
                brand_allowlist=brands,
                allowed_conditions=allowed_conditions,
            )
        )
    pair_count = len(all_pairs)

    # 2) Run semantic verification.
    verifier: DebertaNLISemanticVerifier | None = None
    if pair_count == 0:
        # Evidence completeness (correction brief §12): with no verifiable
        # aspect the authorization cannot be confirmed — fail closed to
        # CHALLENGE instead of vacuously PASSing an empty semantic check.
        verdicts = [
            SemanticVerdict(
                action=SemanticAction.CHALLENGE,
                p_contradiction=0.0,
                p_entailment=0.0,
                p_neutral=0.0,
                model_id="evidence-builder",
                policy_version="n/a",
                reason="no_verifiable_aspects",
            )
        ]
    try:
        if pair_count == 0:
            pass
        elif semantic_backend == "deberta":
            active_model_dir = model_dir
            verifier = get_semantic_verifier(model_dir=model_dir, policy_path=policy_path)
            verdicts = [
                verifier.verify(premise=pair.premise, hypothesis=pair.hypothesis)
                for pair in all_pairs
            ]
        elif semantic_backend == "deberta_v2":
            # AgentPay-IR v2 candidate backend — INACTIVE until the artifact
            # exists at MODEL_DIR_V2. A missing/corrupt artifact fails CLOSED
            # (CHALLENGE), exactly like the deberta backend's missing-model
            # path; it is never substituted with the keyword stub.
            v2_dir = resolve_repo_path(MODEL_DIR_V2)
            if not (v2_dir / "config.json").exists():
                raise FileNotFoundError(f"agentpay-ir-v2 artifact not present at {v2_dir}")
            active_model_dir = v2_dir
            verifier = get_semantic_verifier(model_dir=v2_dir, policy_path=policy_path)
            verdicts = [
                verifier.verify(premise=pair.premise, hypothesis=pair.hypothesis)
                for pair in all_pairs
            ]
        elif semantic_backend == "deterministic_test_stub":
            # Visible stub — never silently substituted.
            from razormesh_api.semantic import DeterministicKeywordVerifier

            kw = DeterministicKeywordVerifier()
            texts = tuple(p.premise + " " + p.hypothesis for p in all_pairs)
            assessment = kw.assess(texts)
            if assessment.verdict.value == "UNSAFE":
                verdicts = [
                    SemanticVerdict(
                        action=SemanticAction.BLOCK,
                        p_contradiction=0.99,
                        p_entailment=0.005,
                        p_neutral=0.005,
                        model_id="DETERMINISTIC_TEST_STUB",
                        policy_version="test-stub",
                    )
                ]
            else:
                verdicts = [
                    SemanticVerdict(
                        action=SemanticAction.PASS,
                        p_contradiction=0.01,
                        p_entailment=0.98,
                        p_neutral=0.01,
                        model_id="DETERMINISTIC_TEST_STUB",
                        policy_version="test-stub",
                    )
                ]
        else:
            raise ValueError(f"unknown semantic_backend: {semantic_backend!r}")
    except Exception as exc:  # noqa: BLE001 - fail closed on ANY model/config failure
        outcome = SemanticRuntimeOutcome(
            final_decision=(
                DeterministicDecision.BLOCK
                if deterministic is DeterministicDecision.BLOCK
                else DeterministicDecision.CHALLENGE
            ),
            semantic_action=SemanticAction.CHALLENGE,
            p_contradiction=0.0,
            p_entailment=0.0,
            p_neutral=0.0,
            model_id="unknown",
            policy_version="unknown",
            fail_closed=True,
            reason=f"{type(exc).__name__}: {exc}",
            pair_count=pair_count,
            duration_ms=0.0,
            semantic_backend=semantic_backend,
        )
        # Record the fail-closed outcome to the audit ledger.
        fail_verdict = SemanticVerdict(
            action=outcome.semantic_action,
            p_entailment=0.0,
            p_neutral=0.0,
            p_contradiction=0.0,
            model_id=outcome.model_id,
            policy_version=outcome.policy_version,
            fail_closed=True,
            reason=outcome.reason,
        )
        record_semantic_verification(
            ledger=ledger,
            intent_id=intent_id,
            attempt_id=attempt_id,
            verdict=fail_verdict,
            semantic_backend=semantic_backend,
            model_version="unknown",
            model_artifact_hash="",
            pair_count=pair_count,
            duration_ms=0.0,
        )
        record_policy_fusion(
            ledger=ledger,
            intent_id=intent_id,
            attempt_id=attempt_id,
            deterministic=deterministic,
            verdict=fail_verdict,
        )
        return outcome

    elapsed = datetime.now(UTC) - started
    duration_ms = elapsed.total_seconds() * 1000

    # 3)/4) Conservative aggregation (§18: any BLOCK -> BLOCK, else any
    #    CHALLENGE -> CHALLENGE, else PASS) with a REAL pair verdict as the
    #    representative, so recorded probabilities stay bound to an actual
    #    pair and a late contradiction is never averaged away by ordering.
    if any(v.action is SemanticAction.BLOCK for v in verdicts):
        primary = next(v for v in verdicts if v.action is SemanticAction.BLOCK)
    elif any(v.action is SemanticAction.CHALLENGE for v in verdicts):
        primary = next(v for v in verdicts if v.action is SemanticAction.CHALLENGE)
    else:
        primary = (
            verdicts[0]
            if verdicts
            else SemanticVerdict(
                action=SemanticAction.CHALLENGE,
                p_contradiction=0.0,
                p_entailment=0.0,
                p_neutral=0.0,
                model_id="unknown",
                policy_version="unknown",
            )
        )
    semantic_action = _aggregate(verdicts)
    # The selection above must equal the §18 aggregate; verified by tests
    # via sr._aggregate and by test_aggregation_is_conservative.
    _ = semantic_action

    # 5) Fuse with deterministic decision.
    final = fuse(deterministic, primary)

    # 6) Record audit events. Per-pair fail-closed verdicts (model missing,
    #    hash mismatch, inference error) propagate to the outcome (§20).
    fail_closed_any = any(v.fail_closed for v in verdicts)
    fail_reason = next((v.reason for v in verdicts if v.fail_closed), None)
    if semantic_backend in ("deberta", "deberta_v2"):
        model_version = verifier.model_version if verifier is not None else active_model_dir.name
        try:
            model_hash = artifact_sha256(active_model_dir)
        except Exception:  # noqa: BLE001 - unreadable weights stay fail-closed, never crash
            model_hash = ""
    else:
        model_version = "DETERMINISTIC_TEST_STUB"
        model_hash = ""
    record_semantic_verification(
        ledger=ledger,
        intent_id=intent_id,
        attempt_id=attempt_id,
        verdict=primary,
        semantic_backend=semantic_backend,
        model_version=model_version,
        model_artifact_hash=model_hash,
        pair_count=pair_count,
        duration_ms=duration_ms,
    )
    record_policy_fusion(
        ledger=ledger,
        intent_id=intent_id,
        attempt_id=attempt_id,
        deterministic=deterministic,
        verdict=primary,
    )

    return SemanticRuntimeOutcome(
        final_decision=final,
        semantic_action=primary.action,
        p_contradiction=primary.p_contradiction,
        p_entailment=primary.p_entailment,
        p_neutral=primary.p_neutral,
        model_id=primary.model_id,
        policy_version=primary.policy_version,
        fail_closed=fail_closed_any,
        reason=fail_reason,
        pair_count=pair_count,
        duration_ms=duration_ms,
        model_version=model_version,
        model_artifact_hash=model_hash,
        semantic_backend=semantic_backend,
    )


__all__ = [
    "SemanticRuntimeOutcome",
    "run_semantic_runtime",
]
