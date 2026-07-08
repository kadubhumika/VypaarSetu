from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.auth import schemas, service

router = APIRouter(prefix="/customer/auth", tags=["customer-auth"])


@router.post("/request-otp")
def request_otp(payload: schemas.OTPRequest):
    service.request_customer_otp(payload.email)
    # Never reveal the OTP in the response in production — dev-only note below.
    return {"message": "OTP sent. Check console/email.", "expires_in_seconds": 300}


@router.post("/verify-otp", response_model=schemas.TokenResponse)
def verify_otp(payload: schemas.OTPVerify, db: Session = Depends(get_db)):
    customer = service.verify_customer_otp(db, payload.email, payload.otp)
    if not customer:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired OTP")

    token = service.issue_customer_token(customer)
    return schemas.TokenResponse(access_token=token)
