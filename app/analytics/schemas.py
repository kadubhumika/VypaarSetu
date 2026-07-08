from pydantic import BaseModel


class BestSellerOut(BaseModel):
    product_name: str
    units_sold: int
    revenue: float


class CategorySalesOut(BaseModel):
    category_name: str
    revenue: float


class WeeklySalesPointOut(BaseModel):
    day: str  # "Mon", "Tue", ...
    revenue: float


class MerchantDashboardOut(BaseModel):
    todays_revenue: float
    todays_orders: int
    total_products: int
    low_stock_items: int
    monthly_revenue: float
    total_customers: int
    total_profit: float
    pending_orders: int
    weekly_sales: list[WeeklySalesPointOut]
    sales_by_category: list[CategorySalesOut]
    best_sellers: list[BestSellerOut]