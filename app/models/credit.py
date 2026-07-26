from datetime import datetime, timezone, date

from sqlalchemy import Numeric, String, DateTime, Date, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class CreditAccount(Base):
    """One row per (customer, store) pair — tracks how much a customer owes a
    specific store on credit ('udhaar'), and the limit the merchant has set for them."""

    __tablename__ = "credit_accounts"
    __table_args__ = (UniqueConstraint("customer_id", "store_id", name="uq_credit_account_customer_store"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False, index=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False, index=True)
    credit_limit: Mapped[float] = mapped_column(Numeric(10, 2), default=0, nullable=False)
    current_balance: Mapped[float] = mapped_column(Numeric(10, 2), default=0, nullable=False)  # amount currently owed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    customer = relationship("Customer")
    store = relationship("Store")
    transactions = relationship("CreditTransaction", back_populates="account", cascade="all, delete-orphan")


class CreditTransaction(Base):
    """Immutable ledger, same philosophy as TransactionLedger — every credit
    extension or repayment is one row, never edited or deleted."""

    __tablename__ = "credit_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    credit_account_id: Mapped[int] = mapped_column(ForeignKey("credit_accounts.id"), nullable=False, index=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"), nullable=True)  # null for a standalone repayment
    transaction_type: Mapped[str] = mapped_column(String(20), nullable=False)  # "credit_extended" | "repayment"
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    balance_after: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)  # only set for credit_extended
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    account = relationship("CreditAccount", back_populates="transactions")
    order = relationship("Order")