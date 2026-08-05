from datetime import datetime, timezone, timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import (
    CreditAccount, CreditTransaction, Customer, Store, Order, Payment,
    TransactionLedger, Inventory, Notification, Merchant,
)
from app.notifications.service import send_order_notification_with_buttons
import anyio
from app.core.ws_manager import manager

CREDIT_DUE_DAYS = 30


def _account_to_dict(db: Session, account: CreditAccount) -> dict:
    customer = db.query(Customer).filter(Customer.id == account.customer_id).first()
    oldest = (
        db.query(CreditTransaction)
        .filter(CreditTransaction.credit_account_id == account.id, CreditTransaction.transaction_type == "credit_extended")
        .order_by(CreditTransaction.created_at.asc())
        .first()
    )
    return {
        "id": account.id,
        "customer_id": customer.id,
        "customer_name": customer.name,
        "customer_email": customer.email,
        "credit_limit": float(account.credit_limit),
        "current_balance": float(account.current_balance),
        "available_credit": float(account.credit_limit) - float(account.current_balance),
        "oldest_outstanding_date": oldest.created_at if oldest else None,
    }


def get_or_create_credit_account(db: Session, customer_id: int, store_id: int) -> CreditAccount:
    account = db.query(CreditAccount).filter(CreditAccount.customer_id == customer_id, CreditAccount.store_id == store_id).first()
    if not account:
        account = CreditAccount(customer_id=customer_id, store_id=store_id, credit_limit=0, current_balance=0)
        db.add(account)
        db.commit()
        db.refresh(account)
    return account


def set_credit_limit(db: Session, store_id: int, customer_id: int, credit_limit: float) -> dict:
    account = get_or_create_credit_account(db, customer_id, store_id)
    account.credit_limit = credit_limit
    db.commit()
    db.refresh(account)
    return _account_to_dict(db, account)


def list_credit_book(db: Session, store_id: int) -> list[dict]:
    accounts = (
        db.query(CreditAccount)
        .filter(CreditAccount.store_id == store_id, CreditAccount.current_balance > 0)
        .order_by(CreditAccount.current_balance.desc())
        .all()
    )
    return [_account_to_dict(db, a) for a in accounts]


def pay_order_with_credit(db: Session, customer_id: int, order_id: int) -> CreditTransaction:
    order = db.query(Order).filter(Order.id == order_id, Order.customer_id == customer_id).first()
    if not order:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found")
    if order.payment_status != "pending":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Order payment already '{order.payment_status}'")

    if db.query(Payment).filter(Payment.order_id == order.id).first():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "A payment already exists for this order")

    account = get_or_create_credit_account(db, customer_id, order.store_id)
    amount = float(order.total_amount)
    available = float(account.credit_limit) - float(account.current_balance)
    if amount > available:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Insufficient credit — available ₹{available:.2f}, order total ₹{amount:.2f}. Ask the merchant to raise your credit limit.",
        )

    # Same Payment row shape a real Razorpay charge would create — this is what lets
    # the rest of the architecture (ledger, analytics, notifications) work unchanged.
    payment = Payment(
        order_id=order.id,
        razorpay_order_id=None,
        razorpay_payment_id=None,
        amount=order.total_amount,
        status="success",
        method="credit",
        paid_at=datetime.now(timezone.utc),
    )
    db.add(payment)
    db.flush()

    order.payment_status = "credit"  # distinct from "paid" so the Udhaar Book can tell them apart

    account.current_balance = float(account.current_balance) + amount
    credit_txn = CreditTransaction(
        credit_account_id=account.id,
        order_id=order.id,
        transaction_type="credit_extended",
        amount=amount,
        balance_after=account.current_balance,
        due_date=(datetime.now(timezone.utc) + timedelta(days=CREDIT_DUE_DAYS)).date(),
    )
    db.add(credit_txn)

    store = db.query(Store).filter(Store.id == order.store_id).first()

    # Revenue is recognized at time of sale, same as standard retail accounting for
    # credit sales — this is why analytics needs zero changes to include Udhaar sales.
    db.add(TransactionLedger(
        payment_id=payment.id,
        merchant_id=store.merchant_id,
        customer_id=order.customer_id,
        order_id=order.id,
        transaction_type="sale",
        amount=amount,
        status="success",
    ))

    for item in order.items:
        inv = db.query(Inventory).filter(Inventory.store_id == order.store_id, Inventory.product_id == item.product_id).first()
        if inv:
            inv.quantity = max(0, inv.quantity - item.quantity)

    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    db.add(Notification(
        merchant_id=store.merchant_id,
        order_id=order.id,
        title="New order — paid on Udhaar (credit)",
        body=f"Order #{order.id} — ₹{amount} added to {customer.name or customer.email}'s credit account. Accept & Pack or mark Out of Stock.",
        type="whatsapp",
    ))
    merchant = db.query(Merchant).filter(Merchant.id == store.merchant_id).first()
    if merchant and merchant.phone:
        send_order_notification_with_buttons(merchant.phone, order.id, amount)

    try:
        anyio.from_thread.run(manager.send_to_merchant, store.merchant_id, {
            "type": "new_order",
            "order_id": order.id,
            "amount": amount,
        })
    except Exception:
        pass

    db.commit()
    db.refresh(credit_txn)
    return credit_txn


def record_repayment(db: Session, store_id: int, account_id: int, amount: float) -> dict:
    account = db.query(CreditAccount).filter(CreditAccount.id == account_id, CreditAccount.store_id == store_id).first()
    if not account:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Credit account not found")
    if amount > float(account.current_balance):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Repayment (₹{amount}) exceeds outstanding balance (₹{account.current_balance})")

    account.current_balance = float(account.current_balance) - amount
    db.add(CreditTransaction(
        credit_account_id=account.id,
        order_id=None,
        transaction_type="repayment",
        amount=amount,
        balance_after=account.current_balance,
        due_date=None,
    ))
    db.commit()
    db.refresh(account)
    return _account_to_dict(db, account)

def list_store_customers(db: Session, store_id: int) -> list[dict]:

    from app.models import Order

    rows = (
        db.query(Customer)
        .join(Order, Order.customer_id == Customer.id)
        .filter(Order.store_id == store_id)
        .distinct()
        .all()
    )
    return [{"id": c.id, "name": c.name, "email": c.email} for c in rows]


def get_customer_credit_accounts(db: Session, customer_id: int) -> list[dict]:
    rows = (
        db.query(CreditAccount, Store)
        .join(Store, CreditAccount.store_id == Store.id)
        .filter(CreditAccount.customer_id == customer_id)
        .all()
    )
    return [
        {
            "store_id": store.id,
            "store_name": store.store_name,
            "credit_limit": float(account.credit_limit),
            "current_balance": float(account.current_balance),
            "available_credit": float(account.credit_limit) - float(account.current_balance),
        }
        for account, store in rows
    ]