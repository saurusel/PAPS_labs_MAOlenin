from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import HTTPException


def now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def api_error(status_code: int, code: str, message: str, details: Optional[dict] = None):
    raise HTTPException(
        status_code=status_code,
        detail={"error": {"code": code, "message": message, "details": details or {}}},
    )


def require_role(x_role: str | None, allowed: set[str]):
    if x_role is None or x_role not in allowed:
        api_error(403, "FORBIDDEN", f"Недостаточно прав. Требуется роль: {', '.join(sorted(allowed))}.")


def product_to_dict(product) -> dict:
    return {
        "id": product.id,
        "name": product.name,
        "description": product.description,
        "images": list(product.images or []),
        "variants": [
            {
                "sku": variant.sku,
                "size": variant.size,
                "color": variant.color,
                "price_points": int(variant.price_points),
                "stock_total": int(variant.stock_total),
                "reserved": int(variant.reserved),
                "product_id": product.id,
            }
            for variant in product.variants
        ],
    }


def order_to_dict(order) -> dict:
    return {
        "id": order.id,
        "user_id": order.user_id,
        "status": order.status,
        "items": [
            {
                "sku": item.sku,
                "qty": int(item.qty),
                "unit_points": int(item.unit_points),
                "line_points": int(item.line_points),
            }
            for item in order.items
        ],
        "total_points": int(order.total_points),
        "created_at": order.created_at,
        "updated_at": order.updated_at,
        "reserved": bool(order.reserved),
    }
