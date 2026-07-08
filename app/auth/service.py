import random
import secrets

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.redis_client import redis_client
from app.core.security import create_access_token, hash_password, verify_password
from app.models import Merchant, Customer


# ---------- Merchant (password-based) ----------

def register_merchant(db: Session, name: str, email: str, phone: str, password: str) -> Merchant:
    merchant = Merchant(
        name=name,
        email=email,
        phone=phone,
        password_hash=hash_password(password),
    )
    db.add(merchant)
    db.commit()
    db.refresh(merchant)
    return merchant


def authenticate_merchant(db: Session, email: str, password: str) -> Merchant | None:
    merchant = db.query(Merchant).filter(Merchant.email == email).first()
    if not merchant or not verify_password(password, merchant.password_hash):
        return None
    return merchant


def issue_merchant_token(merchant: Merchant) -> str:
    return create_access_token(subject=str(merchant.id), role="merchant")


def _reset_key(email: str) -> str:
    return f"pwreset:{email}"


def request_password_reset(email: str) -> str:
    """Generates a reset token, stores it in Redis (15 min TTL), 'sends' it via email.
    Always call this even if the email doesn't exist — don't leak which emails are registered."""
    token = secrets.token_urlsafe(24)
    redis_client.setex(_reset_key(email), 900, token)
    print(f"[DEV] Password reset token for {email}: {token}")  # TODO: real email send
    return token


def reset_password(db: Session, email: str, reset_token: str, new_password: str) -> bool:
    stored = redis_client.get(_reset_key(email))
    if stored is None or stored != reset_token:
        return False

    merchant = db.query(Merchant).filter(Merchant.email == email).first()
    if not merchant:
        return False

    merchant.password_hash = hash_password(new_password)
    db.commit()
    redis_client.delete(_reset_key(email))  # single use
    return True


def update_password(db: Session, merchant: Merchant, old_password: str, new_password: str) -> bool:
    if not verify_password(old_password, merchant.password_hash):
        return False
    merchant.password_hash = hash_password(new_password)
    db.commit()
    return True


def login_with_google(db: Session, id_token_str: str) -> Merchant:
    """
    Verifies the Google ID token SERVER-SIDE — this is the step that actually matters.
    Never trust a frontend's claim of "this user signed in with Google" without this
    verification; the frontend could be sending anything.

    Requires GOOGLE_CLIENT_ID in .env. Raises ValueError on any verification failure.
    """
    if not settings.google_client_id:
        raise ValueError("Google Sign-In is not configured on the server yet")

    from google.oauth2 import id_token as google_id_token
    from google.auth.transport import requests as google_requests

    try:
        idinfo = google_id_token.verify_oauth2_token(
            id_token_str, google_requests.Request(), settings.google_client_id
        )
    except ValueError as e:
        raise ValueError(f"Invalid Google token: {e}")

    google_id = idinfo["sub"]
    email = idinfo["email"]
    name = idinfo.get("name", email)

    # First try matching by google_id (returning Google user), then by email
    # (a merchant who registered with a password using the same email, now trying Google).
    merchant = db.query(Merchant).filter(Merchant.google_id == google_id).first()
    if not merchant:
        merchant = db.query(Merchant).filter(Merchant.email == email).first()
        if merchant:
            merchant.google_id = google_id  # link the existing account
        else:
            merchant = Merchant(
                name=name,
                email=email,
                phone="",  # not provided by Google — merchant fills this in later via Settings
                password_hash=None,
                google_id=google_id,
                is_verified=True,  # Google already verified the email
            )
            db.add(merchant)
        db.commit()
        db.refresh(merchant)

    return merchant


# ---------- Customer (OTP-based, no password) ----------

def _otp_key(email: str) -> str:
    return f"otp:{email}"


def request_customer_otp(email: str) -> str:
    """Generates and stores an OTP in Redis. Returns the OTP (for console/dev use
    until a real SMTP/SMS provider is wired in)."""
    otp = f"{random.randint(0, 999999):06d}"
    redis_client.setex(_otp_key(email), settings.otp_ttl_seconds, otp)
    # TODO: replace with real email send (smtplib) — for now, log it
    print(f"[DEV] OTP for {email}: {otp}")
    return otp


def verify_customer_otp(db: Session, email: str, otp: str) -> Customer | None:
    stored = redis_client.get(_otp_key(email))
    if stored is None or stored != otp:
        return None

    redis_client.delete(_otp_key(email))  # single use

    customer = db.query(Customer).filter(Customer.email == email).first()
    if customer is None:
        customer = Customer(email=email)
        db.add(customer)
        db.commit()
        db.refresh(customer)
    return customer


def issue_customer_token(customer: Customer) -> str:
    return create_access_token(subject=str(customer.id), role="customer")
