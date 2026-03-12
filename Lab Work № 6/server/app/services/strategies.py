from __future__ import annotations

from app.services.observers import EventBus


class TransitionStrategy:
    def apply(self, order):
        raise NotImplementedError


class NoOpTransitionStrategy(TransitionStrategy):
    def apply(self, order):
        return None


class ReviewTransitionStrategy(TransitionStrategy):
    def __init__(self, inventory_port):
        self.inventory_port = inventory_port

    def apply(self, order):
        self.inventory_port.reserve(order)


class CancelTransitionStrategy(TransitionStrategy):
    def __init__(self, inventory_port, points_port, event_bus: EventBus):
        self.inventory_port = inventory_port
        self.points_port = points_port
        self.event_bus = event_bus

    def apply(self, order):
        self.inventory_port.unreserve(order)
        self.points_port.refund_for_order(order)
        self.event_bus.publish("order_cancelled", {"order_id": order.id, "user_id": order.user_id})


class CompleteTransitionStrategy(TransitionStrategy):
    def __init__(self, inventory_port, event_bus: EventBus):
        self.inventory_port = inventory_port
        self.event_bus = event_bus

    def apply(self, order):
        self.inventory_port.complete(order)
        self.event_bus.publish("order_completed", {"order_id": order.id, "user_id": order.user_id})


class TransitionStrategyFactory:
    @staticmethod
    def create(target_status: str, inventory_port, points_port, event_bus: EventBus) -> TransitionStrategy:
        if target_status == "На проверке":
            return ReviewTransitionStrategy(inventory_port)
        if target_status == "Отменен":
            return CancelTransitionStrategy(inventory_port, points_port, event_bus)
        if target_status == "Завершен":
            return CompleteTransitionStrategy(inventory_port, event_bus)
        return NoOpTransitionStrategy()
