import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Order, Payment, TransactionLedger, Inventory, Notification, Store, Merchant
from app.notifications.service import send_order_notification_with_buttons
from app.notifications.whatsapp import send_whatsapp_message


def create_razorpay_order_stub(amount: float) -> str:
    """Fallback when Razorpay credentials aren't configured yet."""
    return f"order_stub_{uuid.uuid4().hex[:14]}"


def create_razorpay_order(amount: float) -> str:
    """
    Real Razorpay order creation.

    Setup (free, test mode):
    1. Sign up at https://dashboard.razorpay.com/signup
    2. Go to Settings > API Keys > Generate Test Key
    3. Add to your .env:
         RAZORPAY_KEY_ID=rzp_test_xxxxxxxxxxxxx
         RAZORPAY_KEY_SECRET=your_test_secret
    4. pip install razorpay (already in requirements.txt)

    Without these two env vars set, falls back to a stub order id — the rest of the
    flow (webhook, ledger, inventory decrement) works identically either way, since
    they only depend on getting an order id string back.
    """
    if not (settings.razorpay_key_id and settings.razorpay_key_secret):
        return create_razorpay_order_stub(amount)

    import razorpay

    client = razorpay.Client(auth=(settings.razorpay_key_id, settings.razorpay_key_secret))
    order = client.order.create({
        "amount": int(amount * 100),  # Razorpay expects paise, not rupees
        "currency": "INR",
        "payment_capture": 1,
    })
    return order["id"]


def verify_razorpay_signature(order_id: str, payment_id: str, signature: str) -> bool:
    """
    Verifies the checkout signature Razorpay's frontend script returns after a real
    payment. This is what actually confirms the payment wasn't tampered with —
    NEVER trust a frontend payment success callback without this check.
    Needs RAZORPAY_KEY_SECRET in .env.
    """
    if not settings.razorpay_key_secret:
        return False  # can't verify without the secret — reject rather than silently trust

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
        return existing  # idempotent — don't create a duplicate payment intent

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
        # NOTE: order.status deliberately stays "created" here — payment succeeding is
        # not the same as the merchant accepting the order. The merchant still needs to
        # Accept & Pack (or mark Out of Stock) via the WhatsApp reply or the dashboard;
        # that action is what moves status to "accepted"/"cancelled".
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