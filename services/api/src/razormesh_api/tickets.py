"""M34: context-bound, single-use execution tickets.

A ticket is a signed claim set binding EVERY authorization-relevant dimension:

principal, agent, intent (+hash), authorization generation, checkout
(authorization-relevant hash + revision), merchant, amount, currency,
decision id, policy version, nonce, validity window.

Verification is fail-closed and ordered:
1. signature over the canonical (JCS) claim form  -> tamper-proof
2. expiry against the trusted clock               -> stale tickets die
3. every binding compared to CURRENT authority    -> drift/stale/split die

Any failure raises ``TicketRejected`` with a machine-readable code. Only a
fully verified ticket may reach the trusted executor (and its single-use
consumption is enforced later by Redis nonce claim, M35).
"""

from dataclasses import dataclass
from datetime import UTC, datetime

import rfc8785
from pydantic import BaseModel, ConfigDict, Field

from razormesh_api.domain.ids import (
    CheckoutId,
    DecisionId,
    ExecutionTicketId,
    IntentId,
)
from razormesh_api.keys import DevKeyPair


class TicketError(Exception):
    pass


class TicketRejected(TicketError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"[{code}] {detail}")
        self.code = code
        self.detail = detail


class ExecutionTicketClaims(BaseModel):
    """Every field that must remain true at execution time."""

    model_config = ConfigDict(frozen=True)

    ticket_id: ExecutionTicketId
    decision_id: DecisionId
    checkout_id: CheckoutId
    intent_id: IntentId

    principal_id: str = Field(min_length=3, max_length=64)
    agent_id: str = Field(min_length=3, max_length=64)

    authorization_generation: int = Field(ge=1)
    intent_hash: str = Field(min_length=16, max_length=128)
    checkout_hash: str = Field(min_length=16, max_length=128)
    checkout_revision: int = Field(ge=1)

    merchant_id: str = Field(min_length=3, max_length=64)
    amount_minor: int = Field(gt=0)
    currency: str = Field(min_length=3, max_length=8)

    policy_version: str = Field(min_length=3, max_length=64)
    nonce: str = Field(min_length=16, max_length=128)

    issued_at: datetime
    expires_at: datetime

    def model_validate_consistency(self) -> None:
        if self.expires_at <= self.issued_at:
            raise ValueError("ticket expires_at must be after issued_at")


@dataclass(frozen=True)
class SignedTicket:
    claims_json: str  # canonical transport form
    signature_hex: str


@dataclass(frozen=True)
class CurrentBinding:
    """The CURRENT authoritative values, re-read immediately before execution."""

    principal_id: str
    agent_id: str
    intent_id: str
    intent_hash: str
    authorization_generation: int
    checkout_id: str
    checkout_hash: str
    checkout_revision: int
    merchant_id: str
    amount_minor: int
    currency: str


_TICKET_SCHEMA = "razormesh.ticket.v1"

_BINDINGS: tuple[tuple[str, str], ...] = (
    ("principal_id", "PRINCIPAL_MISMATCH"),
    ("agent_id", "AGENT_MISMATCH"),
    ("intent_id", "INTENT_MISMATCH"),
    ("intent_hash", "AUTHORIZATION_SUPERSEDED"),
    ("authorization_generation", "AUTHORIZATION_SUPERSEDED"),
    ("checkout_id", "CHECKOUT_MISMATCH"),
    ("checkout_hash", "CHECKOUT_CHANGED"),
    ("checkout_revision", "CHECKOUT_CHANGED"),
    ("merchant_id", "MERCHANT_MISMATCH"),
    ("amount_minor", "AMOUNT_MISMATCH"),
    ("currency", "CURRENCY_MISMATCH"),
)


def _canonical_bytes(claims: ExecutionTicketClaims) -> bytes:
    envelope = {"schema": _TICKET_SCHEMA, **claims.model_dump(mode="json")}
    return rfc8785.dumps(envelope)


class TicketIssuer:
    """Signs new tickets with the local dev key (trusted control plane only)."""

    def __init__(self, keys: DevKeyPair) -> None:
        self._keys = keys

    def issue(self, claims: ExecutionTicketClaims) -> SignedTicket:
        claims.model_validate_consistency()
        payload = _canonical_bytes(claims)
        return SignedTicket(
            claims_json=payload.decode("utf-8"), signature_hex=self._keys.sign(payload).hex()
        )


class TicketVerifier:
    """Fail-closed verification against the CURRENT authoritative context."""

    def __init__(self, keys: DevKeyPair, now_utc: datetime | None = None) -> None:
        self._keys = keys
        self._now = now_utc or datetime.now(UTC)

    def verify(self, signed: SignedTicket, binding: CurrentBinding) -> ExecutionTicketClaims:
        # 1. Signature: proves the ticket came from us and was not altered.
        try:
            payload = signed.claims_json.encode("utf-8")
            if not self._keys.verify(payload, bytes.fromhex(signed.signature_hex)):
                raise TicketRejected("SIGNATURE_INVALID", "signature does not match payload")
        except TicketRejected:
            raise
        except Exception as exc:
            raise TicketRejected("MALFORMED_TICKET", f"cannot parse ticket: {exc}") from exc

        try:
            import json

            raw = json.loads(signed.claims_json)
            raw.pop("schema", None)
            claims = ExecutionTicketClaims.model_validate(raw)
        except Exception as exc:
            raise TicketRejected("MALFORMED_TICKET", f"invalid claims: {exc}") from exc

        # 2. Expiry.
        if self._now >= claims.expires_at:
            raise TicketRejected(
                "TICKET_EXPIRED",
                f"expired at {claims.expires_at.isoformat()} (now {self._now.isoformat()})",
            )

        # 3. Every binding must match CURRENT authority.
        current = {
            "principal_id": binding.principal_id,
            "agent_id": binding.agent_id,
            "intent_id": binding.intent_id,
            "intent_hash": binding.intent_hash,
            "authorization_generation": binding.authorization_generation,
            "checkout_id": binding.checkout_id,
            "checkout_hash": binding.checkout_hash,
            "checkout_revision": binding.checkout_revision,
            "merchant_id": binding.merchant_id,
            "amount_minor": binding.amount_minor,
            "currency": binding.currency,
        }
        for field_name, code in _BINDINGS:
            claimed = getattr(claims, field_name)
            # Normalize: typed ID objects must equal their string authority value.
            if str(claimed) != str(current[field_name]):
                raise TicketRejected(
                    code,
                    f"ticket {field_name}={claimed!r} does not match current "
                    f"authority {current[field_name]!r}",
                )

        return claims
