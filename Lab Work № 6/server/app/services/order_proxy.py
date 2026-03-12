from __future__ import annotations

from app.utils import api_error


class RoleProtectedOrderServiceProxy:
    def __init__(self, inner_service):
        self.inner_service = inner_service

    def create_order(self, payload, *, x_role: str | None, x_user_id: str | None):
        if x_role != "buyer":
            api_error(403, "FORBIDDEN", "Недостаточно прав. Требуется роль: buyer.")
        return self.inner_service.create_order(payload, x_role=x_role, x_user_id=x_user_id)

    def change_status(self, order_id: int, target_status: str, *, x_role: str | None):
        if x_role != "fulfillment_admin":
            api_error(403, "FORBIDDEN", "Недостаточно прав. Требуется роль: fulfillment_admin.")
        return self.inner_service.change_status(order_id, target_status, x_role=x_role)

    def cancel_order(self, order_id: int, *, x_role: str | None, x_user_id: str | None):
        if x_role not in {"buyer", "fulfillment_admin"}:
            api_error(403, "FORBIDDEN", "Недостаточно прав. Требуется роль buyer или fulfillment_admin.")
        return self.inner_service.cancel_order(order_id, x_role=x_role, x_user_id=x_user_id)
