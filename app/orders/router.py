from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_customer, get_current_merchant
from app.orders import schemas, service
from app.inventory.service import get_merchant_store
from app.models import Order

router = APIRouter(prefix="/orders", tags=["orders"])


# ---------- Customer ----------

@router.post("", response_model=schemas.OrderOut)
def place_order(payload: schemas.OrderCreate, db: Session = Depends(get_db), customer=Depends(get_current_customer)):
    order = service.create_order(db, customer.id, payload.store_id, payload.items)
    return service.serialize_order(db, order)


@router.get("/mine", response_model=list[schemas.OrderOut])
def my_orders(db: Session = Depends(get_db), customer=Depends(get_current_customer)):
    orders = service.list_orders_for_customer(db, customer.id)
    return [service.serialize_order(db, o) for o in orders]


# ---------- Merchant ----------

@router.get("/store", response_model=list[schemas.OrderOut])
def store_orders(db: Session = Depends(get_db), merchant=Depends(get_current_merchant)):
    store = get_merchant_store(db, merchant.id)
    if not store:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No store found for this merchant")
    orders = service.list_orders_for_store(db, store.id)
    return [service.serialize_order(db, o) for o in orders]


@router.patch("/{order_id}/status", response_model=schemas.OrderOut)
def update_status(order_id: int, payload: schemas.OrderStatusUpdate, db: Session = Depends(get_db), merchant=Depends(get_current_merchant)):
    store = get_merchant_store(db, merchant.id)
    if not store:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No store found for this merchant")

    order = db.query(Order).filter(Order.id == order_id, Order.store_id == store.id).first()
    if not order:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found")

    updated = service.update_order_status(db, order, payload.status)
    return service.serialize_order(db, updated)
