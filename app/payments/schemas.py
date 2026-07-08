from pydantic import BaseModel


class CreatePaymentOrderRequest(BaseModel):
    order_id: int


class CreatePaymentOrderResponse(BaseModel):
    payment_id: int
    razorpay_order_id: str
    amount: float
    currency: str = "INR"


class RazorpayWebhookPayload(BaseModel):
    """Shape mirrors Razorpay's actual webhook body closely enough to swap in the
    real SDK later without changing this contract."""
    razorpay_order_id: str
    razorpay_payment_id: str
    status: str  # "captured" | "failed"
    method: str | None = None


class PaymentOut(BaseModel):
    id: int
    order_id: int
    razorpay_order_id: str | None
    razorpay_payment_id: str | None
    amount: float
    status: str
    method: str | None

    class Config:
        from_attributes = True
