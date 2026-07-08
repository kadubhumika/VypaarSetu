from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models import Merchant, Customer

bearer_scheme = HTTPBearer()


def _decode(credentials: HTTPAuthorizationCredentials) -> dict:
    try:
        return decode_access_token(credentials.credentials)
    except JWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")


def get_current_merchant(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Merchant:
    payload = _decode(credentials)
    if payload.get("role") != "merchant":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Merchant account required")

    merchant = db.query(Merchant).filter(Merchant.id == int(payload["sub"])).first()
    if not merchant:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Merchant not found")
    return merchant


def get_current_customer(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Customer:
    payload = _decode(credentials)
    if payload.get("role") != "customer":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Customer account required")

    customer = db.query(Customer).filter(Customer.id == int(payload["sub"])).first()
    if not customer:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Customer not found")
    return customer
