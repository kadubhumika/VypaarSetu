import os
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import Store, Category, Product, Inventory, SupplierInvoice, InvoiceItem
from app.inventory.schemas import ExtractedInvoiceItem

LOW_STOCK_THRESHOLD = 10  # units — matches the "Low Stock" badge logic in the UI
UPLOAD_DIR = "uploads/invoices"


# ---------- Store ----------

def create_store(db: Session, merchant_id: int, data) -> Store:
    store = Store(
        merchant_id=merchant_id,
        store_name=data.store_name,
        address=data.address,
        latitude=data.latitude,
        longitude=data.longitude,
        gst_number=data.gst_number,
    )
    db.add(store)
    db.commit()
    db.refresh(store)
    return store


def get_merchant_store(db: Session, merchant_id: int) -> Store | None:
    return db.query(Store).filter(Store.merchant_id == merchant_id).first()


def update_store(db: Session, store: Store, data) -> Store:
    for field, value in data.dict(exclude_unset=True).items():
        setattr(store, field, value)
    db.commit()
    db.refresh(store)
    return store


# ---------- Category / Product helpers ----------

def get_or_create_category(db: Session, name: str) -> Category:
    category = db.query(Category).filter(Category.name.ilike(name)).first()
    if category:
        return category
    category = Category(name=name)
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def get_or_create_product(db: Session, category_id: int, name: str, brand: str | None = None) -> Product:
    query = db.query(Product).filter(Product.name.ilike(name), Product.category_id == category_id)
    if brand:
        query = query.filter(Product.brand.ilike(brand))
    product = query.first()
    if product:
        return product
    product = Product(category_id=category_id, name=name, brand=brand)
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


# ---------- Manual product add ----------

def add_product_to_inventory(db: Session, store_id: int, data) -> Inventory:
    category = get_or_create_category(db, data.category_name)
    product = get_or_create_product(db, category.id, data.name, data.brand)
    if data.barcode and not product.barcode:
        product.barcode = data.barcode
    if data.image_url and not product.image_url:
        product.image_url = data.image_url

    inventory = Inventory(
        store_id=store_id,
        product_id=product.id,
        quantity=data.quantity,
        purchase_price=data.purchase_price,
        selling_price=data.selling_price,
        expiry_date=data.expiry_date,
        manufacturing_date=data.manufacturing_date,
        batch_number=data.batch_number,
    )
    db.add(inventory)
    db.commit()
    db.refresh(inventory)
    return inventory


def update_inventory_item(db: Session, inventory: Inventory, data) -> Inventory:
    for field, value in data.dict(exclude_unset=True).items():
        setattr(inventory, field, value)
    db.commit()
    db.refresh(inventory)
    return inventory


def delete_inventory_item(db: Session, inventory: Inventory) -> None:
    db.delete(inventory)
    db.commit()


def list_inventory_cards(db: Session, store_id: int) -> list[dict]:
    rows = (
        db.query(Inventory, Product, Category)
        .join(Product, Inventory.product_id == Product.id)
        .join(Category, Product.category_id == Category.id)
        .filter(Inventory.store_id == store_id)
        .all()
    )
    return [
        {
            "inventory_id": inv.id,
            "product_id": prod.id,
            "product_name": prod.name,
            "brand": prod.brand,
            "category_name": cat.name,
            "image_url": prod.image_url,
            "quantity": inv.quantity,
            "selling_price": float(inv.selling_price),
            "is_low_stock": inv.quantity < LOW_STOCK_THRESHOLD,
            "updated_at": inv.updated_at,
        }
        for inv, prod, cat in rows
    ]


# ---------- Invoice upload (OCR pipeline) ----------

def save_invoice_file(file_bytes: bytes, original_filename: str) -> str:
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    ext = os.path.splitext(original_filename)[1].lower()
    stored_name = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(UPLOAD_DIR, stored_name)
    with open(path, "wb") as f:
        f.write(file_bytes)
    return path


def mock_extract_invoice(file_path: str) -> list[ExtractedInvoiceItem]:
    """Placeholder for the real OCR + LLM-normalization pipeline (Tesseract/EasyOCR + LLM
    cleanup, per the architecture doc). Returns realistic dummy rows so the approve flow
    can be built and tested end-to-end before OCR is wired in."""
    return [
        ExtractedInvoiceItem(item_name="Premium Basmati Rice 5kg", category_name="Grocery", quantity=20, price_per_unit=550.0),
        ExtractedInvoiceItem(item_name="Refined Sunflower Oil 1L", category_name="Oils", quantity=50, price_per_unit=180.0),
        ExtractedInvoiceItem(item_name="Organic Honey 500g", category_name="Staples", quantity=15, price_per_unit=300.0),
    ]


def create_invoice_record(db: Session, store_id: int, file_path: str) -> SupplierInvoice:
    invoice = SupplierInvoice(store_id=store_id, invoice_file=file_path)
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice


def approve_invoice(db: Session, invoice: SupplierInvoice, items: list[ExtractedInvoiceItem]) -> int:
    added = 0
    for item in items:
        category = get_or_create_category(db, item.category_name)
        product = get_or_create_product(db, category.id, item.item_name)

        db.add(InvoiceItem(
            invoice_id=invoice.id,
            product_id=product.id,
            quantity=item.quantity,
            purchase_price=item.price_per_unit,
        ))

        existing = (
            db.query(Inventory)
            .filter(Inventory.store_id == invoice.store_id, Inventory.product_id == product.id)
            .first()
        )
        if existing:
            existing.quantity += item.quantity
            existing.purchase_price = item.price_per_unit
        else:
            db.add(Inventory(
                store_id=invoice.store_id,
                product_id=product.id,
                quantity=item.quantity,
                purchase_price=item.price_per_unit,
                selling_price=item.price_per_unit * 1.2,  # simple default markup — merchant edits later
            ))
        added += 1

    db.commit()
    return added
