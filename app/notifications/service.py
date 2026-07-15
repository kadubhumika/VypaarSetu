from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import Notification, Merchant, Order, Store  # Explicitly join Store
from app.notifications.whatsapp import send_whatsapp_message

# ---------- Dashboard bell icon ----------

def list_notifications(db: Session, merchant_id: int, limit: int = 50) -> list[Notification]:
    return (
        db.query(Notification)
        .filter(Notification.merchant_id == merchant_id)
        .order_by(Notification.created_at.desc())
        .limit(limit)
        .all()
    )


def unread_count(db: Session, merchant_id: int) -> int:
    # Cleaner SQLAlchemy expression format replacing '== False'
    return db.query(Notification).filter(
        Notification.merchant_id == merchant_id,
        Notification.is_read.is_(False)
    ).count()


def mark_read(db: Session, merchant_id: int, notification_id: int) -> Notification:
    notif = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.merchant_id == merchant_id
    ).first()
    if not notif:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notification not found")
    notif.is_read = True
    db.commit()
    db.refresh(notif)
    return notif


def mark_all_read(db: Session, merchant_id: int) -> int:
    updated = (
        db.query(Notification)
        .filter(Notification.merchant_id == merchant_id, Notification.is_read.is_(False))
        .update({"is_read": True}, synchronize_session="evaluate")
    )
    db.commit()
    return updated


# ---------- WhatsApp inbound reply: "reply 1 to Accept & Pack, 2 for Out of Stock" ----------

ACCEPT_KEYWORDS = {"1", "accept", "yes", "confirm"}
OUT_OF_STOCK_KEYWORDS = {"2", "out", "out of stock", "no"}
_ACCEPTABLE_FROM_STATUS = {"created"}


def handle_whatsapp_reply(db: Session, from_phone: str, body: str) -> str:
    """
    from_phone comes in as 'whatsapp:+919999999999' from Twilio — strip the prefix.
    Returns the reply text to send back (wrapped in TwiML by the router).
    """
    phone = from_phone.replace("whatsapp:", "").strip()
    reply_text = body.strip().lower()

    merchant = db.query(Merchant).filter(Merchant.phone == phone).first()
    if not merchant:
        return "We couldn't find a VyapaarSetu merchant account linked to this number."

    # Performance Fix: Replaced .has() with an explicit flat join query
    pending_order = (
        db.query(Order)
        .join(Store, Order.store_id == Store.id)
        .filter(
            Order.status.in_(_ACCEPTABLE_FROM_STATUS),
            Store.merchant_id == merchant.id
        )
        .order_by(Order.created_at.desc())
        .first()
    )

    if not pending_order:
        return "You have no pending orders awaiting a response right now."

    if reply_text in ACCEPT_KEYWORDS:
        pending_order.status = "accepted"
        db.commit()
        return f"✅ Order #{pending_order.id} marked as Accepted & Packing. The customer has been notified."

    elif reply_text in OUT_OF_STOCK_KEYWORDS:
        pending_order.status = "cancelled"
        db.commit()
        return f"❌ Order #{pending_order.id} marked as Out of Stock and cancelled. The customer has been notified."

    else:
        return f"Sorry, I didn't understand that. For order #{pending_order.id}, reply 1 to Accept & Pack, or 2 for Out of Stock."


def send_order_notification_with_buttons(merchant_phone: str, order_id: int, amount: float) -> None:
    """Called from payments/service.py when a payment succeeds."""
    send_whatsapp_message(
        merchant_phone,
        f"🛒 New order #{order_id} — ₹{amount} paid.\n\n"
        f"Reply *1* to Accept & Pack\n"
        f"Reply *2* if Out of Stock",
    )
