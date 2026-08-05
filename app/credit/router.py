from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_merchant, get_current_customer
from app.credit import schemas, service
from app.inventory.service import get_merchant_store

router = APIRouter(prefix="/credit", tags=["credit"])


# ---------- Merchant ----------

@router.post("/limit", response_model=schemas.CreditAccountOut)
def set_credit_limit(payload: schemas.SetCreditLimitRequest, db: Session = Depends(get_db), merchant=Depends(get_current_merchant)):
    store = get_merchant_store(db, merchant.id)
    if not store:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No store found for this merchant")
    return service.set_credit_limit(db, store.id, payload.customer_id, payload.credit_limit)


@router.get("/book", response_model=list[schemas.CreditAccountOut])
def get_credit_book(db: Session = Depends(get_db), merchant=Depends(get_current_merchant)):
    store = get_merchant_store(db, merchant.id)
    if not store:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No store found for this merchant")
    return service.list_credit_book(db, store.id)


@router.post("/accounts/{account_id}/repay", response_model=schemas.CreditAccountOut)
def repay_credit(account_id: int, payload: schemas.RepaymentRequest, db: Session = Depends(get_db), merchant=Depends(get_current_merchant)):
    store = get_merchant_store(db, merchant.id)
    if not store:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No store found for this merchant")
    return service.record_repayment(db, store.id, account_id, payload.amount)


# ---------- Customer ----------
@router.get("/customers", response_model=list[schemas.CustomerOptionOut])
def get_store_customers(db: Session = Depends(get_db), merchant=Depends(get_current_merchant)):
    store = get_merchant_store(db, merchant.id)
    if not store:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No store found for this merchant")
    return service.list_store_customers(db, store.id)

@router.post("/pay-with-credit", response_model=schemas.CreditTransactionOut)
def pay_with_credit(payload: schemas.PayWithCreditRequest, db: Session = Depends(get_db), customer=Depends(get_current_customer)):
    return service.pay_order_with_credit(db, customer.id, payload.order_id)


@router.get("/my-accounts", response_model=list[schemas.MyCreditBalanceOut])
def my_credit_accounts(db: Session = Depends(get_db), customer=Depends(get_current_customer)):
    return service.get_customer_credit_accounts(db, customer.id)