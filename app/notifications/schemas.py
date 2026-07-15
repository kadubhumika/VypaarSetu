from datetime import datetime

from pydantic import BaseModel


class NotificationOut(BaseModel):
    id: int
    order_id: int | None
    title: str
    body: str
    type: str
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationSummaryOut(BaseModel):
    unread_count: int
    notifications: list[NotificationOut]


class TwilioInboundWebhook(BaseModel):
    """Shape of Twilio's inbound WhatsApp webhook (form-encoded, but FastAPI parses
    it the same way here via Form(...) in the router)."""
    From: str  # e.g. "whatsapp:+919999999999"
    Body: str  # the merchant's reply text, e.g. "1" or "2"