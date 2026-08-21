import smtplib
import socket
from email.mime.text import MIMEText

from app.core.config import settings


def _connect_smtp_ipv4_ssl(host: str, port: int, timeout: int = 10) -> smtplib.SMTP_SSL:
    # Keeps your custom IPv4 resolving logic but upgrades it to secure SSL for Port 465
    addr_info = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
    ipv4_address = addr_info[0][4][0]

    # Use SMTP_SSL instead of SMTP for port 465
    smtp = smtplib.SMTP_SSL(timeout=timeout)
    smtp.connect(ipv4_address, port)

    smtp.ehlo(host)
    return smtp


def send_email(to_email: str, subject: str, body: str) -> bool:
    if not (settings.smtp_host and settings.smtp_user and settings.smtp_password):
        print(f"[DEV] Email (SMTP not configured) to {to_email} — {subject}: {body}")
        return False

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = settings.smtp_user
    msg["To"] = to_email

    try:
        # Connect using the new SSL helper function
        server = _connect_smtp_ipv4_ssl(settings.smtp_host, int(settings.smtp_port))

        # REMOVED server.starttls() because Port 465 is already encrypted!

        server.login(settings.smtp_user, settings.smtp_password)
        server.sendmail(settings.smtp_user, [to_email], msg.as_string())
        server.quit()
        return True
    except smtplib.SMTPAuthenticationError:
        print(
            f"[ERROR] SMTP auth failed — check SMTP_USER/SMTP_PASSWORD (Gmail needs an App Password). Falling back to console for {to_email}: {body}")
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
