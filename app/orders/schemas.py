from datetime import datetime

from pydantic import BaseModel, Field


class OrderItemCreate(BaseModel):
    product_id: int
    quantity: int = Field(ge=1)


class OrderCreate(BaseModel):
    store_id: int
    items: list[OrderItemCreate]


class OrderItemOut(BaseModel):
    product_id: int
    product_name: str
    quantity: int
    price: float
    subtotal: float

    class Config:
        from_attributes = True


class OrderOut(BaseModel):
    id: int
    store_id: int
    store_name: str
    customer_id: int
    customer_name: str | None
    status: str
    payment_status: str
    total_amount: float
    items: list[OrderItemOut]
    created_at: datetime

    class Config:
        from_attributes = True


ALLOWED_STATUS_TRANSITIONS = {
    "created": {"accepted", "cancelled"},
    "accepted": {"packed", "cancelled"},
    "packed": {"completed", "cancelled"},
    "completed": set(),
    "cancelled": set(),
}


class OrderStatusUpdate(BaseModel):
    status: str  # must be one of ALLOWED_STATUS_TRANSITIONS keys
