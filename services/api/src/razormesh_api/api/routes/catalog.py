"""M23: bounded read-only catalog API with validation and pagination."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from razormesh_api.domain.ids import ProductId
from razormesh_api.persistence.repositories import Repositories
from razormesh_api.settings import Settings, get_settings

router = APIRouter(prefix="/catalog", tags=["catalog"])

MAX_PAGE_SIZE = 100


def _get_repositories(
    settings: Annotated[Settings, Depends(get_settings)],
) -> Repositories:
    from razormesh_api.persistence.db import create_db_engine, create_session_factory

    engine = create_db_engine(settings.database_url)
    return Repositories(create_session_factory(engine))


class MerchantOut(BaseModel):
    id: str
    name: str
    display_name: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime


class ProductOut(BaseModel):
    id: str
    merchant_id: str
    title: str
    description: str
    brand: str | None = None
    category: str
    condition: str
    price_minor: int
    currency: str
    shipping_minor: int
    tax_minor: int
    fees_minor: int
    recurring: bool
    recurring_frequency: str | None = None
    image_url: str | None = None
    created_at: datetime
    updated_at: datetime


class MerchantPage(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[MerchantOut]


class ProductPage(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[ProductOut]


LimitQ = Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)]
OffsetQ = Annotated[int, Query(ge=0)]
CategoryQ = Annotated[str | None, Query(min_length=1, max_length=100)]
BrandQ = Annotated[str | None, Query(min_length=1, max_length=100)]


@router.get("/merchants", response_model=MerchantPage)
def list_merchants(
    repos: Annotated[Repositories, Depends(_get_repositories)],
    limit: LimitQ = 20,
    offset: OffsetQ = 0,
) -> MerchantPage:
    merchants = repos.merchants.list(limit=limit, offset=offset)
    items = [MerchantOut.model_validate(m, from_attributes=True) for m in merchants]
    return MerchantPage(total=repos.merchants.count(), limit=limit, offset=offset, items=items)


@router.get("/products", response_model=ProductPage)
def list_products(
    repos: Annotated[Repositories, Depends(_get_repositories)],
    limit: LimitQ = 20,
    offset: OffsetQ = 0,
    category: CategoryQ = None,
    brand: BrandQ = None,
) -> ProductPage:
    products = repos.products.list(category=category, brand=brand, limit=limit, offset=offset)
    items = [ProductOut.model_validate(p, from_attributes=True) for p in products]
    total = repos.products.count(category=category, brand=brand)
    return ProductPage(total=total, limit=limit, offset=offset, items=items)


@router.get("/products/{product_id}", response_model=ProductOut)
def get_product(
    product_id: ProductId,
    repos: Annotated[Repositories, Depends(_get_repositories)],
) -> ProductOut:
    product = repos.products.get(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="product not found")
    return ProductOut.model_validate(product, from_attributes=True)
