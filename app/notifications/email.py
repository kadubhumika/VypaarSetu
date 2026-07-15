"""
Real email sending via SMTP (works with Gmail using an App Password, or any SMTP provider).

Setup for Gmail specifically:
1. Your Google Account must have 2-Step Verification turned on
2. Go to https://myaccount.google.com/apppasswords
3. Create an app password (choose "Mail" as the app) — this is the 16-character
   value that goes in SMTP_PASSWORD, NOT your normal Gmail password
4. .env values:
     SMTP_HOST=smtp.gmail.com
     SMTP_PORT=587
     SMTP_USER=youraddress@gmail.com
     SMTP_PASSWORD=your16charapppassword

Without these configured (or if sending fails), this falls back to console logging.
"""

import smtplib
from email.mime.text import MIMEText

from app.core.config import settings


def send_email(to_email: str, subject: str, body: str) -> bool:
    if not (settings.smtp_host and settings.smtp_user and settings.smtp_password):
        print(f"[DEV] Email (SMTP not configured) to {to_email} — {subject}: {body}")
        return False

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = settings.smtp_user
    msg["To"] = to_email

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(settings.smtp_user, [to_email], msg.as_string())
        return True
    except smtplib.SMTPAuthenticationError:
        print(f"[ERROR] SMTP auth failed — check SMTP_USER/SMTP_PASSWORD (Gmail needs an App Password). Falling back to console for {to_email}: {body}")
        return False
    except (smtplib.SMTPException, OSError, TimeoutError) as e:
        print(f"[ERROR] Email send failed ({e}). Falling back to console for {to_email}: {body}")
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