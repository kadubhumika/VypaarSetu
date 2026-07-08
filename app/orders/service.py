from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import Order, OrderItem, Inventory, Product, Store, Customer
from app.orders.schemas import ALLOWED_STATUS_TRANSITIONS


def create_order(db: Session, customer_id: int, store_id: int, items: list) -> Order:
    if not items:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Order must have at least one item")

    order = Order(customer_id=customer_id, store_id=store_id, total_amount=0, status="created", payment_status="pending")
    db.add(order)
    db.flush()  # get order.id without committing yet

    total = 0.0
    for item in items:
        inventory = (
            db.query(Inventory)
            .filter(Inventory.store_id == store_id, Inventory.product_id == item.product_id)
            .first()
        )
        if not inventory:
            db.rollback()
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Product {item.product_id} not found in this store")
        if inventory.quantity < item.quantity:
            db.rollback()
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Insufficient stock for product {item.product_id}")

        price = float(inventory.selling_price)
        subtotal = price * item.quantity
        total += subtotal

        db.add(OrderItem(order_id=order.id, product_id=item.product_id, quantity=item.quantity, price=price, subtotal=subtotal))

    order.total_amount = total
    db.commit()
    db.refresh(order)
    return order


def serialize_order(db: Session, order: Order) -> dict:
    store = db.query(Store).filter(Store.id == order.store_id).first()
    customer = db.query(Customer).filter(Customer.id == order.customer_id).first()
    items_out = []
    for item in order.items:
        product = db.query(Product).filter(Product.id == item.product_id).first()
        items_out.append({
            "product_id": item.product_id,
            "product_name": product.name if product else "Unknown",
            "quantity": item.quantity,
            "price": float(item.price),
            "subtotal": float(item.subtotal),
        })
    return {
        "id": order.id,
        "store_id": order.store_id,
        "store_name": store.store_name if store else "",
        "customer_id": order.customer_id,
        "customer_name": customer.name if customer else None,
        "status": order.status,
        "payment_status": order.payment_status,
        "total_amount": float(order.total_amount),
        "items": items_out,
        "created_at": order.created_at,
    }


def list_orders_for_store(db: Session, store_id: int) -> list[Order]:
    return db.query(Order).filter(Order.store_id == store_id).order_by(Order.created_at.desc()).all()


def list_orders_for_customer(db: Session, customer_id: int) -> list[Order]:
    return db.query(Order).filter(Order.customer_id == customer_id).order_by(Order.created_at.desc()).all()


def update_order_status(db: Session, order: Order, new_status: str) -> Order:
    allowed_next = ALLOWED_STATUS_TRANSITIONS.get(order.status, set())
    if new_status not in allowed_next:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Cannot move order from '{order.status}' to '{new_status}'. Allowed: {sorted(allowed_next) or 'none'}",
        )
    order.status = new_status
    db.commit()
    db.refresh(order)
    return order
