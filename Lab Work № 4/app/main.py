from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional, Literal

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field, conint

app = FastAPI(title="Corporate Merch Store API (Lab 4)", version="1.0")

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

# ---- in-memory storage (для ЛР) ----

_product_id_seq = 1
_order_id_seq = 1

products: Dict[int, dict] = {}
variants_by_sku: Dict[str, dict] = {}
orders: Dict[int, dict] = {}

# Балансы поинтов (упрощённо)
user_points: Dict[str, int] = {"u1": 5000, "u2": 2000}

# Леджер поинтов (упрощённо)
ledger: List[dict] = []

# ---- модели ----

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
    items: List[OrderItemIn] = Field(..., min_length=1)

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

# ---- Products ----

@app.post("/api/v1/products", response_model=ProductOut, status_code=201)
def create_product(payload: ProductCreate, x_role: Optional[str] = Header(default=None, alias="X-Role")):
    require_role(x_role, {"content_admin"})
    global _product_id_seq
    pid = _product_id_seq
    _product_id_seq += 1

    req_skus = [v.sku for v in payload.variants]
    if len(req_skus) != len(set(req_skus)):
        api_error(422, "VALIDATION_ERROR", "В запросе повторяются SKU.", {"skus": req_skus})
    for sku in req_skus:
        if sku in variants_by_sku:
            api_error(409, "SKU_EXISTS", "SKU уже существует.", {"sku": sku})

    product = {"id": pid, "name": payload.name, "description": payload.description, "images": payload.images, "variants": []}
    for v in payload.variants:
        variant = {
            "sku": v.sku, "size": v.size, "color": v.color,
            "price_points": int(v.price_points),
            "stock_total": int(v.stock_total),
            "reserved": 0,
            "product_id": pid
        }
        product["variants"].append(variant)
        variants_by_sku[v.sku] = variant

    products[pid] = product
    return product

@app.get("/api/v1/products", response_model=List[ProductOut])
def list_products(q: Optional[str] = Query(default=None)):
    items = list(products.values())
    if q:
        ql = q.lower()
        items = [p for p in items if ql in p["name"].lower()]
    return items

@app.get("/api/v1/products/{product_id}", response_model=ProductOut)
def get_product(product_id: int):
    p = products.get(product_id)
    if not p:
        api_error(404, "NOT_FOUND", "Товар не найден.", {"product_id": product_id})
    return p

# ---- Orders ----

@app.post("/api/v1/orders", status_code=201)
def create_order(
    payload: OrderCreate,
    x_role: Optional[str] = Header(default=None, alias="X-Role"),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
):
    require_role(x_role, {"buyer"})
    if not x_user_id:
        api_error(422, "VALIDATION_ERROR", "Не передан X-User-Id.")

    for it in payload.items:
        if it.sku not in variants_by_sku:
            api_error(404, "SKU_NOT_FOUND", "SKU не найден.", {"sku": it.sku})

    total = 0
    items_out = []
    for it in payload.items:
        v = variants_by_sku[it.sku]
        line = int(v["price_points"]) * int(it.qty)
        total += line
        items_out.append({"sku": it.sku, "qty": int(it.qty), "unit_points": int(v["price_points"]), "line_points": line})

    balance = user_points.get(x_user_id, 0)
    if balance < total:
        api_error(409, "INSUFFICIENT_POINTS", "Недостаточно поинтов для оформления заказа.", {"balance": balance, "required": total})

    # списываем поинты сразу
    user_points[x_user_id] = balance - total
    ledger.append({"ts": now_iso(), "user_id": x_user_id, "delta": -total, "reason": "ORDER_CREATED", "order_id": None})

    global _order_id_seq
    oid = _order_id_seq
    _order_id_seq += 1

    order = {
        "id": oid,
        "user_id": x_user_id,
        "status": "Новый",
        "items": items_out,
        "total_points": total,
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "history": [{"ts": now_iso(), "from": None, "to": "Новый", "by_role": x_role}],
        "reserved": False,
    }
    orders[oid] = order
    ledger[-1]["order_id"] = oid
    return order

@app.get("/api/v1/orders")
def list_orders(
    status: Optional[str] = Query(default=None),
    user_id: Optional[str] = Query(default=None),
    x_role: Optional[str] = Header(default=None, alias="X-Role"),
    x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
):
    if x_role not in {"buyer", "fulfillment_admin"}:
        api_error(403, "FORBIDDEN", "Недостаточно прав. Требуется роль buyer или fulfillment_admin.")

    items = list(orders.values())
    if x_role == "buyer":
        if not x_user_id:
            api_error(422, "VALIDATION_ERROR", "Не передан X-User-Id.")
        items = [o for o in items if o["user_id"] == x_user_id]
    else:
        if user_id:
            items = [o for o in items if o["user_id"] == user_id]

    if status:
        items = [o for o in items if o["status"] == status]
    return items

def reserve_for_order(order: dict):
    if order["reserved"]:
        return
    for it in order["items"]:
        v = variants_by_sku[it["sku"]]
        available = int(v["stock_total"]) - int(v["reserved"])
        if available < int(it["qty"]):
            api_error(409, "INSUFFICIENT_STOCK", "Недостаточно остатков для резервирования.", {"sku": it["sku"], "available": available, "required": int(it["qty"])})
    for it in order["items"]:
        v = variants_by_sku[it["sku"]]
        v["reserved"] = int(v["reserved"]) + int(it["qty"])
    order["reserved"] = True

def unreserve_for_order(order: dict):
    if not order["reserved"]:
        return
    for it in order["items"]:
        v = variants_by_sku[it["sku"]]
        v["reserved"] = max(0, int(v["reserved"]) - int(it["qty"]))
    order["reserved"] = False

def deduct_stock_on_complete(order: dict):
    if not order["reserved"]:
        reserve_for_order(order)
    for it in order["items"]:
        v = variants_by_sku[it["sku"]]
        qty = int(it["qty"])
        v["stock_total"] = int(v["stock_total"]) - qty
        v["reserved"] = max(0, int(v["reserved"]) - qty)
    order["reserved"] = False

def refund_points(order: dict):
    uid = order["user_id"]
    total = int(order["total_points"])
    user_points[uid] = user_points.get(uid, 0) + total
    ledger.append({"ts": now_iso(), "user_id": uid, "delta": total, "reason": "ORDER_CANCELLED", "order_id": order["id"]})

@app.put("/api/v1/orders/{order_id}/status")
def update_order_status(order_id: int, payload: OrderStatusUpdate, x_role: Optional[str] = Header(default=None, alias="X-Role")):
    require_role(x_role, {"fulfillment_admin"})
    order = orders.get(order_id)
    if not order:
        api_error(404, "NOT_FOUND", "Заказ не найден.", {"order_id": order_id})

    current = order["status"]
    target = payload.status

    allowed = ALLOWED_TRANSITIONS.get(current, set())
    if target not in allowed:
        api_error(400, "INVALID_STATUS_TRANSITION", "Недопустимый переход статуса.", {"from": current, "to": target, "allowed": sorted(allowed)})

    if target == "На проверке":
        reserve_for_order(order)
    if target == "Отменен":
        if current not in CANCEL_ALLOWED:
            api_error(400, "CANCEL_NOT_ALLOWED", "Отмена разрешена только в статусах: Новый, На проверке.")
        unreserve_for_order(order)
        refund_points(order)
    if target == "Завершен":
        deduct_stock_on_complete(order)

    order["status"] = target
    order["updated_at"] = now_iso()
    order["history"].append({"ts": now_iso(), "from": current, "to": target, "by_role": x_role})
    return order

@app.delete("/api/v1/orders/{order_id}")
def cancel_order(order_id: int, x_role: Optional[str] = Header(default=None, alias="X-Role"), x_user_id: Optional[str] = Header(default=None, alias="X-User-Id")):
    if x_role not in {"buyer", "fulfillment_admin"}:
        api_error(403, "FORBIDDEN", "Недостаточно прав. Требуется роль buyer или fulfillment_admin.")
    order = orders.get(order_id)
    if not order:
        api_error(404, "NOT_FOUND", "Заказ не найден.", {"order_id": order_id})

    if x_role == "buyer":
        if not x_user_id:
            api_error(422, "VALIDATION_ERROR", "Не передан X-User-Id.")
        if order["user_id"] != x_user_id:
            api_error(403, "FORBIDDEN", "Нельзя отменить чужой заказ.")

    if order["status"] not in CANCEL_ALLOWED:
        api_error(400, "CANCEL_NOT_ALLOWED", "Отмена разрешена только в статусах: Новый, На проверке.")

    unreserve_for_order(order)
    refund_points(order)

    prev = order["status"]
    order["status"] = "Отменен"
    order["updated_at"] = now_iso()
    order["history"].append({"ts": now_iso(), "from": prev, "to": "Отменен", "by_role": x_role})
    return order