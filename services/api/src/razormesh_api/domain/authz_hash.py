"""M26: canonical authorization hashing (JCS / RFC 8785 compatible).

Only the DOCUMENTED authorization-relevant projection of a checkout or an
intent contract is hashed:

Checkout projection (authorization-relevant):
    checkout_id, revision, merchant_id, line items (product, quantity,
    unit price, condition), tax, shipping, fees, server-computed total,
    subscription recurring flag/frequency.

Deliberately EXCLUDED (must never influence authorization):
    - untrusted merchant text (display names, descriptions),
    - observation timestamps and other presentation metadata,
    - client-provided total (already validated == computed).

Intent projection: identity, authority bounds, budget caps, expiry and the
human confirmation moment. Lifecycle status is excluded (tracked separately).

Serialization is JCS (RFC 8785): deterministic key ordering, number and string
escaping, so hashes are reproducible across languages and runtimes.
"""

import hashlib
from datetime import UTC
from typing import Any

import rfc8785

from razormesh_api.domain.checkout import CheckoutEnvelope
from razormesh_api.domain.intent import IntentContract

HASH_SCHEMA_VERSION = "razormesh.authz-hash.v1"


def jcs_bytes(value: Any) -> bytes:
    """RFC 8785 (JCS) canonical JSON serialization."""
    return rfc8785.dumps(value)


def jcs_sha256(value: Any) -> str:
    """Deterministic SHA-256 hex digest over the JCS form of ``value``."""
    digest = hashlib.sha256()
    digest.update(jcs_bytes(HASH_SCHEMA_VERSION))
    digest.update(b"\n")
    digest.update(jcs_bytes(value))
    return digest.hexdigest()


def _money_view(money: Any) -> dict[str, Any]:
    # Money exposes integer minor units only (no floats ever reach the hash).
    return {"amount_minor": money.amount_minor, "currency": money.currency}


def checkout_authorization_projection(envelope: CheckoutEnvelope) -> dict[str, Any]:
    """The documented authorization-relevant subset of a checkout."""
    return {
        "kind": "checkout",
        "checkout_id": envelope.checkout_id.value,
        "revision": envelope.revision,
        "merchant_id": envelope.merchant_id.value,
        "line_items": [
            {
                "product_id": item.product_id.value,
                "quantity": item.quantity,
                "unit_price": _money_view(item.unit_price),
                "condition": item.condition,
            }
            for item in envelope.line_items
        ],
        "tax": _money_view(envelope.tax),
        "shipping": _money_view(envelope.shipping),
        "fees": _money_view(envelope.fees),
        "computed_total": _money_view(envelope.compute_total()),
        "subscription_terms": (
            None
            if envelope.subscription_terms is None
            else {
                "recurring": envelope.subscription_terms.recurring,
                "frequency": envelope.subscription_terms.frequency,
            }
        ),
    }


def intent_authorization_projection(contract: IntentContract) -> dict[str, Any]:
    """The documented authorization-relevant subset of an intent contract."""
    return {
        "kind": "intent",
        "intent_id": contract.intent_id.value,
        "principal_id": contract.principal_id.value,
        "agent_id": contract.agent_id.value,
        "authorization_generation": contract.authorization_generation,
        "allowed_merchant_ids": (
            None
            if contract.allowed_merchant_ids is None
            else sorted(m.value for m in contract.allowed_merchant_ids)
        ),
        "allowed_product_ids": (
            None
            if contract.allowed_product_ids is None
            else sorted(p.value for p in contract.allowed_product_ids)
        ),
        "allowed_categories": (
            None if contract.allowed_categories is None else sorted(contract.allowed_categories)
        ),
        "brand_restriction": (
            None
            if contract.brand_restriction is None
            else {
                "brands": sorted(contract.brand_restriction.brands),
                "mode": contract.brand_restriction.mode,
            }
        ),
        "condition_restriction": (
            None
            if contract.condition_restriction is None
            else {"allowed_conditions": sorted(contract.condition_restriction.allowed_conditions)}
        ),
        "currency": contract.currency,
        "max_total": _money_view(contract.max_total),
        "aggregate_budget": _money_view(contract.aggregate_budget),
        "max_quantity": contract.max_quantity,
        "recurring_allowed": contract.recurring_allowed,
        "approval_threshold": _money_view(contract.approval_threshold),
        "authorized_at": contract.authorized_at.astimezone(UTC).isoformat(),
        "expires_at": contract.expires_at.astimezone(UTC).isoformat(),
    }


def checkout_authorization_hash(envelope: CheckoutEnvelope) -> str:
    return jcs_sha256(checkout_authorization_projection(envelope))


def intent_authorization_hash(contract: IntentContract) -> str:
    return jcs_sha256(intent_authorization_projection(contract))
