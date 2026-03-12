from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Product, Variant
from app.repositories.factories import SqlAlchemyRepositoryFactory
from app.schemas import ProductCreate, ProductOut
from app.utils import api_error, product_to_dict, require_role

router = APIRouter(prefix="/api/v1/products", tags=["products"])


@router.post("", response_model=ProductOut, status_code=201)
def create_product(
    payload: ProductCreate,
    x_role: Optional[str] = Header(default=None, alias="X-Role"),
    db: Session = Depends(get_db),
):
    require_role(x_role, {"content_admin"})
    repo_factory = SqlAlchemyRepositoryFactory(db)
    products_repo = repo_factory.products()

    requested_skus = [variant.sku for variant in payload.variants]
    if len(requested_skus) != len(set(requested_skus)):
        api_error(422, "VALIDATION_ERROR", "В запросе повторяются SKU.", {"skus": requested_skus})

    existing = products_repo.existing_skus(requested_skus)
    if existing:
        api_error(409, "SKU_EXISTS", "SKU уже существует.", {"sku": existing[0]})

    product = Product(name=payload.name, description=payload.description, images=list(payload.images or []))
    for variant in payload.variants:
        product.variants.append(
            Variant(
                sku=variant.sku,
                size=variant.size,
                color=variant.color,
                price_points=int(variant.price_points),
                stock_total=int(variant.stock_total),
                reserved=0,
            )
        )

    try:
        created = products_repo.add(product)
        db.commit()
    except Exception:
        db.rollback()
        raise

    return product_to_dict(created)


@router.get("", response_model=List[ProductOut])
def list_products(q: Optional[str] = Query(default=None), db: Session = Depends(get_db)):
    repo_factory = SqlAlchemyRepositoryFactory(db)
    products = repo_factory.products().list()

    output = []
    ql = q.lower() if q else None
    for product in products:
        _ = product.variants
        if ql and ql not in product.name.lower():
            continue
        output.append(product_to_dict(product))
    return output


@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: int, db: Session = Depends(get_db)):
    repo_factory = SqlAlchemyRepositoryFactory(db)
    product = repo_factory.products().get(product_id)
    if not product:
        api_error(404, "NOT_FOUND", "Товар не найден.", {"product_id": product_id})
    return product_to_dict(product)
