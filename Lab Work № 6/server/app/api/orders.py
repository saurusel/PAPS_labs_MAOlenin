from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.repositories.factories import SqlAlchemyRepositoryFactory
from app.schemas import OrderCreate, OrderStatusUpdate
from app.services.adapters import InventoryAdapter, PointsAdapter
from app.services.commands import CancelOrderCommand, ChangeOrderStatusCommand, CreateOrderCommand
from app.services.observers import build_event_bus
from app.services.order_decorators import AuditOrderServiceDecorator, LoggingOrderServiceDecorator
from app.services.order_facade import OrderFacade
from app.services.order_proxy import RoleProtectedOrderServiceProxy
from app.services.validators import CreateOrderValidationChainFactory
from app.utils import api_error, order_to_dict

router = APIRouter(prefix="/api/v1/orders", tags=["orders"])



def build_order_service(db: Session):
    repo_factory = SqlAlchemyRepositoryFactory(db)
    event_bus = build_event_bus()
    validator_chain = CreateOrderValidationChainFactory.build(repo_factory)
    facade = OrderFacade(
        repo_factory=repo_factory,
        validator_chain=validator_chain,
        inventory_port=InventoryAdapter(db),
        points_port=PointsAdapter(db),
        event_bus=event_bus,
    )
    proxy = RoleProtectedOrderServiceProxy(facade)
    audited = AuditOrderServiceDecorator(proxy, event_bus)
    return LoggingOrderServiceDecorator(audited)


@router.post("", status_code=201)
def create_order(
    payload: OrderCreate,
    x_role: Optional[str] = Header(default=None, alias="X-Role"),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    db: Session = Depends(get_db),
):
    command = CreateOrderCommand(build_order_service(db), payload, x_role, x_user_id)
    return order_to_dict(command.execute())


@router.get("")
def list_orders(
    status: Optional[str] = Query(default=None),
    user_id: Optional[str] = Query(default=None),
    x_role: Optional[str] = Header(default=None, alias="X-Role"),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    db: Session = Depends(get_db),
):
    if x_role not in {"buyer", "fulfillment_admin"}:
        api_error(403, "FORBIDDEN", "Недостаточно прав. Требуется роль buyer или fulfillment_admin.")

    orders = SqlAlchemyRepositoryFactory(db).orders().list()
    items = orders

    if x_role == "buyer":
        if not x_user_id:
            api_error(422, "VALIDATION_ERROR", "Не передан X-User-Id.")
        items = [order for order in items if order.user_id == x_user_id]
    elif user_id:
        items = [order for order in items if order.user_id == user_id]

    if status:
        items = [order for order in items if order.status == status]

    return [order_to_dict(order) for order in items]


@router.put("/{order_id}/status")
def update_order_status(
    order_id: int,
    payload: OrderStatusUpdate,
    x_role: Optional[str] = Header(default=None, alias="X-Role"),
    db: Session = Depends(get_db),
):
    command = ChangeOrderStatusCommand(build_order_service(db), order_id, payload.status, x_role)
    return order_to_dict(command.execute())


@router.delete("/{order_id}")
def cancel_order(
    order_id: int,
    x_role: Optional[str] = Header(default=None, alias="X-Role"),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    db: Session = Depends(get_db),
):
    command = CancelOrderCommand(build_order_service(db), order_id, x_role, x_user_id)
    return order_to_dict(command.execute())
