from __future__ import annotations


class OrderServiceDecorator:
    def __init__(self, inner_service):
        self.inner_service = inner_service

    def create_order(self, payload, *, x_role: str | None, x_user_id: str | None):
        return self.inner_service.create_order(payload, x_role=x_role, x_user_id=x_user_id)

    def change_status(self, order_id: int, target_status: str, *, x_role: str | None):
        return self.inner_service.change_status(order_id, target_status, x_role=x_role)

    def cancel_order(self, order_id: int, *, x_role: str | None, x_user_id: str | None):
        return self.inner_service.cancel_order(order_id, x_role=x_role, x_user_id=x_user_id)


class LoggingOrderServiceDecorator(OrderServiceDecorator):
    def create_order(self, payload, *, x_role: str | None, x_user_id: str | None):
        print(f"[LOG] create_order role={x_role} user={x_user_id}")
        result = super().create_order(payload, x_role=x_role, x_user_id=x_user_id)
        print(f"[LOG] create_order done order_id={result.id}")
        return result

    def change_status(self, order_id: int, target_status: str, *, x_role: str | None):
        print(f"[LOG] change_status role={x_role} order_id={order_id} -> {target_status}")
        result = super().change_status(order_id, target_status, x_role=x_role)
        print(f"[LOG] change_status done order_id={result.id} status={result.status}")
        return result

    def cancel_order(self, order_id: int, *, x_role: str | None, x_user_id: str | None):
        print(f"[LOG] cancel_order role={x_role} user={x_user_id} order_id={order_id}")
        result = super().cancel_order(order_id, x_role=x_role, x_user_id=x_user_id)
        print(f"[LOG] cancel_order done order_id={result.id} status={result.status}")
        return result


class AuditOrderServiceDecorator(OrderServiceDecorator):
    def __init__(self, inner_service, event_bus):
        super().__init__(inner_service)
        self.event_bus = event_bus

    def create_order(self, payload, *, x_role: str | None, x_user_id: str | None):
        self.event_bus.publish("audit", {"action": "create_order_requested", "user_id": x_user_id})
        return super().create_order(payload, x_role=x_role, x_user_id=x_user_id)

    def change_status(self, order_id: int, target_status: str, *, x_role: str | None):
        self.event_bus.publish("audit", {"action": "change_status_requested", "order_id": order_id, "status": target_status})
        return super().change_status(order_id, target_status, x_role=x_role)

    def cancel_order(self, order_id: int, *, x_role: str | None, x_user_id: str | None):
        self.event_bus.publish("audit", {"action": "cancel_order_requested", "order_id": order_id, "user_id": x_user_id})
        return super().cancel_order(order_id, x_role=x_role, x_user_id=x_user_id)
