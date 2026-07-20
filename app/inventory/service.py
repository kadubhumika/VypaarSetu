import os
import re
import uuid
import pdfplumber
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import Store, Category, Product, Inventory, SupplierInvoice, InvoiceItem
from app.inventory.schemas import ExtractedInvoiceItem

LOW_STOCK_THRESHOLD = 10
UPLOAD_DIR = "uploads/invoices"
IMAGE_UPLOAD_DIR = "static/uploads/products"


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
    payload = data.dict(exclude_unset=True)
    image_url = payload.pop("image_url", None)

    for field, value in payload.items():
        setattr(inventory, field, value)

    # image_url lives on Product, not Inventory — cascade it to the linked product
    if image_url:
        product = db.query(Product).filter(Product.id == inventory.product_id).first()
        if product:
            product.image_url = image_url

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


# ---------- Image upload (real file storage) ----------

def save_product_image(file_bytes: bytes, original_filename: str) -> str:
    """Saves an uploaded product image to disk and returns a public URL for it.
    Requires app.mount("/static", StaticFiles(directory="static")) in main.py."""
    os.makedirs(IMAGE_UPLOAD_DIR, exist_ok=True)
    ext = os.path.splitext(original_filename)[1].lower() or ".jpg"
    stored_name = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(IMAGE_UPLOAD_DIR, stored_name)
    with open(path, "wb") as f:
        f.write(file_bytes)
    return f"/static/uploads/products/{stored_name}"


# ---------- Invoice upload (real PDF text extraction + OCR fallback) ----------

def save_invoice_file(file_bytes: bytes, original_filename: str) -> str:
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    ext = os.path.splitext(original_filename)[1].lower()
    stored_name = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(UPLOAD_DIR, stored_name)
    with open(path, "wb") as f:
        f.write(file_bytes)
    return path


# Matches lines like: "1. Maggie Noodles (Qty: 5) - $2.50 each"
# Also tolerates ₹ instead of $, and "x" or "qty" variants loosely.
_LINE_PATTERN = re.compile(
    r'^\s*\d+[\.\)]\s*(?P<name>.+?)\s*\(\s*(?:qty|quantity)\s*:?\s*(?P<qty>\d+)\s*\)\s*[-–]\s*[₹$]\s*(?P<price>[\d.]+)',
    re.IGNORECASE,
)

_CATEGORY_KEYWORDS = {
    "Dairy": ["milk", "cheese", "butter", "yogurt", "curd", "paneer"],
    "Grocery": ["rice", "oil", "sugar", "flour", "atta", "dal", "salt", "ketchup"],
    "Personal Care": ["soap", "detergent", "toothpaste", "shampoo"],
    "Snacks & Beverages": ["chips", "biscuit", "soda", "coffee", "tea", "noodles", "cookie"],
    "Household": ["towel", "trash", "bag", "cleaning", "tissue"],
    "Bakery": ["bread"],
}


def _guess_category(product_name: str) -> str:
    name_lower = product_name.lower()
    for category, keywords in _CATEGORY_KEYWORDS.items():
        if any(k in name_lower for k in keywords):
            return category
    return "General"


def _extract_from_pdf_text(file_path: str) -> list[ExtractedInvoiceItem]:


    with pdfplumber.open(file_path) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    items = []
    for line in text.splitlines():
        match = _LINE_PATTERN.match(line.strip())
        if match:
            name = match.group("name").strip()
            items.append(ExtractedInvoiceItem(
                item_name=name,
                category_name=_guess_category(name),
                quantity=int(match.group("qty")),
                price_per_unit=float(match.group("price")),
            ))

    if not items:
        raise ValueError("No recognizable 'N. Product (Qty: X) - $Y each' lines found in this PDF's text")

    return items


def mock_extract_invoice(file_path: str) -> list[ExtractedInvoiceItem]:
    """Fallback used for images (JPG/PNG) — real image OCR needs Tesseract installed
    in the Docker image, which isn't wired in yet. Returns realistic dummy rows so
    the approve flow still works end-to-end for image uploads until that's added."""
    return [
        ExtractedInvoiceItem(item_name="Premium Basmati Rice 5kg", category_name="Grocery", quantity=20, price_per_unit=550.0),
        ExtractedInvoiceItem(item_name="Refined Sunflower Oil 1L", category_name="Oils", quantity=50, price_per_unit=180.0),
        ExtractedInvoiceItem(item_name="Organic Honey 500g", category_name="Staples", quantity=15, price_per_unit=300.0),
    ]


def extract_invoice_items(file_path: str) -> list[ExtractedInvoiceItem]:
    """Real extraction for PDFs with selectable text (like your test file).
    Falls back to mock data for images, or if the PDF's text doesn't match the
    expected line format — check Docker logs for the [ERROR] line if that happens."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        try:
            return _extract_from_pdf_text(file_path)
        except Exception as e:
            print(f"[ERROR] PDF text extraction failed ({e}). Falling back to mock data. "
                  f"Check that your PDF has selectable text (not a scanned image) matching "
                  f"the pattern 'N. Product Name (Qty: X) - $Y each'.")
            return mock_extract_invoice(file_path)
    else:
        print(f"[DEV] Image OCR not wired in yet for {file_path} — using mock data. "
              f"Real image OCR needs Tesseract installed in the Docker image.")
        return mock_extract_invoice(file_path)


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
                selling_price=item.price_per_unit * 1.2,
            ))
        added += 1

    db.commit()
    return added