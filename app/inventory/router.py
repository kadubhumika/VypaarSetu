import os

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_merchant
from app.inventory import schemas, service
from app.models import Store, Inventory, SupplierInvoice

router = APIRouter(tags=["inventory"])


def _get_store_or_404(db: Session, merchant_id: int) -> Store:
    store = service.get_merchant_store(db, merchant_id)
    if not store:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Create a store before managing inventory")
    return store


@router.post("/stores", response_model=schemas.StoreOut)
def create_store(payload: schemas.StoreCreate, db: Session = Depends(get_db), merchant=Depends(get_current_merchant)):
    if service.get_merchant_store(db, merchant.id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Store already exists for this merchant")
    return service.create_store(db, merchant.id, payload)


@router.get("/stores/me", response_model=schemas.StoreOut)
def get_my_store(db: Session = Depends(get_db), merchant=Depends(get_current_merchant)):
    return _get_store_or_404(db, merchant.id)


@router.patch("/stores/me", response_model=schemas.StoreOut)
def update_my_store(payload: schemas.StoreUpdate, db: Session = Depends(get_db), merchant=Depends(get_current_merchant)):
    store = _get_store_or_404(db, merchant.id)
    return service.update_store(db, store, payload)


@router.post("/inventory/upload-invoice", response_model=schemas.InvoiceUploadResponse)
async def upload_invoice(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    merchant=Depends(get_current_merchant),
):
    store = _get_store_or_404(db, merchant.id)

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in schemas.ALLOWED_INVOICE_EXTENSIONS:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(schemas.ALLOWED_INVOICE_EXTENSIONS))}",
        )

    contents = await file.read()
    size_mb = len(contents) / (1024 * 1024)
    if size_mb > schemas.MAX_INVOICE_SIZE_MB:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"File too large ({size_mb:.1f}MB). Max {schemas.MAX_INVOICE_SIZE_MB}MB")

    file_path = service.save_invoice_file(contents, file.filename)
    invoice = service.create_invoice_record(db, store.id, file_path)
    extracted = service.extract_invoice_items(file_path)  # <-- real extraction now, not mock

    return schemas.InvoiceUploadResponse(
        invoice_id=invoice.id,
        file_name=file.filename,
        extracted_items=extracted,
        total_items=len(extracted),
        total_value=sum(i.total for i in extracted),
    )


@router.post("/inventory/invoices/{invoice_id}/approve", response_model=schemas.InvoiceApproveResponse)
def approve_invoice(
    invoice_id: int,
    payload: schemas.InvoiceApproveRequest,
    db: Session = Depends(get_db),
    merchant=Depends(get_current_merchant),
):
    store = _get_store_or_404(db, merchant.id)
    invoice = db.query(SupplierInvoice).filter(SupplierInvoice.id == invoice_id, SupplierInvoice.store_id == store.id).first()
    if not invoice:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invoice not found")

    added = service.approve_invoice(db, invoice, payload.items)
    return schemas.InvoiceApproveResponse(invoice_id=invoice.id, items_added=added)


@router.post("/inventory/invoices/{invoice_id}/cancel")
def cancel_invoice(invoice_id: int, db: Session = Depends(get_db), merchant=Depends(get_current_merchant)):
    store = _get_store_or_404(db, merchant.id)
    invoice = db.query(SupplierInvoice).filter(SupplierInvoice.id == invoice_id, SupplierInvoice.store_id == store.id).first()
    if not invoice:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invoice not found")
    db.delete(invoice)
    db.commit()
    return {"message": "Invoice discarded"}


@router.post("/inventory/products", response_model=schemas.InventoryCardOut)
def add_product(payload: schemas.ProductCreate, db: Session = Depends(get_db), merchant=Depends(get_current_merchant)):
    store = _get_store_or_404(db, merchant.id)
    inventory = service.add_product_to_inventory(db, store.id, payload)
    cards = service.list_inventory_cards(db, store.id)
    return next(c for c in cards if c["inventory_id"] == inventory.id)


@router.get("/inventory", response_model=list[schemas.InventoryCardOut])
def list_inventory(db: Session = Depends(get_db), merchant=Depends(get_current_merchant)):
    store = _get_store_or_404(db, merchant.id)
    return service.list_inventory_cards(db, store.id)


@router.patch("/inventory/{inventory_id}", response_model=schemas.InventoryCardOut)
def update_inventory(inventory_id: int, payload: schemas.ProductUpdate, db: Session = Depends(get_db), merchant=Depends(get_current_merchant)):
    store = _get_store_or_404(db, merchant.id)
    inventory = db.query(Inventory).filter(Inventory.id == inventory_id, Inventory.store_id == store.id).first()
    if not inventory:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Inventory item not found")
    service.update_inventory_item(db, inventory, payload)
    cards = service.list_inventory_cards(db, store.id)
    return next(c for c in cards if c["inventory_id"] == inventory_id)


@router.delete("/inventory/{inventory_id}")
def delete_inventory(inventory_id: int, db: Session = Depends(get_db), merchant=Depends(get_current_merchant)):
    store = _get_store_or_404(db, merchant.id)
    inventory = db.query(Inventory).filter(Inventory.id == inventory_id, Inventory.store_id == store.id).first()
    if not inventory:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Inventory item not found")
    service.delete_inventory_item(db, inventory)
    return {"message": "Item removed from inventory"}


# ---------- Product image upload (new) ----------

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_IMAGE_SIZE_MB = 5


@router.post("/inventory/upload-image")
async def upload_product_image(
    file: UploadFile = File(...),
    merchant=Depends(get_current_merchant),
):
    """Generic image upload — returns a URL you then PATCH onto an inventory item's
    image_url field. Works for the 'Upload Image' button; for 'Camera', the frontend
    file input uses capture="environment" which opens the device camera directly
    on mobile browsers and calls this same endpoint."""
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unsupported image type '{ext}'. Allowed: {', '.join(sorted(ALLOWED_IMAGE_EXTENSIONS))}")

    contents = await file.read()
    size_mb = len(contents) / (1024 * 1024)
    if size_mb > MAX_IMAGE_SIZE_MB:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Image too large ({size_mb:.1f}MB). Max {MAX_IMAGE_SIZE_MB}MB")

    image_url = service.save_product_image(contents, file.filename)
    return {"image_url": image_url}