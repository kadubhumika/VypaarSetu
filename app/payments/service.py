import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Order, Payment, TransactionLedger, Inventory, Notification, Store, Merchant
from app.notifications.service import send_order_notification_with_buttons


def create_razorpay_order_stub(amount: float) -> str:
    """Fallback when Razorpay credentials aren't configured or fail."""
    return f"order_stub_{uuid.uuid4().hex[:14]}"


def create_razorpay_order(amount: float) -> str:
    """
    Real Razorpay order creation — now with a safety net. If the keys are missing,
    malformed, or Razorpay rejects them (wrong test/live key, typo, etc.), this falls
    back to the stub instead of crashing the whole checkout with a 500. Check your
    Docker logs for the [ERROR] line if this fires — it tells you exactly why.
    """
    if not (settings.razorpay_key_id and settings.razorpay_key_secret):
        return create_razorpay_order_stub(amount)

    try:
        import razorpay
        client = razorpay.Client(auth=(settings.razorpay_key_id, settings.razorpay_key_secret))
        order = client.order.create({
            "amount": int(amount * 100),
            "currency": "INR",
            "payment_capture": 1,
        })
        return order["id"]
    except Exception as e:
        print(f"[ERROR] Razorpay order creation failed ({e}). Falling back to stub — "
              f"double check RAZORPAY_KEY_ID/RAZORPAY_KEY_SECRET in .env are correct TEST mode keys.")
        return create_razorpay_order_stub(amount)


def verify_razorpay_signature(order_id: str, payment_id: str, signature: str) -> bool:
    if not settings.razorpay_key_secret:
        return False
    import razorpay
    client = razorpay.Client(auth=(settings.razorpay_key_id, settings.razorpay_key_secret))
    try:
        client.utility.verify_payment_signature({
            "razorpay_order_id": order_id,
            "razorpay_payment_id": payment_id,
            "razorpay_signature": signature,
        })
        return True
    except razorpay.errors.SignatureVerificationError:
        return False


def create_payment_for_order(db: Session, order: Order) -> Payment:
    existing = db.query(Payment).filter(Payment.order_id == order.id).first()
    if existing:
        return existing

    razorpay_order_id = create_razorpay_order(float(order.total_amount))
    payment = Payment(
        order_id=order.id,
        razorpay_order_id=razorpay_order_id,
        amount=order.total_amount,
        status="pending",
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment


def handle_webhook(db: Session, razorpay_order_id: str, razorpay_payment_id: str, webhook_status: str, method: str | None) -> Payment:
    payment = db.query(Payment).filter(Payment.razorpay_order_id == razorpay_order_id).first()
    if not payment:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No matching payment intent for this order")

    if payment.razorpay_payment_id == razorpay_payment_id and payment.status == "success":
        return payment

    payment.razorpay_payment_id = razorpay_payment_id
    payment.method = method
    payment.status = "success" if webhook_status == "captured" else "failed"
    payment.paid_at = datetime.now(timezone.utc) if payment.status == "success" else None

    order = db.query(Order).filter(Order.id == payment.order_id).first()

    if payment.status == "success":
        order.payment_status = "paid"

        store = db.query(Store).filter(Store.id == order.store_id).first()

        db.add(TransactionLedger(
            payment_id=payment.id,
            merchant_id=store.merchant_id,
            customer_id=order.customer_id,
            order_id=order.id,
            transaction_type="sale",
            amount=payment.amount,
            status="success",
        ))

        for item in order.items:
            inv = db.query(Inventory).filter(Inventory.store_id == order.store_id, Inventory.product_id == item.product_id).first()
            if inv:
                inv.quantity = max(0, inv.quantity - item.quantity)

        db.add(Notification(
            merchant_id=store.merchant_id,
            order_id=order.id,
            title="New order received",
            body=f"Order #{order.id} paid — ₹{payment.amount}. Accept & Pack or mark Out of Stock.",
            type="whatsapp",
        ))
        merchant = db.query(Merchant).filter(Merchant.id == store.merchant_id).first()
        if merchant and merchant.phone:
            send_order_notification_with_buttons(merchant.phone, order.id, float(payment.amount))

    else:
        order.payment_status = "failed"

    db.commit()
    db.refresh(payment)
    return payment