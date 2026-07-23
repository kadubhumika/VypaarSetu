"""Real WhatsApp notifications via Twilio — see earlier setup notes for signup steps."""

import time
from app.core.config import settings


def send_whatsapp_message(to_phone: str, body: str) -> bool:
    if not (settings.twilio_account_sid and settings.twilio_auth_token and settings.twilio_whatsapp_from):
        print(f"[DEV] WhatsApp (Twilio not configured) to {to_phone}: {body}")
        return False

    # Twilio requires strict E.164 — auto-fix common formatting mistakes rather than
    # silently failing on a number that's missing its country code.
    if not to_phone.startswith("+"):
        to_phone = "+91" + to_phone.lstrip("0")
        print(f"[WARN] Phone number wasn't in E.164 format — auto-corrected to {to_phone}")

    from twilio.rest import Client
    client = Client(settings.twilio_account_sid, settings.twilio_auth_token)

    last_error = None
    for attempt in range(1, 3):  # retry once — the SSL hiccup we saw is usually transient
        try:
            client.messages.create(from_=settings.twilio_whatsapp_from, to=f"whatsapp:{to_phone}", body=body)
            return True
        except Exception as e:
            last_error = e
            print(f"[WARN] Twilio send attempt {attempt} failed for {to_phone}: {e}")
            time.sleep(1)

    print(f"[ERROR] Twilio send failed after 2 attempts for {to_phone}: {last_error}")
    return False