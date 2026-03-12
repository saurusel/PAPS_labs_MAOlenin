from __future__ import annotations


class CreateOrderCommand:
    def __init__(self, service, payload, x_role: str | None, x_user_id: str | None):
        self.service = service
        self.payload = payload
        self.x_role = x_role
        self.x_user_id = x_user_id

    def execute(self):
        return self.service.create_order(self.payload, x_role=self.x_role, x_user_id=self.x_user_id)


class ChangeOrderStatusCommand:
    def __init__(self, service, order_id: int, target_status: str, x_role: str | None):
        self.service = service
        self.order_id = order_id
        self.target_status = target_status
        self.x_role = x_role

    def execute(self):
        return self.service.change_status(self.order_id, self.target_status, x_role=self.x_role)


class CancelOrderCommand:
    def __init__(self, service, order_id: int, x_role: str | None, x_user_id: str | None):
        self.service = service
        self.order_id = order_id
        self.x_role = x_role
        self.x_user_id = x_user_id

    def execute(self):
        return self.service.cancel_order(self.order_id, x_role=self.x_role, x_user_id=self.x_user_id)
