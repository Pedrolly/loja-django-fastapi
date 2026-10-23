from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- Auth ----------
class RegisterIn(BaseModel):
    username: str = Field(min_length=3, max_length=150)
    email: str = ""
    password: str = Field(min_length=8)


class UserOut(ORMModel):
    id: int
    username: str
    email: str
    is_staff: bool


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------- Catálogo ----------
class CategoryOut(ORMModel):
    id: int
    name: str
    slug: str


class CategoryIn(BaseModel):
    name: str = Field(max_length=100)
    slug: str = Field(max_length=120)


class ProductOut(ORMModel):
    id: int
    name: str
    slug: str
    description: str
    price: Decimal
    stock: int
    is_active: bool
    category: CategoryOut
    image_url: str | None = None


class ProductIn(BaseModel):
    category_id: int
    name: str = Field(max_length=200)
    slug: str = Field(max_length=220)
    description: str = ""
    price: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    stock: int = Field(ge=0, default=0)
    is_active: bool = True


class ProductPatch(BaseModel):
    name: str | None = None
    description: str | None = None
    price: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    stock: int | None = Field(default=None, ge=0)
    is_active: bool | None = None


# ---------- Pedidos ----------
class OrderItemIn(BaseModel):
    product_id: int
    quantity: int = Field(gt=0, le=100)


class OrderIn(BaseModel):
    items: list[OrderItemIn] = Field(min_length=1)


class OrderItemOut(BaseModel):
    product_id: int
    product_name: str
    quantity: int
    unit_price: Decimal
    subtotal: Decimal


class OrderOut(BaseModel):
    id: int
    status: str
    created_at: datetime
    total: Decimal
    items: list[OrderItemOut]
