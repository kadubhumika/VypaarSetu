from fastapi import APIRouter, Depends, Form, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_merchant
from app.notifications import schemas, service

router = APIRouter(prefix="/notifications", tags=["notifications"])


# ---------- Dashboard bell icon (merchant-facing) ----------

@router.get("", response_model=schemas.NotificationSummaryOut)
def list_my_notifications(db: Session = Depends(get_db), merchant=Depends(get_current_merchant)):
    notifications = service.list_notifications(db, merchant.id)
    return schemas.NotificationSummaryOut(
        unread_count=service.unread_count(db, merchant.id),
        notifications=notifications,
    )


@router.patch("/{notification_id}/read", response_model=schemas.NotificationOut)
def mark_notification_read(notification_id: int, db: Session = Depends(get_db), merchant=Depends(get_current_merchant)):
    return service.mark_read(db, merchant.id, notification_id)


@router.patch("/read-all")
def mark_all_notifications_read(db: Session = Depends(get_db), merchant=Depends(get_current_merchant)):
    count = service.mark_all_read(db, merchant.id)
    return {"marked_read": count}


# ---------- Twilio inbound webhook (Twilio calls this, not your frontend) ----------

@router.post("/whatsapp-inbound")
async def whatsapp_inbound_webhook(
    From: str = Form(...),
    Body: str = Form(...),
    db: Session = Depends(get_db),
):
    """
    Point your Twilio WhatsApp Sandbox's 'WHEN A MESSAGE COMES IN' webhook at:
        https://your-domain/notifications/whatsapp-inbound
    (Twilio Console > Messaging > Try it out > Send a WhatsApp message > Sandbox Settings)

    Twilio expects a TwiML XML response to acknowledge receipt.
    """
    reply_text = service.handle_whatsapp_reply(db, From, Body)

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response><Message>{reply_text}</Message></Response>"""

    return Response(content=twiml, media_type="application/xml")