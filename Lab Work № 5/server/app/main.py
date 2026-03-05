from __future__ import annotations

import os
import time
from datetime import datetime
from typing import Dict, List, Optional, Literal

from fastapi import FastAPI, Header, HTTPException, Query, Request, Depends
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field, conint

from sqlalchemy import (
    create_engine, String, Integer, Text, Boolean, DateTime, ForeignKey, JSON as SAJSON
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker, Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select


# -------------------- FastAPI --------------------

app = FastAPI(title="Corporate Merch Store API (Lab 5)", version="1.0")


# ---- единый формат ошибок ----

@app.exception_handler(HTTPException)
async def http_exc_handler(request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": "HTTP_ERROR", "message": str(exc.detail), "details": {}}},
    )

@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "VALIDATION_ERROR", "message": "Ошибка валидации входных данных.", "details": exc.errors()}},
    )

def now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

def api_error(status_code: int, code: str, message: str, details: dict | None = None):
    raise HTTPException(
        status_code=status_code,
        detail={"error": {"code": code, "message": message, "details": details or {}}},
    )

def require_role(x_role: str | None, allowed: set[str]):
    if x_role is None or x_role not in allowed:
        api_error(403, "FORBIDDEN", f"Недостаточно прав. Требуется роль: {', '.join(sorted(allowed))}.")


# -------------------- DB (PostgreSQL) --------------------

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://merch:merch@localhost:5432/merchdb")
ENGINE = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=ENGINE, autoflush=False, autocommit=False)

class Base(DeclarativeBase):
    pass


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    images: Mapped[list] = mapped_column(SAJSON, default=list, nullable=False)

    variants: Mapped[List["Variant"]] = relationship(back_populates="product", cascade="all, delete-orphan")


class Variant(Base):
    __tablename__ = "variants"

    sku: Mapped[str] = mapped_column(String(128), primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False)

    size: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    color: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    price_points: Mapped[int] = mapped_column(Integer, nullable=False)
    stock_total: Mapped[int] = mapped_column(Integer, nullable=False)
    reserved: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    product: Mapped["Product"] = relationship(back_populates="variants")


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    total_points: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False)
    reserved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    items: Mapped[List["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    sku: Mapped[str] = mapped_column(ForeignKey("variants.sku"), nullable=False)
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_points: Mapped[int] = mapped_column(Integer, nullable=False)
    line_points: Mapped[int] = mapped_column(Integer, nullable=False)

    order: Mapped["Order"] = relationship(back_populates="items")


class UserPoints(Base):
    __tablename__ = "user_points"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    balance: Mapped[int] = mapped_column(Integer, nullable=False)


class LedgerEntry(Base):
    __tablename__ = "ledger"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[str] = mapped_column(String(32), nullable=False)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(64), nullable=False)
    order_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.on_event("startup")
def startup():
    # небольшой retry, чтобы контейнер Postgres успел подняться
    for attempt in range(1, 31):
        try:
            Base.metadata.create_all(ENGINE)
            break
        except Exception:  # noqa
            if attempt == 30:
                raise
            time.sleep(1)

    # сидирование балансов (как в ЛР4)
    with SessionLocal() as db:
        try:
            for uid, bal in {"u1": 5000, "u2": 2000}.items():
                exists = db.get(UserPoints, uid)
                if not exists:
                    db.add(UserPoints(user_id=uid, balance=bal))


            db.commit()
        except Exception:
            db.rollback()
            raise
@app.get("/health")
def health():
    return {"ok": True}


# -------------------- Pydantic models --------------------

class VariantIn(BaseModel):
    sku: str = Field(..., min_length=1)
    size: Optional[str] = None
    color: Optional[str] = None
    price_points: conint(ge=0)  # type: ignore
    stock_total: conint(ge=0)  # type: ignore


class ProductCreate(BaseModel):
    name: str = Field(..., min_length=1)
    description: str = ""
    images: List[str] = Field(default_factory=list)
    variants: List[VariantIn] = Field(default_factory=list)


class ProductOut(BaseModel):
    id: int
    name: str
    description: str
    images: List[str]
    variants: List[dict]


class OrderItemIn(BaseModel):
    sku: str = Field(..., min_length=1)
    qty: conint(ge=1, le=1000)  # type: ignore


class OrderCreate(BaseModel):
    items: List[OrderItemIn] = Field(..., min_items=1)


OrderStatus = Literal["Новый", "На проверке", "Сборка", "Готов к выдаче", "Завершен", "Отменен"]


class OrderStatusUpdate(BaseModel):
    status: OrderStatus


ALLOWED_TRANSITIONS = {
    "Новый": {"На проверке", "Отменен"},
    "На проверке": {"Сборка", "Отменен"},
    "Сборка": {"Готов к выдаче"},
    "Готов к выдаче": {"Завершен"},
    "Завершен": set(),
    "Отменен": set(),
}
CANCEL_ALLOWED = {"Новый", "На проверке"}


# -------------------- Helpers --------------------

def product_to_dict(p: Product) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "description": p.description,
        "images": list(p.images or []),
        "variants": [
            {
                "sku": v.sku,
                "size": v.size,
                "color": v.color,
                "price_points": int(v.price_points),
                "stock_total": int(v.stock_total),
                "reserved": int(v.reserved),
                "product_id": p.id,
            }
            for v in p.variants
        ],
    }


def order_to_dict(o: Order) -> dict:
    return {
        "id": o.id,
        "user_id": o.user_id,
        "status": o.status,
        "items": [
            {
                "sku": it.sku,
                "qty": int(it.qty),
                "unit_points": int(it.unit_points),
                "line_points": int(it.line_points),
            }
            for it in o.items
        ],
        "total_points": int(o.total_points),
        "created_at": o.created_at,
        "updated_at": o.updated_at,
        "reserved": bool(o.reserved),
    }


def reserve_for_order(db: Session, order: Order):
    if order.reserved:
        return

    # блокируем строки вариантов, чтобы корректно проверить доступность
    for it in order.items:
        v = db.execute(
            select(Variant).where(Variant.sku == it.sku).with_for_update()
        ).scalar_one()
        available = int(v.stock_total) - int(v.reserved)
        if available < int(it.qty):
            api_error(
                409,
                "INSUFFICIENT_STOCK",
                "Недостаточно остатков для резервирования.",
                {"sku": it.sku, "available": available, "required": int(it.qty)},
            )

    for it in order.items:
        v = db.execute(
            select(Variant).where(Variant.sku == it.sku).with_for_update()
        ).scalar_one()
        v.reserved = int(v.reserved) + int(it.qty)

    order.reserved = True


def unreserve_for_order(db: Session, order: Order):
    if not order.reserved:
        return

    for it in order.items:
        v = db.execute(
            select(Variant).where(Variant.sku == it.sku).with_for_update()
        ).scalar_one()
        v.reserved = max(0, int(v.reserved) - int(it.qty))

    order.reserved = False


def deduct_stock_on_complete(db: Session, order: Order):
    if not order.reserved:
        reserve_for_order(db, order)

    for it in order.items:
        v = db.execute(
            select(Variant).where(Variant.sku == it.sku).with_for_update()
        ).scalar_one()
        qty = int(it.qty)
        v.stock_total = int(v.stock_total) - qty
        v.reserved = max(0, int(v.reserved) - qty)

    order.reserved = False


def refund_points(db: Session, order: Order):
    uid = order.user_id
    total = int(order.total_points)

    user = db.execute(select(UserPoints).where(UserPoints.user_id == uid).with_for_update()).scalar_one()
    user.balance = int(user.balance) + total

    db.add(LedgerEntry(ts=now_iso(), user_id=uid, delta=total, reason="ORDER_CANCELLED", order_id=order.id))


# -------------------- Products --------------------

@app.post("/api/v1/products", response_model=ProductOut, status_code=201)
def create_product(
    payload: ProductCreate,
    x_role: Optional[str] = Header(default=None, alias="X-Role"),
    db: Session = Depends(get_db),
):
    require_role(x_role, {"content_admin"})

    req_skus = [v.sku for v in payload.variants]
    if len(req_skus) != len(set(req_skus)):
        api_error(422, "VALIDATION_ERROR", "В запросе повторяются SKU.", {"skus": req_skus})

    # проверяем существующие SKU
    if req_skus:
        existing = db.execute(select(Variant.sku).where(Variant.sku.in_(req_skus))).scalars().all()
        if existing:
            api_error(409, "SKU_EXISTS", "SKU уже существует.", {"sku": existing[0]})

    try:
        p = Product(name=payload.name, description=payload.description, images=list(payload.images or []))
        for v in payload.variants:
            p.variants.append(
                Variant(
                    sku=v.sku,
                    size=v.size,
                    color=v.color,
                    price_points=int(v.price_points),
                    stock_total=int(v.stock_total),
                    reserved=0,
                )
            )
        db.add(p)
        db.flush()
        db.refresh(p)
        # подгружаем variants
        _ = p.variants

        db.commit()
    except Exception:
        db.rollback()
        raise
    return product_to_dict(p)


@app.get("/api/v1/products", response_model=List[ProductOut])
def list_products(q: Optional[str] = Query(default=None), db: Session = Depends(get_db)):
    stmt = select(Product).order_by(Product.id.asc())
    products_list = db.execute(stmt).scalars().unique().all()

    out = []
    ql = q.lower() if q else None
    for p in products_list:
        if ql and ql not in p.name.lower():
            continue
        # ensure variants loaded
        _ = p.variants
        out.append(product_to_dict(p))
    return out


@app.get("/api/v1/products/{product_id}", response_model=ProductOut)
def get_product(product_id: int, db: Session = Depends(get_db)):
    p = db.get(Product, product_id)
    if not p:
        api_error(404, "NOT_FOUND", "Товар не найден.", {"product_id": product_id})
    _ = p.variants
    return product_to_dict(p)


# -------------------- Orders --------------------

@app.post("/api/v1/orders", status_code=201)
def create_order(
    payload: OrderCreate,
    x_role: Optional[str] = Header(default=None, alias="X-Role"),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    db: Session = Depends(get_db),
):
    require_role(x_role, {"buyer"})
    if not x_user_id:
        api_error(422, "VALIDATION_ERROR", "Не передан X-User-Id.")

    skus = [it.sku for it in payload.items]
    if not skus:
        api_error(422, "VALIDATION_ERROR", "Пустой список items.")

    variants = db.execute(select(Variant).where(Variant.sku.in_(skus))).scalars().all()
    by_sku: Dict[str, Variant] = {v.sku: v for v in variants}
    for sku in skus:
        if sku not in by_sku:
            api_error(404, "SKU_NOT_FOUND", "SKU не найден.", {"sku": sku})

    total = 0
    items_out = []
    for it in payload.items:
        v = by_sku[it.sku]
        line = int(v.price_points) * int(it.qty)
        total += line
        items_out.append(
            {"sku": it.sku, "qty": int(it.qty), "unit_points": int(v.price_points), "line_points": line}
        )

    try:
        # блокируем баланс
        user = db.execute(select(UserPoints).where(UserPoints.user_id == x_user_id).with_for_update()).scalar_one_or_none()
        if not user:
            user = UserPoints(user_id=x_user_id, balance=0)
            db.add(user)
            db.flush()

        balance = int(user.balance)
        if balance < total:
            api_error(409, "INSUFFICIENT_POINTS", "Недостаточно поинтов для оформления заказа.", {"balance": balance, "required": total})

        user.balance = balance - total

        o = Order(
            user_id=x_user_id,
            status="Новый",
            total_points=total,
            created_at=now_iso(),
            updated_at=now_iso(),
            reserved=False,
        )
        for it in items_out:
            o.items.append(
                OrderItem(
                    sku=it["sku"],
                    qty=int(it["qty"]),
                    unit_points=int(it["unit_points"]),
                    line_points=int(it["line_points"]),
                )
            )
        db.add(o)
        db.flush()
        db.refresh(o)

        db.add(LedgerEntry(ts=now_iso(), user_id=x_user_id, delta=-total, reason="ORDER_CREATED", order_id=o.id))

        _ = o.items

        db.commit()
    except Exception:
        db.rollback()
        raise
    return order_to_dict(o)


@app.get("/api/v1/orders")
def list_orders(
    status: Optional[str] = Query(default=None),
    user_id: Optional[str] = Query(default=None),
    x_role: Optional[str] = Header(default=None, alias="X-Role"),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    db: Session = Depends(get_db),
):
    if x_role not in {"buyer", "fulfillment_admin"}:
        api_error(403, "FORBIDDEN", "Недостаточно прав. Требуется роль buyer или fulfillment_admin.")

    stmt = select(Order).order_by(Order.id.asc())
    orders_list = db.execute(stmt).scalars().unique().all()

    items = orders_list
    if x_role == "buyer":
        if not x_user_id:
            api_error(422, "VALIDATION_ERROR", "Не передан X-User-Id.")
        items = [o for o in items if o.user_id == x_user_id]
    else:
        if user_id:
            items = [o for o in items if o.user_id == user_id]

    if status:
        items = [o for o in items if o.status == status]

    out = []
    for o in items:
        _ = o.items
        out.append(order_to_dict(o))
    return out


@app.put("/api/v1/orders/{order_id}/status")
def update_order_status(
    order_id: int,
    payload: OrderStatusUpdate,
    x_role: Optional[str] = Header(default=None, alias="X-Role"),
    db: Session = Depends(get_db),
):
    require_role(x_role, {"fulfillment_admin"})

    try:
        order = db.get(Order, order_id)
        if not order:
            api_error(404, "NOT_FOUND", "Заказ не найден.", {"order_id": order_id})
        _ = order.items

        current = order.status
        target = payload.status

        allowed = ALLOWED_TRANSITIONS.get(current, set())
        if target not in allowed:
            api_error(400, "INVALID_STATUS_TRANSITION", "Недопустимый переход статуса.", {"from": current, "to": target, "allowed": sorted(allowed)})

        if target == "На проверке":
            reserve_for_order(db, order)
        if target == "Отменен":
            if current not in CANCEL_ALLOWED:
                api_error(400, "CANCEL_NOT_ALLOWED", "Отмена разрешена только в статусах: Новый, На проверке.")
            unreserve_for_order(db, order)
            refund_points(db, order)
        if target == "Завершен":
            deduct_stock_on_complete(db, order)

        order.status = target
        order.updated_at = now_iso()

        db.commit()
    except Exception:
        db.rollback()
        raise
    return order_to_dict(order)


@app.delete("/api/v1/orders/{order_id}")
def cancel_order(
    order_id: int,
    x_role: Optional[str] = Header(default=None, alias="X-Role"),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    db: Session = Depends(get_db),
):
    if x_role not in {"buyer", "fulfillment_admin"}:
        api_error(403, "FORBIDDEN", "Недостаточно прав. Требуется роль buyer или fulfillment_admin.")

    try:
        order = db.get(Order, order_id)
        if not order:
            api_error(404, "NOT_FOUND", "Заказ не найден.", {"order_id": order_id})
        _ = order.items

        if x_role == "buyer":
            if not x_user_id:
                api_error(422, "VALIDATION_ERROR", "Не передан X-User-Id.")
            if order.user_id != x_user_id:
                api_error(403, "FORBIDDEN", "Нельзя отменить чужой заказ.")

        if order.status not in CANCEL_ALLOWED:
            api_error(400, "CANCEL_NOT_ALLOWED", "Отмена разрешена только в статусах: Новый, На проверке.")

        unreserve_for_order(db, order)
        refund_points(db, order)

        order.status = "Отменен"
        order.updated_at = now_iso()

        db.commit()
    except Exception:
        db.rollback()
        raise
    return order_to_dict(order)
