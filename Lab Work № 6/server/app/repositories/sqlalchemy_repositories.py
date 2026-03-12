from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import LedgerEntry, Order, Product, UserPoints, Variant


class SqlAlchemyProductRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, product: Product) -> Product:
        self.db.add(product)
        self.db.flush()
        self.db.refresh(product)
        _ = product.variants
        return product

    def get(self, product_id: int) -> Product | None:
        product = self.db.get(Product, product_id)
        if product:
            _ = product.variants
        return product

    def list(self) -> list[Product]:
        return self.db.execute(select(Product).order_by(Product.id.asc())).scalars().unique().all()

    def get_variants_by_skus(self, skus: list[str]) -> list[Variant]:
        if not skus:
            return []
        return self.db.execute(select(Variant).where(Variant.sku.in_(skus))).scalars().all()

    def existing_skus(self, skus: list[str]) -> list[str]:
        if not skus:
            return []
        return self.db.execute(select(Variant.sku).where(Variant.sku.in_(skus))).scalars().all()

    def get_variant_for_update(self, sku: str) -> Variant | None:
        return self.db.execute(select(Variant).where(Variant.sku == sku).with_for_update()).scalar_one_or_none()


class SqlAlchemyOrderRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, order: Order) -> Order:
        self.db.add(order)
        self.db.flush()
        self.db.refresh(order)
        _ = order.items
        return order

    def get(self, order_id: int) -> Order | None:
        order = self.db.get(Order, order_id)
        if order:
            _ = order.items
        return order

    def list(self) -> list[Order]:
        return self.db.execute(select(Order).order_by(Order.id.asc())).scalars().unique().all()

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()


class SqlAlchemyPointsRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_for_update(self, user_id: str) -> UserPoints | None:
        return self.db.execute(
            select(UserPoints).where(UserPoints.user_id == user_id).with_for_update()
        ).scalar_one_or_none()

    def ensure(self, user_id: str) -> UserPoints:
        user = self.get_for_update(user_id)
        if user:
            return user
        user = UserPoints(user_id=user_id, balance=0)
        self.db.add(user)
        self.db.flush()
        return user


class SqlAlchemyLedgerRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, entry: LedgerEntry) -> LedgerEntry:
        self.db.add(entry)
        self.db.flush()
        return entry
