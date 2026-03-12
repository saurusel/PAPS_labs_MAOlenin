from __future__ import annotations

from app.models import Order, OrderItem
from app.utils import now_iso


class OrderBuilder:
    def __init__(self, user_id: str):
        self.order = Order(
            user_id=user_id,
            status="Новый",
            total_points=0,
            created_at=now_iso(),
            updated_at=now_iso(),
            reserved=False,
        )

    def add_item(self, sku: str, qty: int, unit_points: int):
        line_points = qty * unit_points
        self.order.items.append(
            OrderItem(
                sku=sku,
                qty=qty,
                unit_points=unit_points,
                line_points=line_points,
            )
        )
        self.order.total_points += line_points
        return self

    def build(self) -> Order:
        return self.order
