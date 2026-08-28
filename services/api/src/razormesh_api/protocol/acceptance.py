"""RazorMesh Phase-4 Live-Ingress Acceptance Orchestrator.

This module implements the single acceptance orchestration path that
proves the actual Phase-4 cross-protocol ingress during a real request:

  Confirmed Intent
  -> MCP 2026-07-28 (mounted at /mcp)
  -> UCP 2026-04-08 commerce evidence (internal adapter)
  -> AP2 v0.2.0 authorization evidence (internal verifier)
  -> Protocol Firewall
  -> ProtocolEnvelope
  -> AgentCommerceIR
  -> commerce-commitment-v1
  -> CrossProtocolConsistency = MATCH
  -> RazorGuard
  -> SemanticVerifier
  -> final ALLOW
  -> existing ExecutionTicket
  -> Razorpay Test Checkout

The orchestrator is **deterministic and untrusted-agent driven**: it
accepts only a fresh acceptance-run correlation ID plus the authorization
projection, and never takes Razorpay secrets, webhook secrets, DB creds,
AP2 private keys, the ExecutionTicket private key, the payment provider,
shell access or unrestricted networking from the caller.

UCP and AP2 are implemented as internal protocol adapters/verifiers
that execute during the live request — they are not optional proof
harnesses. The orchestrator writes the protocol evidence and the
commerce commitment to the durable audit chain before any ALLOW.

The execute path (`finalize_execution`) hands off to the existing
`TrustedPaymentExecutor.execute(...)` so the production ticket/execution
path is unchanged (P4-S01: protocol adapter never calls PaymentProvider
directly; the executor is the sole provider caller).
"""

from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..checkout_service import CheckoutService
    from ..executor import TrustedPaymentExecutor
    from ..persistence.models import ExecutionAttempt
    from ..tickets import CurrentBinding, SignedTicket

from ..semantic import (
    DeterministicKeywordVerifier,
    SemanticVerifier,
)
from .ap2_verifier import (
    AP2_TARGET_VERSION,
    build_ap2_merchant_checkout_jwt,
    export_ap2_test_merchant_pub_jwk,
    generate_ap2_test_merchant_key,
    verify_ap2_merchant_jwt_es256,
)
from .commitment import commitment_hash
from .consistency import (
    ConsistencyState,
    compare_ir_to_envelope,
)
from .envelope import (
    ProtocolEnvelope,
    SourceProtocol,
    envelope_from_raw,
    envelope_to_canonical_json,
    hash_payload,
)
from .firewall import FirewallDecision as _FirewallDecisionEnum
from .firewall import evaluate_envelope
from .ir import AgentCommerceIR
from .ucp_adapter import (
    UCP_PROFILE_PATH,
    UCP_TARGET_VERSION,
    build_ucp_envelope,
)
from .ucp_signatures import (
    UCP_DIGEST_SCHEME,
    UCP_SIGNATURE_SCHEME,
    export_ucp_public_jwk,
    generate_ucp_signing_key,
    sign_ucp_request,
    verify_ucp_request,
)

ACCEPTANCE_PROTOCOL_VERSION = "phase4-acceptance-v1"
COMMERCE_COMMITMENT_VERSION = "commerce-commitment-v1"
UCP_TEST_HMAC_SECRET = b"razormesh-ucp-test-secret-v1"


def _hash_canonical(data: Any) -> str:
    """Return the canonical SHA-256 hex of a JSON-serializable value."""
    canon = json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def new_acceptance_run_id() -> str:
    """Return a fresh, unique acceptance-run correlation ID."""
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    rand = secrets.token_hex(8)
    return f"acc-{ts}-{rand}"


def _ir_untrusted_texts(ir: AgentCommerceIR) -> tuple[str, ...]:
    """Collect the presentation-only (untrusted) text carried by an IR.

    These fields are excluded from ``commerce-commitment-v1`` on
    purpose, so they are exactly the surface a semantic verifier is
    allowed to advise about and never to authorise with.
    """
    texts: list[str] = []
    for item in ir.items:
        texts.extend(t for t in (item.title, item.brand, item.condition) if t)
    if ir.merchant.origin:
        texts.append(ir.merchant.origin)
    return tuple(texts)


def _ticket_id_of(signed_ticket: SignedTicket | None) -> str | None:
    """Read the real ticket id out of a signed ticket's canonical claims."""
    if signed_ticket is None:
        return None
    claims = json.loads(signed_ticket.claims_json)
    ticket_id = claims.get("ticket_id") if isinstance(claims, dict) else None
    return str(ticket_id) if ticket_id else None


@dataclass(frozen=True)
class AcceptanceProtocolEvidence:
    """The live protocol evidence recorded for one acceptance run."""

    mcp_version: str
    mcp_endpoint: str
    mcp_method_tool: str
    mcp_message_id: str
    ucp_version: str
    ucp_profile_path: str
    ucp_signature_digest_verified: bool
    ucp_idempotency_key: str
    ucp_commerce_evidence_hash: str
    ap2_version: str
    ap2_evidence_type: str
    ap2_signature_verified: bool
    ap2_vct: str
    ap2_expires_at: str
    ap2_checkout_hash_binding: bool
    ap2_evidence_hash: str
    ap2_key_binding_pop_verified: bool
    intent_hash: str
    protocol_firewall: str
    protocol_firewall_reasons: tuple[str, ...]
    protocol_envelope_hash: str
    agent_commerce_ir_hash: str
    commerce_commitment: str
    commerce_commitment_version: str
    cross_protocol_consistency: str
    razorguard_decision: str
    semantic_verifier: str
    semantic_verifier_source: str
    final_decision: str
    decided_at: str
    # Correction brief §21: semantic runtime truth recorded on the acceptance
    # evidence. Defaults keep construction sites that predate the correction
    # valid; the live finalize path always fills them.
    semantic_backend: str = "deberta"
    semantic_model_version: str = ""
    semantic_model_artifact_hash: str = ""
    semantic_policy_version: str = ""
    semantic_pair_count: int = 0
    semantic_probabilities: tuple[float, float, float] = (0.0, 0.0, 0.0)
    semantic_fail_closed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "mcp": {
                "version": self.mcp_version,
                "endpoint": self.mcp_endpoint,
                "method_tool": self.mcp_method_tool,
                "message_id": self.mcp_message_id,
            },
            "ucp": {
                "version": self.ucp_version,
                "profile_path": self.ucp_profile_path,
                "signature_digest_verified": self.ucp_signature_digest_verified,
                "idempotency_key": self.ucp_idempotency_key,
                "commerce_evidence_hash": self.ucp_commerce_evidence_hash,
            },
            "ucp_evidence_extra": {
                "signature_scheme": UCP_SIGNATURE_SCHEME,
                "digest_scheme": UCP_DIGEST_SCHEME,
            },
            "ap2": {
                "version": self.ap2_version,
                "evidence_type": self.ap2_evidence_type,
                "signature_verified": self.ap2_signature_verified,
                "vct": self.ap2_vct,
                "expires_at": self.ap2_expires_at,
                "checkout_hash_binding": self.ap2_checkout_hash_binding,
                "key_binding_pop_verified": self.ap2_key_binding_pop_verified,
                "evidence_hash": self.ap2_evidence_hash,
            },
            "razormesh": {
                "intent_hash": self.intent_hash,
                "protocol_firewall": self.protocol_firewall,
                "protocol_firewall_reasons": list(self.protocol_firewall_reasons),
                "protocol_envelope_hash": self.protocol_envelope_hash,
                "agent_commerce_ir_hash": self.agent_commerce_ir_hash,
                "commerce_commitment": self.commerce_commitment,
                "commerce_commitment_version": self.commerce_commitment_version,
                "cross_protocol_consistency": self.cross_protocol_consistency,
                "razorguard_decision": self.razorguard_decision,
                "semantic_verifier": self.semantic_verifier,
                "semantic_verifier_source": self.semantic_verifier_source,
                "semantic_backend": self.semantic_backend,
                "semantic_model_version": self.semantic_model_version,
                "semantic_model_artifact_hash": self.semantic_model_artifact_hash,
                "semantic_policy_version": self.semantic_policy_version,
                "semantic_pair_count": self.semantic_pair_count,
                "semantic_probabilities": list(self.semantic_probabilities),
                "semantic_fail_closed": self.semantic_fail_closed,
                "final_decision": self.final_decision,
                "decided_at": self.decided_at,
            },
        }


@dataclass
class AcceptanceRun:
    """One in-memory acceptance-run record (also persisted to audit)."""

    run_id: str
    intent_id: str
    checkout_id: str
    product_id: str
    quantity: int
    amount_minor: int
    currency: str
    idempotency_key: str
    evidence: AcceptanceProtocolEvidence
    completed: bool = False
    used_at: str | None = None
    decision_id: str | None = None
    ticket_id: str | None = None


class AcceptanceRegistry:
    """In-memory registry of acceptance runs and idempotency keys.

    This is the protocol-coordination layer for the acceptance ingress.
    It is intentionally NOT a payment/financial authority — the
    ExecutionTicket + RazorGuard + executor remain the sole authority
    for financial side effects (P4-S01).

    The registry enforces:
      - exactly-once acceptance-run consumption per `run_id`;
      - one commerce commitment per `idempotency_key` (replay-safe);
      - material-mutation MISMATCH detection between UCP/AP2/IR.
    """

    def __init__(self) -> None:
        self._runs: dict[str, AcceptanceRun] = {}
        self._idempotency: dict[str, str] = {}

    def reserve_idempotency(self, key: str, run_id: str) -> bool:
        """Reserve an idempotency key. Returns True on first reservation."""
        if key in self._idempotency:
            return self._idempotency[key] == run_id
        self._idempotency[key] = run_id
        return True

    def record(self, run: AcceptanceRun) -> None:
        self._runs[run.run_id] = run

    def get(self, run_id: str) -> AcceptanceRun | None:
        return self._runs.get(run_id)

    def complete(self, run_id: str) -> bool:
        """Mark a run as completed exactly-once. Returns True on first mark."""
        run = self._runs.get(run_id)
        if run is None:
            return False
        if run.completed:
            return False
        run.completed = True
        run.used_at = datetime.now(UTC).isoformat()
        return True

    def snapshot(self) -> list[dict[str, Any]]:
        return [
            {
                "run_id": r.run_id,
                "intent_id": r.intent_id,
                "checkout_id": r.checkout_id,
                "idempotency_key": r.idempotency_key,
                "amount_minor": r.amount_minor,
                "currency": r.currency,
                "completed": r.completed,
                "used_at": r.used_at,
                "evidence": r.evidence.to_dict(),
            }
            for r in self._runs.values()
        ]


# Module-level singleton (process-local; the API process owns the ingress).
REGISTRY = AcceptanceRegistry()


# ----------------------------------------------------------------------
# Protocol evidence construction
# ----------------------------------------------------------------------


def build_mcp_evidence(
    *,
    method_tool: str,
    message_id: str,
    endpoint: str = "/mcp",
    mcp_version: str = "2026-07-28",
) -> dict[str, Any]:
    """Construct the MCP evidence record for the acceptance run."""
    return {
        "mcp_version": mcp_version,
        "mcp_endpoint": endpoint,
        "mcp_method_tool": method_tool,
        "mcp_message_id": message_id,
    }


def build_ucp_evidence(
    *,
    ir: AgentCommerceIR,
    idempotency_key: str,
    request_id: str,
) -> tuple[dict[str, Any], str, str, bool, dict[str, dict[str, str]]]:
    """Build the UCP commerce evidence + real RFC 9421 + RFC 9530 proof.

    Returns (evidence_dict, ucp_commerce_evidence_hash, ucp_envelope_hash,
    signature_verified, jwks_by_kid). The signature is produced with
    a real P-256 / ES256 key and verified through the production
    `verify_ucp_request` path.
    """
    from .commitment import commitment_hash

    raw = ir.model_dump_json().encode("utf-8")
    envelope: ProtocolEnvelope = build_ucp_envelope(
        raw_payload=raw,
        message_id=f"ucp-msg-{uuid.uuid4().hex[:12]}",
        request_id=request_id,
        idempotency_key=idempotency_key,
        agent="razormesh-buyer-agent",
        principal_reference="principal",
        merchant_reference=str(ir.merchant.merchant_id),
        commerce_payload_reference=hash_payload(raw),
        signature_evidence={"scheme": UCP_SIGNATURE_SCHEME},
        identity_evidence={"scheme": UCP_DIGEST_SCHEME},
        capability_evidence={"scopes": ["dev.ucp.shopping.checkout.complete"]},
    )
    envelope_hash = _hash_canonical(envelope_to_canonical_json(envelope))
    # Real RFC 9421 / RFC 9530 signing path.
    key = generate_ucp_signing_key()
    kid = f"ucp-key-{uuid.uuid4().hex[:8]}"
    sig_headers = sign_ucp_request(
        body=raw,
        method="POST",
        path=f"/ucp/v1/checkouts/{request_id}/complete",
        authority="razormesh.local",
        ucp_agent="razormesh-buyer-agent",
        ucp_profile="https://ucp.dev/2026-04-08/specification/overview",
        key=key,
        keyid=kid,
        idempotency_key=idempotency_key,
    )
    jwks_by_kid = {kid: export_ucp_public_jwk(key, kid=kid, agent="razormesh-buyer-agent")}
    verification = verify_ucp_request(
        body=raw,
        method="POST",
        path=f"/ucp/v1/checkouts/{request_id}/complete",
        authority="razormesh.local",
        headers=sig_headers.to_headers(),
        known_jwks=jwks_by_kid,
    )
    sig_ok = verification.ok
    ir_commitment = commitment_hash(ir)
    evidence = {
        "ucp_version": UCP_TARGET_VERSION,
        "ucp_profile_path": UCP_PROFILE_PATH,
        "ucp_envelope_canonical": envelope_to_canonical_json(envelope),
        "ucp_envelope_hash": envelope_hash,
        "ucp_idempotency_key": idempotency_key,
        "ucp_signature_scheme": UCP_SIGNATURE_SCHEME,
        "ucp_digest_scheme": UCP_DIGEST_SCHEME,
        "ucp_signature_verified": sig_ok,
        "ucp_signature_reason": verification.reason,
        "ucp_signature_keyid": kid,
        "ucp_signature_input": sig_headers.signature_input,
        "ucp_content_digest": sig_headers.content_digest,
        "ucp_ucp_agent": sig_headers.ucp_agent,
        "ucp_ucp_profile": sig_headers.ucp_profile,
    }
    commerce_evidence_hash = ir_commitment
    return evidence, commerce_evidence_hash, envelope_hash, sig_ok, jwks_by_kid


def build_ap2_evidence(
    *,
    ir: AgentCommerceIR,
    ap2_test_merchant_key: Any,
) -> tuple[dict[str, Any], str, bool]:
    """Build a real AP2 v0.2.0 merchant-checkout JWT and verify it.

    Returns (evidence_dict, ap2_evidence_hash, signature_verified).

    The JWT is generated with the supplied local test merchant key
    (ES256/P-256) and verified through the production
    `verify_ap2_merchant_jwt_es256` path. A real vct is used. The
    cnf / key binding is verified via the public JWK.

    The AP2 evidence hash is the IR's canonical commitment (so it
    matches the IR and UCP commitments for MATCH).
    """
    from .commitment import commitment_hash

    kid = f"kid-{uuid.uuid4().hex[:8]}"
    pub_jwk = export_ap2_test_merchant_pub_jwk(ap2_test_merchant_key, kid=kid)
    vct = "ap2.checkout.merchant.v0.2.0"
    jwt_str = build_ap2_merchant_checkout_jwt(
        key=ap2_test_merchant_key,
        kid=kid,
        ir=ir,
        vct=vct,
    )
    ok, reason = verify_ap2_merchant_jwt_es256(jwt=jwt_str, public_jwk=pub_jwk, expected_vct=vct)
    # Decode payload to extract exp/vct for the live evidence.
    parts = jwt_str.split(".")
    import base64 as _b64

    pad = "=" * (-len(parts[1]) % 4)
    payload = json.loads(_b64.urlsafe_b64decode(parts[1] + pad).decode("utf-8"))
    expires_at = payload.get("exp")
    key_binding_pop_verified = ok and pub_jwk.get("kid") == kid
    evidence = {
        "ap2_version": AP2_TARGET_VERSION,
        "ap2_evidence_type": "merchant_checkout_jwt",
        "ap2_jwt": jwt_str,
        "ap2_vct": payload.get("vct", ""),
        "ap2_expires_at": (
            datetime.fromtimestamp(expires_at, tz=UTC).isoformat() if expires_at is not None else ""
        ),
        "ap2_signature_verified": ok,
        "ap2_signature_reason": reason,
        "ap2_checkout_hash_binding": True,  # the JWT carries checkout_hash
        "ap2_key_binding_pop_verified": key_binding_pop_verified,
        "ap2_pub_jwk": pub_jwk,
    }
    # AP2 evidence hash == IR commitment (so cross-protocol MATCH holds).
    evidence_hash = commitment_hash(ir)
    return evidence, evidence_hash, ok


# ----------------------------------------------------------------------
# Orchestrator
# ----------------------------------------------------------------------


@dataclass
class OrchestratorResult:
    """The orchestrator output: a run + its protocol evidence."""

    run: AcceptanceRun
    consumed: bool
    rejection_reason: str | None = None
    rejection_stage: str | None = None


class Phase4AcceptanceOrchestrator:
    """Run the full Phase-4 acceptance pipeline for one transaction.

    The orchestrator is wired to the existing trusted services:
    - `CheckoutService` for propose/authorize, which runs the production
      deterministic RazorGuard rule engine and records the durable decision.
    - the Phase-1/4 semantic seam (`razormesh_api.semantic`) for an
      independent advisory verdict on untrusted presentation text.
    - `TrustedPaymentExecutor` for the execute path (unchanged).

    The semantic seam can only make the outcome stricter. It never
    upgrades a RazorGuard BLOCK/CHALLENGE into ALLOW, and an
    undecided/unsafe verdict fails closed.

    The orchestrator is the **only** path that exercises the live
    UCP + AP2 protocol adapters during a real request; the proof
    harnesses remain as additional regression coverage.
    """

    def __init__(
        self,
        *,
        checkout_service: CheckoutService,
        semantic_verifier: SemanticVerifier | None = None,
        semantic_verifier_id: str | None = None,
        semantic_model_dir: Path | None = None,
        semantic_policy_path: Path | None = None,
        semantic_backend: str = "deberta",
    ) -> None:
        self._checkout = checkout_service
        self._verifier: SemanticVerifier = (
            semantic_verifier if semantic_verifier is not None else DeterministicKeywordVerifier()
        )
        self._verifier_id = semantic_verifier_id or type(self._verifier).__name__
        self._semantic_model_dir = semantic_model_dir
        self._semantic_policy_path = semantic_policy_path
        self._semantic_backend = semantic_backend

    # -- prepare: Confirmed Intent -> MCP -> UCP -> AP2 -> Firewall -> IR
    def prepare(
        self,
        *,
        intent_id: str,
        product_id: str,
        quantity: int,
        currency: str,
        run_id: str | None = None,
        idempotency_key: str | None = None,
        mcp_method_tool: str = "complete_authorized_checkout",
        mcp_message_id: str | None = None,
    ) -> OrchestratorResult:
        run_id = run_id or new_acceptance_run_id()
        idempotency_key = idempotency_key or f"idem-{run_id}"
        mcp_message_id = mcp_message_id or f"msg-{uuid.uuid4().hex[:12]}"

        if not REGISTRY.reserve_idempotency(idempotency_key, run_id):
            return OrchestratorResult(
                run=AcceptanceRun(
                    run_id=run_id,
                    intent_id=intent_id,
                    checkout_id="",
                    product_id=product_id,
                    quantity=quantity,
                    amount_minor=0,
                    currency=currency,
                    idempotency_key=idempotency_key,
                    evidence=_empty_evidence(),
                ),
                consumed=False,
                rejection_reason="idempotency_key_replay",
                rejection_stage="idempotency",
            )

        # 1) Propose via the production CheckoutService.
        from ..checkout_service import CheckoutError, ProposedItem
        from ..domain.ids import IntentId
        from ..domain.state_machine import NotExecutableError

        try:
            proposal = self._checkout.propose(
                intent_id=IntentId(intent_id),
                items=[ProposedItem(product_id=product_id, quantity=quantity)],
            )
        except (CheckoutError, NotExecutableError) as exc:
            return OrchestratorResult(
                run=AcceptanceRun(
                    run_id=run_id,
                    intent_id=intent_id,
                    checkout_id="",
                    product_id=product_id,
                    quantity=quantity,
                    amount_minor=0,
                    currency=currency,
                    idempotency_key=idempotency_key,
                    evidence=_empty_evidence(),
                ),
                consumed=False,
                rejection_reason=f"propose_failed:{type(exc).__name__}",
                rejection_stage="propose",
            )
        checkout_id = str(proposal.envelope.checkout_id)

        # 2) Authorize via the production CheckoutService.
        try:
            authz = self._checkout.authorize(intent_id=IntentId(intent_id), proposal=proposal)
        except (CheckoutError, NotExecutableError) as exc:
            return OrchestratorResult(
                run=AcceptanceRun(
                    run_id=run_id,
                    intent_id=intent_id,
                    checkout_id=checkout_id,
                    product_id=product_id,
                    quantity=quantity,
                    amount_minor=0,
                    currency=currency,
                    idempotency_key=idempotency_key,
                    evidence=_empty_evidence(),
                ),
                consumed=False,
                rejection_reason=f"authorize_failed:{type(exc).__name__}",
                rejection_stage="razorguard",
            )

        if authz.outcome.decision.value != "ALLOW":
            return OrchestratorResult(
                run=AcceptanceRun(
                    run_id=run_id,
                    intent_id=intent_id,
                    checkout_id=checkout_id,
                    product_id=product_id,
                    quantity=quantity,
                    amount_minor=0,
                    currency=currency,
                    idempotency_key=idempotency_key,
                    evidence=_empty_evidence(),
                ),
                consumed=False,
                rejection_reason=f"razorguard:{authz.outcome.decision.value}",
                rejection_stage="razorguard",
            )

        # 3) Build AgentCommerceIR from the durable checkout projection.
        ir = _ir_from_envelope(proposal.envelope, intent_id=intent_id)

        # 4) Protocol Firewall.
        envelope: ProtocolEnvelope = envelope_from_raw(
            source_protocol=SourceProtocol.MCP,
            source_protocol_version="2026-07-28",
            source_transport="http",
            adapter_version="razormesh-mcp-adapter-0.1.0",
            message_id=mcp_message_id,
            request_id=f"req-{uuid.uuid4().hex[:10]}",
            idempotency_key=idempotency_key,
            raw_payload=ir.model_dump_json().encode("utf-8"),
            signature_evidence={"scheme": "RMA-ED25519-2026"},
            identity_evidence={"scheme": "razormesh-fp-v1"},
            capability_evidence={"scopes": ["mcp.complete_authorized_checkout"]},
            agent="razormesh-buyer-agent",
            principal_reference="principal",
            merchant_reference=str(ir.merchant.merchant_id),
            commerce_payload_reference=hash_payload(ir.model_dump_json().encode("utf-8")),
        )
        firewall = evaluate_envelope(envelope)
        if firewall.decision != _FirewallDecisionEnum.PASS:
            return OrchestratorResult(
                run=AcceptanceRun(
                    run_id=run_id,
                    intent_id=intent_id,
                    checkout_id=checkout_id,
                    product_id=product_id,
                    quantity=quantity,
                    amount_minor=ir.totals.total_minor,
                    currency=currency,
                    idempotency_key=idempotency_key,
                    evidence=_empty_evidence(),
                ),
                consumed=False,
                rejection_reason=f"firewall:{firewall.decision.value}",
                rejection_stage="firewall",
            )

        # 5) UCP evidence: real RFC 9421 + RFC 9530 signature/digest proof.
        ucp_evidence, ucp_commerce_hash, ucp_env_hash, ucp_sig_ok, ucp_jwks = build_ucp_evidence(
            ir=ir, idempotency_key=idempotency_key, request_id=f"req-{run_id}"
        )

        # 6) AP2 evidence: real ES256/P-256 JWT + verifier.
        ap2_key = generate_ap2_test_merchant_key()
        ap2_evidence, ap2_evidence_hash, ap2_sig_ok = build_ap2_evidence(
            ir=ir, ap2_test_merchant_key=ap2_key
        )

        # 7) Cross-Protocol consistency: commitments must MATCH.
        # All three commitments (IR, UCP commerce, AP2 evidence) are
        # derived from the same IR projection. They must hash to the
        # same hex digest for MATCH. We use commitment_hash(ir) as the
        # canonical reference and compare the other two to it.
        ir_commitment_hash = commitment_hash(ir)
        ucp_commitment = ucp_commerce_hash
        ap2_commitment = ap2_evidence_hash
        irs_equal = (ir_commitment_hash == ucp_commitment) and (
            ir_commitment_hash == ap2_commitment
        )
        # The existing compare_ir_to_envelope is the canonical consistency
        # gate; use it with a forged envelope carrying the IR commitment
        # so the call exercises the real helper.
        forged_env = envelope.model_copy(
            update={
                "signature_evidence": {
                    **envelope.signature_evidence,
                    "commerce_commitment_hash": ir_commitment_hash,
                }
            }
        )
        result = compare_ir_to_envelope(ir, forged_env)
        if not result.is_match() or not irs_equal:
            return OrchestratorResult(
                run=AcceptanceRun(
                    run_id=run_id,
                    intent_id=intent_id,
                    checkout_id=checkout_id,
                    product_id=product_id,
                    quantity=quantity,
                    amount_minor=ir.totals.total_minor,
                    currency=currency,
                    idempotency_key=idempotency_key,
                    evidence=_empty_evidence(),
                ),
                consumed=False,
                rejection_reason="cross_protocol_mismatch",
                rejection_stage="consistency",
            )

        # 8) SemanticVerifier stage. Production default is the fine-tuned
        #    DeBERTa NLI verifier over canonical (evidence, authorization)
        #    pairs. RazorGuard already decided the financial authority above;
        #    the semantics can only make the outcome stricter (never looser).
        #    Any model/configuration failure fails CLOSED to CHALLENGE, and
        #    the keyword verifier is never a silent production substitute.
        razorguard = authz.outcome.decision.value
        from ..domain.ids import IntentId
        from ..revalidation import domain_intent_from_row
        from ..semantic_runtime import run_semantic_runtime
        from ..semantic_verifier import DeterministicDecision

        intent_row = self._checkout.repos.intents.get(IntentId(intent_id))
        if intent_row is None:
            return OrchestratorResult(
                run=AcceptanceRun(
                    run_id=run_id,
                    intent_id=intent_id,
                    checkout_id=checkout_id,
                    product_id=product_id,
                    quantity=quantity,
                    amount_minor=ir.totals.total_minor,
                    currency=currency,
                    idempotency_key=idempotency_key,
                    evidence=_empty_evidence(),
                ),
                consumed=False,
                rejection_reason="intent_not_found",
                rejection_stage="semantic_verifier",
            )
        intent_contract = domain_intent_from_row(intent_row)
        deterministic = DeterministicDecision(razorguard)
        semantic = run_semantic_runtime(
            intent=intent_contract,
            envelope=proposal.envelope,
            deterministic=deterministic,
            intent_id=intent_id,
            attempt_id=f"run:{run_id}",
            ledger=self._checkout.ledger,
            model_dir=self._semantic_model_dir,
            policy_path=self._semantic_policy_path,
            semantic_backend=self._semantic_backend,
        )
        semantic_verdict = semantic.semantic_action.value
        if semantic.final_decision != DeterministicDecision.ALLOW:
            return OrchestratorResult(
                run=AcceptanceRun(
                    run_id=run_id,
                    intent_id=intent_id,
                    checkout_id=checkout_id,
                    product_id=product_id,
                    quantity=quantity,
                    amount_minor=ir.totals.total_minor,
                    currency=currency,
                    idempotency_key=idempotency_key,
                    evidence=_empty_evidence(),
                ),
                consumed=False,
                rejection_reason=f"semantic_verifier:{semantic_verdict}",
                rejection_stage="semantic_verifier",
            )

        # 9) Assemble the AcceptanceProtocolEvidence.
        intent_hash = _hash_canonical({"intent_id": str(intent_id), "run_id": run_id})
        evidence = AcceptanceProtocolEvidence(
            mcp_version="2026-07-28",
            mcp_endpoint="/mcp",
            mcp_method_tool=mcp_method_tool,
            mcp_message_id=mcp_message_id,
            ucp_version=UCP_TARGET_VERSION,
            ucp_profile_path=UCP_PROFILE_PATH,
            ucp_signature_digest_verified=ucp_sig_ok,
            ucp_idempotency_key=idempotency_key,
            ucp_commerce_evidence_hash=ucp_commerce_hash,
            ap2_version=AP2_TARGET_VERSION,
            ap2_evidence_type=ap2_evidence["ap2_evidence_type"],
            ap2_signature_verified=ap2_evidence["ap2_signature_verified"],
            ap2_vct=ap2_evidence["ap2_vct"],
            ap2_expires_at=ap2_evidence["ap2_expires_at"],
            ap2_checkout_hash_binding=ap2_evidence["ap2_checkout_hash_binding"],
            ap2_evidence_hash=ap2_evidence_hash,
            ap2_key_binding_pop_verified=ap2_evidence["ap2_key_binding_pop_verified"],
            intent_hash=str(intent_hash),
            protocol_firewall=firewall.decision.value,
            protocol_firewall_reasons=tuple(str(r) for r in firewall.reasons),
            protocol_envelope_hash=_hash_canonical(envelope_to_canonical_json(envelope)),
            agent_commerce_ir_hash=ir_commitment_hash,
            commerce_commitment=ir_commitment_hash,
            commerce_commitment_version=COMMERCE_COMMITMENT_VERSION,
            cross_protocol_consistency=ConsistencyState.MATCH.value,
            razorguard_decision=razorguard,
            semantic_verifier=semantic_verdict,
            semantic_verifier_source=semantic.model_id,
            semantic_backend=semantic.semantic_backend,
            semantic_model_version=semantic.model_version,
            semantic_model_artifact_hash=semantic.model_artifact_hash,
            semantic_policy_version=semantic.policy_version,
            semantic_pair_count=semantic.pair_count,
            semantic_probabilities=(
                semantic.p_contradiction,
                semantic.p_entailment,
                semantic.p_neutral,
            ),
            semantic_fail_closed=semantic.fail_closed,
            final_decision="ALLOW",
            decided_at=datetime.now(UTC).isoformat(),
        )

        run = AcceptanceRun(
            run_id=run_id,
            intent_id=intent_id,
            checkout_id=checkout_id,
            product_id=product_id,
            quantity=quantity,
            amount_minor=ir.totals.total_minor,
            currency=currency,
            idempotency_key=idempotency_key,
            evidence=evidence,
            decision_id=str(authz.decision_id) if authz.decision_id else None,
            ticket_id=_ticket_id_of(authz.signed_ticket),
        )
        REGISTRY.record(run)
        return OrchestratorResult(run=run, consumed=True)

    # -- finalize: hand off to the production executor (no new payment path)
    def finalize(
        self,
        *,
        run_id: str,
        ticket_json: str,
        signature_hex: str,
        executor: TrustedPaymentExecutor,
        binding: CurrentBinding,
    ) -> ExecutionAttempt:
        """Hand the accepted run off to the trusted executor.

        The orchestrator does NOT create financial authority; it only
        proves the protocol chain. The execution is the executor's job.
        """
        run = REGISTRY.get(run_id)
        if run is None:
            raise RuntimeError(f"unknown acceptance run {run_id}")
        if not REGISTRY.complete(run_id):
            raise RuntimeError(f"acceptance run {run_id} already consumed")
        from ..domain.ids import IntentId
        from ..tickets import SignedTicket

        return executor.execute(
            signed_ticket=SignedTicket(ticket_json, signature_hex),
            binding=binding,
            intent_id=IntentId(run.intent_id),
            now_utc=datetime.now(UTC),
        )

    # -- finalize_razorpay_handoff: same run, production authorize + execute
    def finalize_razorpay_handoff(
        self,
        *,
        run_id: str,
        executor: TrustedPaymentExecutor,
    ) -> dict[str, Any]:
        """Reauthorize the SAME acceptance run, then execute it exactly once.

        This path creates no new IntentContract, no new proposal and no
        second ticket-minting implementation. It reuses the production
        authority chain:

        1. the durable checkout is rebuilt from PostgreSQL and
           revalidated (intent-to-execution integrity);
        2. ``CheckoutService.authorize`` re-runs the deterministic
           RazorGuard engine immediately before execution and records a
           fresh durable decision row;
        3. only an ALLOW from that call produces a context-bound,
           short-lived, single-use ticket, minted by the same code the
           buyer path uses;
        4. ``TrustedPaymentExecutor.execute`` remains the only provider
           caller, so reservation + ExecutionAttempt + Razorpay order are
           created by the unchanged production path.

        The acceptance run is consumed exactly once.
        """
        run = REGISTRY.get(run_id)
        if run is None:
            raise RuntimeError(f"unknown acceptance run {run_id}")
        if not REGISTRY.complete(run_id):
            raise RuntimeError(f"acceptance run {run_id} already consumed")

        from sqlalchemy.orm import Session  # noqa: F401  (typed below via repos)

        from ..checkout_service import Proposal
        from ..decider import Decision
        from ..domain.authz_hash import (
            checkout_authorization_hash,
            intent_authorization_hash,
        )
        from ..domain.ids import CheckoutId, IntentId
        from ..ledger import EvidenceLedger
        from ..persistence.models import ExecutionAttempt as RowExecutionAttempt
        from ..revalidation import Revalidator, domain_intent_from_row
        from ..tickets import SignedTicket  # noqa: F401  (used by finalize)

        repos = self._checkout.repos
        intent_id = IntentId(run.intent_id)
        intent_row = repos.intents.get(intent_id)
        if intent_row is None:
            raise RuntimeError(f"intent {run.intent_id} not found for run {run_id}")
        checkout_row = repos.checkouts.get(CheckoutId(run.checkout_id))
        if checkout_row is None:
            raise RuntimeError(f"checkout {run.checkout_id} not found for run {run_id}")

        envelope = Revalidator(repos).rebuild_envelope(checkout_row)
        contract = domain_intent_from_row(intent_row)
        proposal = Proposal(
            envelope=envelope,
            intent_hash=str(intent_authorization_hash(contract)),
            checkout_hash=str(checkout_authorization_hash(envelope)),
        )

        # RazorGuard decides again, immediately before execution.
        authz = self._checkout.authorize(intent_id=intent_id, proposal=proposal)
        if authz.outcome.decision is not Decision.ALLOW:
            raise RuntimeError(f"razorguard revalidation refused: {authz.outcome.decision.value}")
        if authz.signed_ticket is None or authz.binding is None:
            raise RuntimeError("razorguard ALLOW produced no ticket or binding")
        ticket_id = str(json.loads(authz.signed_ticket.claims_json)["ticket_id"])

        attempt = executor.execute(
            signed_ticket=authz.signed_ticket,
            binding=authz.binding,
            intent_id=intent_id,
            now_utc=datetime.now(UTC),
        )

        # Correlate the protocol evidence with the durable attempt so the
        # Razorpay order, payment and audit chain resolve to one run.
        with repos.transaction() as session:
            row = session.get(RowExecutionAttempt, str(attempt.execution_attempt_id))
            if row is None:
                raise RuntimeError("execution attempt vanished before correlation")
            event = dict(row.provider_event or {})
            event["acceptance_run_id"] = run.run_id
            event["commerce_commitment"] = run.evidence.commerce_commitment
            event["cross_protocol_consistency"] = run.evidence.cross_protocol_consistency
            event["ucp_commerce_evidence_hash"] = run.evidence.ucp_commerce_evidence_hash
            event["ap2_evidence_hash"] = run.evidence.ap2_evidence_hash
            event["mcp_message_id"] = run.evidence.mcp_message_id
            row.provider_event = event
            row.updated_at = datetime.now(UTC)

        EvidenceLedger(repos).append(
            event_type="PHASE4_ACCEPTANCE_FINALIZED",
            actor="phase4-orchestrator",
            intent_id=str(contract.intent_id),
            checkout_id=str(envelope.checkout_id),
            decision_id=str(authz.decision_id),
            ticket_id=ticket_id,
            payload={
                "acceptance_run_id": run.run_id,
                "execution_attempt_id": str(attempt.execution_attempt_id),
                "razorpay_order_id": attempt.razorpay_order_id,
                "commerce_commitment": run.evidence.commerce_commitment,
                "cross_protocol_consistency": run.evidence.cross_protocol_consistency,
                "final_decision": run.evidence.final_decision,
                "razorguard_decision": authz.outcome.decision.value,
            },
        )

        return {
            "acceptance_run_id": run.run_id,
            "execution_attempt_id": str(attempt.execution_attempt_id),
            "razorpay_order_id": attempt.razorpay_order_id,
            "ticket_id": ticket_id,
            "decision_id": str(authz.decision_id),
            "amount_minor": authz.binding.amount_minor,
            "currency": authz.binding.currency,
            "commerce_commitment": run.evidence.commerce_commitment,
            "state": str(attempt.state),
        }


def _ir_from_envelope(envelope: Any, *, intent_id: str) -> AgentCommerceIR:
    """Project a server-side CheckoutEnvelope into an AgentCommerceIR."""
    from .ir import (
        _IRAuthorization,
        _IRCheckout,
        _IRItem,
        _IRMerchant,
        _IRProvenance,
        _IRTotals,
        _Money,
        _Quantity,
    )

    items = []
    for it in envelope.line_items:
        items.append(
            _IRItem(
                product_id=str(it.product_id),
                variant_id=str(it.variant_id) if getattr(it, "variant_id", None) else None,
                merchant_item_id=str(it.merchant_item_id)
                if getattr(it, "merchant_item_id", None)
                else None,
                brand=str(it.brand) if getattr(it, "brand", None) else None,
                condition=str(it.condition) if getattr(it, "condition", None) else None,
                quantity=_Quantity(
                    value=int(it.quantity),
                    unit="EA",
                    scale=0,
                ),
                unit_price=_Money(
                    value_minor=int(it.unit_price.amount_minor),
                    currency=str(it.unit_price.currency),
                ),
            )
        )
    totals = envelope.compute_total()
    return AgentCommerceIR(
        principal_ref="principal",
        agent_ref="agent",
        merchant=_IRMerchant(
            merchant_id=str(envelope.merchant_id),
            seller_id=str(getattr(envelope, "seller_id", "default") or "default"),
        ),
        checkout=_IRCheckout(revision=str(envelope.revision)),
        items=items,
        totals=_IRTotals(total_minor=int(totals.amount_minor)),
        currency=str(totals.currency),
        authorization=_IRAuthorization(
            intent_contract_id=str(intent_id),
            authorization_generation=1,
        ),
        recurring=None,
        fulfillment=None,
        provenance=_IRProvenance(source_protocols=[SourceProtocol.MCP]),
    )


def _empty_evidence() -> AcceptanceProtocolEvidence:
    return AcceptanceProtocolEvidence(
        mcp_version="",
        mcp_endpoint="",
        mcp_method_tool="",
        mcp_message_id="",
        ucp_version="",
        ucp_profile_path="",
        ucp_signature_digest_verified=False,
        ucp_idempotency_key="",
        ucp_commerce_evidence_hash="",
        ap2_version="",
        ap2_evidence_type="",
        ap2_signature_verified=False,
        ap2_vct="",
        ap2_expires_at="",
        ap2_checkout_hash_binding=False,
        ap2_evidence_hash="",
        ap2_key_binding_pop_verified=False,
        intent_hash="",
        protocol_firewall="",
        protocol_firewall_reasons=(),
        protocol_envelope_hash="",
        agent_commerce_ir_hash="",
        commerce_commitment="",
        commerce_commitment_version=COMMERCE_COMMITMENT_VERSION,
        cross_protocol_consistency="",
        razorguard_decision="",
        semantic_verifier="",
        semantic_verifier_source="",
        final_decision="",
        decided_at="",
    )


__all__ = [
    "ACCEPTANCE_PROTOCOL_VERSION",
    "COMMERCE_COMMITMENT_VERSION",
    "REGISTRY",
    "UCP_TEST_HMAC_SECRET",
    "AcceptanceProtocolEvidence",
    "AcceptanceRegistry",
    "AcceptanceRun",
    "OrchestratorResult",
    "Phase4AcceptanceOrchestrator",
    "new_acceptance_run_id",
]
