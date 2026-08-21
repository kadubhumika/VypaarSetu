import requests
from app.core.config import settings


def send_email(to_email: str, subject: str, body: str) -> bool:
    if not settings.smtp_password:
        print(f"[DEV] Resend API Key is missing! Check SMTP_PASSWORD variable. Recipient: {to_email}")
        return False

    try:
        # We add clear headers to bypass Cloudflare security rules
        headers = {
            "Authorization": f"Bearer {settings.smtp_password}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "VyapaarSetuBackend/1.0.0 (Python-Requests)"
        }

        payload = {
            "from": "onboarding@resend.dev",
            "to": to_email,
            "subject": subject,
            "text": body,
        }

        response = requests.post(
            "https://api.resend.com/emails",
            headers=headers,
            json=payload,
            timeout=10
        )

        if response.status_code >= 200 and response.status_code < 300:
            print(f"[SUCCESS] Email sent successfully via Resend API to {to_email}!")
            return True

        print(f"[ERROR] Resend API rejected email. Status code: {response.status_code}. Response: {response.text}")
        return False

    except Exception as e:
        print(f"[ERROR] Email network fail ({e}). Falling back to console for {to_email}: {body}")
        return False


def send_otp_email(to_email: str, otp: str) -> bool:
    return send_email(
        to_email,
        "Your VyapaarSetu login code",
        f"Your one-time login code is: {otp}\n\nThis code expires in 5 minutes. "
        f"If you didn't request this, you can safely ignore this email.",
    )


def send_password_reset_email(to_email: str, reset_token: str) -> bool:
    return send_email(
        to_email,
        "Reset your VyapaarSetu password",
        f"Your password reset code is: {reset_token}\n\nThis code expires in 15 minutes. "
        f"If you didn't request this, you can safely ignore this email.",
    )
