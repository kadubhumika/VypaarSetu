from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import TransactionLedger, Order, Inventory, Product, Category, OrderItem
from app.inventory.service import LOW_STOCK_THRESHOLD


def _day_bounds(dt: datetime) -> tuple[datetime, datetime]:
    start = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)


def get_merchant_dashboard(db: Session, merchant_id: int, store_id: int) -> dict:
    now = datetime.now(timezone.utc)
    today_start, today_end = _day_bounds(now)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Today's revenue — from the immutable ledger, the single source of truth
    todays_revenue = (
        db.query(func.coalesce(func.sum(TransactionLedger.amount), 0))
        .filter(
            TransactionLedger.merchant_id == merchant_id,
            TransactionLedger.status == "success",
            TransactionLedger.created_at >= today_start,
            TransactionLedger.created_at < today_end,
        )
        .scalar()
    )

    todays_orders = (
        db.query(func.count(Order.id))
        .filter(Order.store_id == store_id, Order.created_at >= today_start, Order.created_at < today_end)
        .scalar()
    )

    total_products = db.query(func.count(Inventory.id)).filter(Inventory.store_id == store_id).scalar()

    low_stock_items = (
        db.query(func.count(Inventory.id))
        .filter(Inventory.store_id == store_id, Inventory.quantity < LOW_STOCK_THRESHOLD)
        .scalar()
    )

    monthly_revenue = (
        db.query(func.coalesce(func.sum(TransactionLedger.amount), 0))
        .filter(
            TransactionLedger.merchant_id == merchant_id,
            TransactionLedger.status == "success",
            TransactionLedger.created_at >= month_start,
        )
        .scalar()
    )

    total_customers = (
        db.query(func.count(func.distinct(Order.customer_id))).filter(Order.store_id == store_id).scalar()
    )

    # Profit = sum(selling_price - purchase_price) * quantity across paid order items
    profit_rows = (
        db.query(OrderItem.quantity, OrderItem.price, Inventory.purchase_price)
        .join(Order, OrderItem.order_id == Order.id)
        .join(Inventory, (Inventory.product_id == OrderItem.product_id) & (Inventory.store_id == Order.store_id))
        .filter(Order.store_id == store_id, Order.payment_status == "paid")
        .all()
    )
    total_profit = sum((float(price) - float(purchase_price)) * qty for qty, price, purchase_price in profit_rows)

    pending_orders = (
        db.query(func.count(Order.id))
        .filter(Order.store_id == store_id, Order.status.in_(["created", "accepted", "packed"]))
        .scalar()
    )

    # Weekly sales — last 7 days, from the ledger
    week_start = today_start - timedelta(days=6)
    weekly_rows = (
        db.query(func.date(TransactionLedger.created_at), func.sum(TransactionLedger.amount))
        .filter(
            TransactionLedger.merchant_id == merchant_id,
            TransactionLedger.status == "success",
            TransactionLedger.created_at >= week_start,
        )
        .group_by(func.date(TransactionLedger.created_at))
        .all()
    )
    revenue_by_date = {str(d): float(r) for d, r in weekly_rows}
    weekly_sales = []
    for i in range(7):
        day = week_start + timedelta(days=i)
        weekly_sales.append({"day": day.strftime("%a"), "revenue": revenue_by_date.get(str(day.date()), 0.0)})

    # Sales by category
    category_rows = (
        db.query(Category.name, func.sum(OrderItem.subtotal))
        .join(Product, Product.category_id == Category.id)
        .join(OrderItem, OrderItem.product_id == Product.id)
        .join(Order, Order.id == OrderItem.order_id)
        .filter(Order.store_id == store_id, Order.payment_status == "paid")
        .group_by(Category.name)
        .all()
    )
    sales_by_category = [{"category_name": name, "revenue": float(total)} for name, total in category_rows]

    best_seller_rows = (
        db.query(Product.name, func.sum(OrderItem.quantity), func.sum(OrderItem.subtotal))
        .join(OrderItem, OrderItem.product_id == Product.id)
        .join(Order, Order.id == OrderItem.order_id)
        .filter(Order.store_id == store_id, Order.payment_status == "paid")
        .group_by(Product.name)
        .order_by(func.sum(OrderItem.quantity).desc())
        .limit(5)
        .all()
    )
    best_sellers = [{"product_name": name, "units_sold": int(units), "revenue": float(rev)} for name, units, rev in best_seller_rows]

    return {
        "todays_revenue": float(todays_revenue),
        "todays_orders": todays_orders,
        "total_products": total_products,
        "low_stock_items": low_stock_items,
        "monthly_revenue": float(monthly_revenue),
        "total_customers": total_customers,
        "total_profit": total_profit,
        "pending_orders": pending_orders,
        "weekly_sales": weekly_sales,
        "sales_by_category": sales_by_category,
        "best_sellers": best_sellers,
    }