from __future__ import annotations

from typing import Protocol

from app.services.order_builder import OrderBuilder
from app.services.states import OrderStateFactory
from app.services.strategies import TransitionStrategyFactory
from app.utils import api_error, now_iso


class OrderService(Protocol):
    def create_order(self, payload, *, x_role: str | None, x_user_id: str | None): ...
    def change_status(self, order_id: int, target_status: str, *, x_role: str | None): ...
    def cancel_order(self, order_id: int, *, x_role: str | None, x_user_id: str | None): ...


class OrderFacade:
    def __init__(self, repo_factory, validator_chain, inventory_port, points_port, event_bus):
        self.repo_factory = repo_factory
        self.validator_chain = validator_chain
        self.inventory_port = inventory_port
        self.points_port = points_port
        self.event_bus = event_bus

    def create_order(self, payload, *, x_role: str | None, x_user_id: str | None):
        ctx = {"x_user_id": x_user_id, "items": payload.items}
        self.validator_chain.handle(ctx)

        products_repo = self.repo_factory.products()
        orders_repo = self.repo_factory.orders()

        skus = [item.sku for item in payload.items]
        variants = products_repo.get_variants_by_skus(skus)
        by_sku = {variant.sku: variant for variant in variants}

        builder = OrderBuilder(user_id=str(x_user_id))
        for item in payload.items:
            variant = by_sku[item.sku]
            builder.add_item(item.sku, int(item.qty), int(variant.price_points))

        order = builder.build()

        try:
            saved = orders_repo.add(order)
            self.points_port.debit_for_order(saved.user_id, int(saved.total_points), int(saved.id))
            orders_repo.commit()
        except Exception:
            orders_repo.rollback()
            raise

        self.event_bus.publish("order_created", {"order_id": saved.id, "user_id": saved.user_id})
        return saved

    def change_status(self, order_id: int, target_status: str, *, x_role: str | None):
        orders_repo = self.repo_factory.orders()
        order = orders_repo.get(order_id)
        if not order:
            api_error(404, "NOT_FOUND", "Заказ не найден.", {"order_id": order_id})

        state = OrderStateFactory.create(order.status)
        state.ensure_can_transition(target_status)
        strategy = TransitionStrategyFactory.create(target_status, self.inventory_port, self.points_port, self.event_bus)

        try:
            strategy.apply(order)
            order.status = target_status
            order.updated_at = now_iso()
            orders_repo.commit()
        except Exception:
            orders_repo.rollback()
            raise

        self.event_bus.publish(
            "order_status_changed",
            {"order_id": order.id, "user_id": order.user_id, "status": order.status},
        )
        return order

    def cancel_order(self, order_id: int, *, x_role: str | None, x_user_id: str | None):
        orders_repo = self.repo_factory.orders()
        order = orders_repo.get(order_id)
        if not order:
            api_error(404, "NOT_FOUND", "Заказ не найден.", {"order_id": order_id})

        if x_role == "buyer":
            if not x_user_id:
                api_error(422, "VALIDATION_ERROR", "Не передан X-User-Id.")
            if order.user_id != x_user_id:
                api_error(403, "FORBIDDEN", "Нельзя отменить чужой заказ.")

        state = OrderStateFactory.create(order.status)
        state.ensure_can_transition("Отменен")
        strategy = TransitionStrategyFactory.create("Отменен", self.inventory_port, self.points_port, self.event_bus)

        try:
            strategy.apply(order)
            order.status = "Отменен"
            order.updated_at = now_iso()
            orders_repo.commit()
        except Exception:
            orders_repo.rollback()
            raise

        self.event_bus.publish(
            "order_status_changed",
            {"order_id": order.id, "user_id": order.user_id, "status": order.status},
        )
        return order
