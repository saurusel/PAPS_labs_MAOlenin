from __future__ import annotations

from app.utils import api_error


class OrderState:
    name = ""
    allowed_transitions: set[str] = set()

    def ensure_can_transition(self, target_status: str):
        if target_status not in self.allowed_transitions:
            api_error(
                400,
                "INVALID_STATUS_TRANSITION",
                "Недопустимый переход статуса.",
                {"from": self.name, "to": target_status, "allowed": sorted(self.allowed_transitions)},
            )


class NewOrderState(OrderState):
    name = "Новый"
    allowed_transitions = {"На проверке", "Отменен"}


class ReviewOrderState(OrderState):
    name = "На проверке"
    allowed_transitions = {"Сборка", "Отменен"}


class AssemblyOrderState(OrderState):
    name = "Сборка"
    allowed_transitions = {"Готов к выдаче"}


class ReadyOrderState(OrderState):
    name = "Готов к выдаче"
    allowed_transitions = {"Завершен"}


class CompletedOrderState(OrderState):
    name = "Завершен"
    allowed_transitions = set()


class CancelledOrderState(OrderState):
    name = "Отменен"
    allowed_transitions = set()


class OrderStateFactory:
    STATES = {
        "Новый": NewOrderState,
        "На проверке": ReviewOrderState,
        "Сборка": AssemblyOrderState,
        "Готов к выдаче": ReadyOrderState,
        "Завершен": CompletedOrderState,
        "Отменен": CancelledOrderState,
    }

    @classmethod
    def create(cls, status: str) -> OrderState:
        state_cls = cls.STATES.get(status)
        if not state_cls:
            api_error(400, "UNKNOWN_ORDER_STATE", "Неизвестное состояние заказа.", {"status": status})
        return state_cls()
