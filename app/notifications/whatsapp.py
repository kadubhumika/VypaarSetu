"""
Real WhatsApp notifications via Twilio.

Setup (free):
1. Sign up at https://www.twilio.com/try-twilio (free trial gives test credit)
2. Go to Console > Messaging > Try it out > Send a WhatsApp message
   -> this activates the Twilio Sandbox for WhatsApp on a shared number
3. From your phone, WhatsApp the join code Twilio shows you to their sandbox number
   -> this opts your phone in to receive sandbox messages
4. Copy your Account SID and Auth Token from the Console dashboard
5. Add to your .env:
     TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
     TWILIO_AUTH_TOKEN=your_auth_token
     TWILIO_WHATSAPP_FROM=whatsapp:+14155238886   (the sandbox number, keep the whatsapp: prefix)
6. pip install twilio  (already in requirements.txt below)

Without these three env vars set, this module silently falls back to printing
to the console — exactly what you had before, so nothing breaks if you haven't
set up Twilio yet.
"""

from app.core.config import settings


def send_whatsapp_message(to_phone: str, body: str) -> bool:
    """
    to_phone must be in E.164 format, e.g. '+919999999999' (no 'whatsapp:' prefix —
    this function adds it). Returns True if a real send was attempted, False if it
    fell back to console logging (e.g. credentials not configured yet).
    """
    if not (settings.twilio_account_sid and settings.twilio_auth_token and settings.twilio_whatsapp_from):
        print(f"[DEV] WhatsApp (Twilio not configured) to {to_phone}: {body}")
        return False

    try:
        from twilio.rest import Client

        client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        client.messages.create(
            from_=settings.twilio_whatsapp_from,
            to=f"whatsapp:{to_phone}",
            body=body,
        )
        return True
    except Exception as e:
        # Never let a notification failure break the payment/order flow — log and move on.
        print(f"[ERROR] Twilio send failed for {to_phone}: {e}")
        return False
