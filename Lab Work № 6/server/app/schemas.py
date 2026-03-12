from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field, conint


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
