"""Phase-5 (M036-M043): Merchant Sandbox API.

- GET  /merchant-sandbox/presets       → bounded attack-preset inputs
- POST /merchant-sandbox/checkout      → create a real fixture intent + checkout for a product
- POST /merchant-sandbox/mutate        → apply a bounded mutation to the checkout row
- POST /merchant-sandbox/revert        → restore truth, preserving audit history
- GET  /merchant-sandbox/diff/{cid}    → before/after diff (authorized vs current)

The demo API mutates only the durable CHECKOUT row (post-authorization drift
surface) — never the confirmed mandate, never provider state.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from razormesh_api.ledger import EvidenceLedger
from razormesh_api.merchant_sandbox import (
    MerchantDemoError,
    MutationKind,
    apply_mutation,
    list_presets,
    offer_diff,
    propose_checkout_for_demo,
)
from razormesh_api.persistence.db import create_db_engine, create_session_factory
from razormesh_api.persistence.repositories import Repositories
from razormesh_api.settings import Settings, get_settings

router = APIRouter(prefix="/merchant-sandbox", tags=["phase5-merchant"])

CHECKOUT_RE = r"^chk_[0-9A-HJKMNP-TV-Z]{26}$"
INTENT_RE = r"^intent_[0-9A-HJKMNP-TV-Z]{26}$"


def _repos(
    settings: Annotated[Settings, Depends(get_settings)],
) -> Repositories:
    return Repositories(create_session_factory(create_db_engine(settings.database_url)))


def _ledger(repos: Annotated[Repositories, Depends(_repos)]) -> EvidenceLedger:
    return EvidenceLedger(repos)


def _err(exc: MerchantDemoError) -> HTTPException:
    status = {
        "INTENT_NOT_FOUND": 404,
        "CHECKOUT_NOT_FOUND": 404,
        "BASELINE_MISSING": 409,
        "MUTATION_OUT_OF_BOUNDS": 422,
        "NO_OTHER_MERCHANT": 409,
        "PRODUCT_GONE": 409,
    }.get(exc.code, 400)
    return HTTPException(status_code=status, detail={"code": exc.code, "detail": exc.detail})


class CheckoutRequest(BaseModel):
    product_id: str = Field(min_length=6, max_length=64)
    quantity: int = Field(default=1, ge=1, le=2)
    # G015: when the caller is working within an existing mission, pass its
    # intent id so the sandbox mutation targets THAT transaction instead of
    # silently creating a disconnected one. Explicit new mission = omit it.
    intent_id: str | None = Field(default=None, pattern=INTENT_RE)


@router.get("/presets")
def presets() -> dict[str, Any]:
    return {"presets": list_presets()}


@router.post("/checkout")
def create_checkout(
    body: CheckoutRequest,
    repos: Annotated[Repositories, Depends(_repos)],
) -> dict[str, Any]:
    from razormesh_api.persistence.models import IntentContract, Product

    with session_scope_safe(repos) as session:
        product = session.get(Product, body.product_id)
        if product is None:
            raise HTTPException(status_code=404, detail="Unknown product")
        title = product.title
        price_minor = product.price_minor
        shipping_minor = product.shipping_minor
        condition = product.condition
    # G015: reuse the CURRENT mission's intent when the caller passes it
    # (the frontend forwards the global live trace's intent) — the mutation
    # surface then targets the live mission's own checkout, keeping one
    # trace across Buyer/Merchant/Protocols/Security/Audit.
    if body.intent_id:
        with session_scope_safe(repos) as session:
            intent = session.get(IntentContract, body.intent_id)
        if intent is None:
            raise HTTPException(status_code=404, detail="Unknown intent")
        # A fresh checkout for the CURRENT mission intent (new revision of
        # the same transaction, not a disconnected trace).
        try:
            intent_id, checkout_id, _expected = propose_checkout_for_demo(
                repos,
                product_id=body.product_id,
                quantity=body.quantity,
                intent_id=body.intent_id,
            )
        except Exception as exc:
            raise HTTPException(status_code=422, detail=str(exc)[:200]) from exc
    else:
        try:
            intent_id, checkout_id, _expected = propose_checkout_for_demo(
                repos, product_id=body.product_id, quantity=body.quantity
            )
        except Exception as exc:
            raise HTTPException(status_code=422, detail=str(exc)[:200]) from exc
    # Resolve the trace this checkout belongs to (G015: response carries it).
    from razormesh_api.trace_registry import TraceRegistry

    trace = TraceRegistry(repos).by_intent(intent_id)
    return {
        "intent_id": intent_id,
        "checkout_id": checkout_id,
        "trace_id": trace.trace_id if trace else "",
        "product": {
            "product_id": body.product_id,
            "title": title,
            "price_minor": price_minor,
            "shipping_minor": shipping_minor,
            "condition": condition,
        },
        "note": (
            "Checkout bound to the current mission trace."
            if body.intent_id
            else "New sandbox mission (fresh intent and trace)."
        ),
    }


class MutateRequest(BaseModel):
    intent_id: str = Field(pattern=INTENT_RE)
    checkout_id: str = Field(pattern=CHECKOUT_RE)
    kind: str = Field(min_length=4, max_length=32)


def session_scope_safe(repos: Repositories):  # type: ignore[no-untyped-def]
    from razormesh_api.persistence.repositories import session_scope

    return session_scope(repos.factory)


@router.post("/mutate")
def mutate(
    body: MutateRequest,
    repos: Annotated[Repositories, Depends(_repos)],
    ledger: Annotated[EvidenceLedger, Depends(_ledger)],
) -> dict[str, Any]:
    try:
        kind = MutationKind(body.kind)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"unknown mutation kind {body.kind}") from exc
    try:
        result = apply_mutation(
            repos,
            ledger,
            intent_id=body.intent_id,
            checkout_id=body.checkout_id,
            kind=kind,
        )
    except MerchantDemoError as exc:
        raise _err(exc) from exc
    return result.__dict__


@router.post("/revert")
def revert(
    body: MutateRequest,
    repos: Annotated[Repositories, Depends(_repos)],
    ledger: Annotated[EvidenceLedger, Depends(_ledger)],
) -> dict[str, Any]:
    body_kind = body.model_copy(update={"kind": "revert"})
    try:
        result = apply_mutation(
            repos,
            ledger,
            intent_id=body_kind.intent_id,
            checkout_id=body_kind.checkout_id,
            kind=MutationKind.REVERT,
        )
    except MerchantDemoError as exc:
        raise _err(exc) from exc
    return result.__dict__


@router.get("/diff/{checkout_id}")
def diff(
    checkout_id: str,
    repos: Annotated[Repositories, Depends(_repos)],
) -> dict[str, Any]:
    import re

    if not re.fullmatch(CHECKOUT_RE, checkout_id):
        raise HTTPException(status_code=404, detail="Unknown checkout")
    try:
        return offer_diff(repos, checkout_id)
    except MerchantDemoError as exc:
        raise _err(exc) from exc
