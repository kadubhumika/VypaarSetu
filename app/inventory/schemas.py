from datetime import date, datetime

from pydantic import BaseModel, Field


# --- Store ---
class StoreCreate(BaseModel):
    store_name: str
    address: str
    latitude: float
    longitude: float
    gst_number: str | None = None


class StoreUpdate(BaseModel):
    store_name: str | None = None
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    gst_number: str | None = None
    logo_url: str | None = None


class StoreOut(BaseModel):
    id: int
    store_name: str
    address: str
    latitude: float
    longitude: float
    logo_url: str | None
    rating: float

    class Config:
        from_attributes = True


# --- Category / Product ---
class CategoryOut(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True


class ProductCreate(BaseModel):
    category_name: str  # matched or created on the fly — merchant shouldn't need a category_id
    name: str
    brand: str | None = None
    barcode: str | None = None
    description: str | None = None
    image_url: str | None = None
    quantity: int = Field(ge=0)
    purchase_price: float = Field(ge=0)
    selling_price: float = Field(ge=0)
    expiry_date: date | None = None
    manufacturing_date: date | None = None
    batch_number: str | None = None


class ProductUpdate(BaseModel):
    quantity: int | None = Field(default=None, ge=0)
    selling_price: float | None = Field(default=None, ge=0)
    purchase_price: float | None = Field(default=None, ge=0)
    expiry_date: date | None = None
    batch_number: str | None = None
    image_url: str | None = None

# --- Inventory card view — the shape the "Store Inventory" screen renders ---
class InventoryCardOut(BaseModel):
    inventory_id: int
    product_id: int
    product_name: str
    brand: str | None
    category_name: str
    image_url: str | None
    quantity: int
    selling_price: float
    is_low_stock: bool  # computed, threshold-based — not a stored column
    updated_at: datetime

    class Config:
        from_attributes = True


# --- Invoice upload (OCR pipeline) ---
ALLOWED_INVOICE_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
MAX_INVOICE_SIZE_MB = 10


class ExtractedInvoiceItem(BaseModel):
    """One row of the 'Extracted Products Preview' table — editable before approval."""
    item_name: str
    category_name: str
    quantity: int = Field(ge=1)
    price_per_unit: float = Field(ge=0)

    @property
    def total(self) -> float:
        return self.quantity * self.price_per_unit


class InvoiceUploadResponse(BaseModel):
    invoice_id: int
    file_name: str
    extracted_items: list[ExtractedInvoiceItem]
    total_items: int
    total_value: float


class InvoiceApproveRequest(BaseModel):
    """Merchant confirms (possibly edited) items before they're written to inventory."""
    items: list[ExtractedInvoiceItem]


class InvoiceApproveResponse(BaseModel):
    invoice_id: int
    items_added: int
    message: str = "Products added to inventory"
