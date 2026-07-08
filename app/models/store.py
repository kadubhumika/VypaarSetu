from datetime import datetime, timezone

from sqlalchemy import String, Float, DateTime, ForeignKey, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Store(Base):
    __tablename__ = "stores"

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), nullable=False, index=True)
    store_name: Mapped[str] = mapped_column(String(150), nullable=False)
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    address: Mapped[str] = mapped_column(String(300), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    gst_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    opening_time: Mapped[str | None] = mapped_column(Time, nullable=True)
    closing_time: Mapped[str | None] = mapped_column(Time, nullable=True)
    rating: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    merchant = relationship("Merchant", back_populates="stores")
    inventory = relationship("Inventory", back_populates="store", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="store")
    reviews = relationship("Review", back_populates="store", cascade="all, delete-orphan")
    supplier_invoices = relationship("SupplierInvoice", back_populates="store", cascade="all, delete-orphan")