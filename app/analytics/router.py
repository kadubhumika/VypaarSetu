from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_merchant
from app.analytics import schemas, service
from app.inventory.service import get_merchant_store

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/dashboard", response_model=schemas.MerchantDashboardOut)
def merchant_dashboard(db: Session = Depends(get_db), merchant=Depends(get_current_merchant)):
    store = get_merchant_store(db, merchant.id)
    if not store:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No store found for this merchant")
    return service.get_merchant_dashboard(db, merchant.id, store.id)