from pydantic import BaseModel

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_customer
from app.payments import schemas, service
from app.models import Order

router = APIRouter(prefix="/payments", tags=["payments"])


@router.get("/config")
def payment_config():
    """Publishable config only — razorpay_key_secret NEVER leaves the server."""
    from app.core.config import settings
    return {
        "razorpay_key_id": settings.razorpay_key_id,  # null if not configured yet — frontend should show a notice
        "razorpay_configured": bool(settings.razorpay_key_id and settings.razorpay_key_secret),
    }


@router.post("/create-order", response_model=schemas.CreatePaymentOrderResponse)
def create_payment_order(payload: schemas.CreatePaymentOrderRequest, db: Session = Depends(get_db), customer=Depends(get_current_customer)):
    order = db.query(Order).filter(Order.id == payload.order_id, Order.customer_id == customer.id).first()
    if not order:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found")

    payment = service.create_payment_for_order(db, order)
    return schemas.CreatePaymentOrderResponse(
        payment_id=payment.id,
        razorpay_order_id=payment.razorpay_order_id,
        amount=float(payment.amount),
    )


class RazorpayCheckoutVerifyRequest(BaseModel):
    """What Razorpay's Checkout.js returns to your frontend after a real payment —
    see checkout.html for the JS that calls this."""
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


@router.post("/verify", response_model=schemas.PaymentOut)
def verify_razorpay_checkout(payload: RazorpayCheckoutVerifyRequest, db: Session = Depends(get_db)):
    """Real Razorpay flow: frontend Checkout.js gives you these 3 values on success.
    Verify the signature here BEFORE trusting the payment — this is the real security
    check that a dev-mode /webhook call skips."""
    if not service.verify_razorpay_signature(payload.razorpay_order_id, payload.razorpay_payment_id, payload.razorpay_signature):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Payment signature verification failed")

    payment = service.handle_webhook(
        db, payload.razorpay_order_id, payload.razorpay_payment_id, "captured", "razorpay_checkout"
    )
    return payment


@router.post("/webhook", response_model=schemas.PaymentOut)
def razorpay_webhook(payload: schemas.RazorpayWebhookPayload, db: Session = Depends(get_db)):
    """Dev/testing shortcut — simulates a webhook without signature verification.
    Use /payments/verify for the real Razorpay Checkout.js flow instead."""
    payment = service.handle_webhook(
        db, payload.razorpay_order_id, payload.razorpay_payment_id, payload.status, payload.method
    )
    return payment
