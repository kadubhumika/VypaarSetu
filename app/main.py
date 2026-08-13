import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from starlette.staticfiles import StaticFiles
from app.credit.router import router as credit_router
from app.core.database import SessionLocal
from app.core.redis_client import redis_client
from app.auth.merchant_router import router as merchant_auth_router
from app.auth.customer_router import router as customer_auth_router
from app.inventory.router import router as inventory_router
from app.orders.router import router as orders_router
from app.payments.router import router as payments_router
from app.analytics.router import router as analytics_router
from app.customers.router import router as customers_router
from app.notifications.router import router as notifications_router


app = FastAPI(title="VyapaarSetu API", version="0.1.0")

os.makedirs("static/uploads/products", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "https://vypaarsetu-1.onrender.com",     # Your Frontend URL
        "https://vypaarsetu-p1xs.onrender.com",  # Your Backend URL
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(merchant_auth_router)
app.include_router(customer_auth_router)
app.include_router(inventory_router)
app.include_router(orders_router)
app.include_router(payments_router)
app.include_router(analytics_router)
app.include_router(customers_router)
app.include_router(notifications_router)
app.include_router(credit_router)

@app.get("/")
def read_root():
    return {
        "status": "online",
        "message": "Welcome to VyapaarSetu API. Visit /docs for the interactive API layout."
    }



@app.get("/health")
def health_check():
    db_ok, redis_ok = False, False
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        db_ok = True
    except Exception:
        db_ok = False
    try:
        redis_ok = redis_client.ping()
    except Exception:
        redis_ok = False
    return {"status": "ok" if db_ok and redis_ok else "degraded", "database": db_ok, "redis": redis_ok}