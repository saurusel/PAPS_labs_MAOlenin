from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import LedgerEntry, UserPoints, Variant
from app.repositories.interfaces import RepositoryFactory
from app.utils import api_error, now_iso


# Legacy helper functions preserved from Lab 5 and adapted behind ports.

def reserve_for_order_legacy(db: Session, order):
    if order.reserved:
        return

    for item in order.items:
        variant = db.execute(select(Variant).where(Variant.sku == item.sku).with_for_update()).scalar_one()
        available = int(variant.stock_total) - int(variant.reserved)
        if available < int(item.qty):
            api_error(
                409,
                "INSUFFICIENT_STOCK",
                "Недостаточно остатков для резервирования.",
                {"sku": item.sku, "available": available, "required": int(item.qty)},
            )

    for item in order.items:
        variant = db.execute(select(Variant).where(Variant.sku == item.sku).with_for_update()).scalar_one()
        variant.reserved = int(variant.reserved) + int(item.qty)

    order.reserved = True



def unreserve_for_order_legacy(db: Session, order):
    if not order.reserved:
        return

    for item in order.items:
        variant = db.execute(select(Variant).where(Variant.sku == item.sku).with_for_update()).scalar_one()
        variant.reserved = max(0, int(variant.reserved) - int(item.qty))

    order.reserved = False



def deduct_stock_on_complete_legacy(db: Session, order):
    if not order.reserved:
        reserve_for_order_legacy(db, order)

    for item in order.items:
        variant = db.execute(select(Variant).where(Variant.sku == item.sku).with_for_update()).scalar_one()
        qty = int(item.qty)
        variant.stock_total = int(variant.stock_total) - qty
        variant.reserved = max(0, int(variant.reserved) - qty)

    order.reserved = False



def refund_points_legacy(db: Session, order):
    user = db.execute(
        select(UserPoints).where(UserPoints.user_id == order.user_id).with_for_update()
    ).scalar_one()
    user.balance = int(user.balance) + int(order.total_points)
    db.add(
        LedgerEntry(
            ts=now_iso(),
            user_id=order.user_id,
            delta=int(order.total_points),
            reason="ORDER_CANCELLED",
            order_id=order.id,
        )
    )



def debit_points_legacy(db: Session, user_id: str, total: int, order_id: int):
    user = db.execute(select(UserPoints).where(UserPoints.user_id == user_id).with_for_update()).scalar_one_or_none()
    if not user:
        user = UserPoints(user_id=user_id, balance=0)
        db.add(user)
        db.flush()

    balance = int(user.balance)
    if balance < total:
        api_error(
            409,
            "INSUFFICIENT_POINTS",
            "Недостаточно поинтов для оформления заказа.",
            {"balance": balance, "required": total},
        )

    user.balance = balance - total
    db.add(LedgerEntry(ts=now_iso(), user_id=user_id, delta=-total, reason="ORDER_CREATED", order_id=order_id))


class InventoryAdapter:
    def __init__(self, db: Session):
        self.db = db

    def reserve(self, order):
        reserve_for_order_legacy(self.db, order)

    def unreserve(self, order):
        unreserve_for_order_legacy(self.db, order)

    def complete(self, order):
        deduct_stock_on_complete_legacy(self.db, order)


class PointsAdapter:
    def __init__(self, db: Session):
        self.db = db

    def debit_for_order(self, user_id: str, total: int, order_id: int):
        debit_points_legacy(self.db, user_id, total, order_id)

    def refund_for_order(self, order):
        refund_points_legacy(self.db, order)
