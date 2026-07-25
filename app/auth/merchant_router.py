from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_merchant
from app.auth import schemas, service

router = APIRouter(prefix="/merchant/auth", tags=["merchant-auth"])


@router.get("/config")
def merchant_auth_config():
    """Client ID is meant to be public — Google's docs explicitly say so. Never expose
    a client secret this way, but there isn't one in this flow."""
    from app.core.config import settings
    return {"google_client_id": settings.google_client_id, "google_configured": bool(settings.google_client_id)}


@router.post("/register", response_model=schemas.TokenResponse)
def register(payload: schemas.MerchantRegister, db: Session = Depends(get_db)):
    from app.models import Merchant

    if db.query(Merchant).filter(Merchant.email == payload.email).first():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Email already registered")

    merchant = service.register_merchant(db, payload.name, payload.email, payload.phone, payload.password)
    token = service.issue_merchant_token(merchant)
    return schemas.TokenResponse(access_token=token)

@router.get("/me", response_model=schemas.MerchantProfileOut)
def get_my_profile(merchant=Depends(get_current_merchant)):
    return merchant


@router.patch("/me", response_model=schemas.MerchantProfileOut)
def update_my_profile(payload: schemas.MerchantProfileUpdate, db: Session = Depends(get_db), merchant=Depends(get_current_merchant)):
    return service.update_merchant_profile(db, merchant, payload)


@router.post("/login", response_model=schemas.TokenResponse)
def login(payload: schemas.MerchantLogin, db: Session = Depends(get_db)):
    merchant = service.authenticate_merchant(db, payload.email, payload.password)
    if not merchant:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")

    token = service.issue_merchant_token(merchant)
    return schemas.TokenResponse(access_token=token)


@router.post("/forgot-password")
def forgot_password(payload: schemas.ForgotPasswordRequest):
    service.request_password_reset(payload.email)
    # Always return the same message whether or not the email exists — don't leak account existence.
    return {"message": "If that email is registered, a reset link has been sent."}


@router.post("/reset-password")
def reset_password(payload: schemas.ResetPasswordRequest, db: Session = Depends(get_db)):
    ok = service.reset_password(db, payload.email, payload.reset_token, payload.new_password)
    if not ok:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired reset token")
    return {"message": "Password updated successfully"}


@router.post("/update-password")
def update_password(
    payload: schemas.UpdatePasswordRequest,
    db: Session = Depends(get_db),
    merchant=Depends(get_current_merchant),
):
    ok = service.update_password(db, merchant, payload.old_password, payload.new_password)
    if not ok:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Old password is incorrect")
    return {"message": "Password updated successfully"}


@router.post("/google", response_model=schemas.TokenResponse)
def google_login(payload: schemas.GoogleLoginRequest, db: Session = Depends(get_db)):
    try:
        merchant = service.login_with_google(db, payload.id_token)
    except ValueError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(e))

    token = service.issue_merchant_token(merchant)
    return schemas.TokenResponse(access_token=token)
