from datetime import datetime, date
from pydantic import BaseModel, Field


class SetCreditLimitRequest(BaseModel):
    customer_id: int
    credit_limit: float = Field(ge=0)


class CreditAccountOut(BaseModel):
    id: int
    customer_id: int
    customer_name: str | None
    customer_email: str
    credit_limit: float
    current_balance: float
    available_credit: float
    oldest_outstanding_date: datetime | None


class CreditTransactionOut(BaseModel):
    id: int
    order_id: int | None
    transaction_type: str
    amount: float
    balance_after: float
    due_date: date | None
    created_at: datetime

    class Config:
        from_attributes = True


class PayWithCreditRequest(BaseModel):
    order_id: int


class RepaymentRequest(BaseModel):
    amount: float = Field(gt=0)

class CustomerOptionOut(BaseModel):
    id: int
    name: str | None
    email: str


class MyCreditBalanceOut(BaseModel):
    store_id: int
    store_name: str
    credit_limit: float
    current_balance: float
    available_credit: float