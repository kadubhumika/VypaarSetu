from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_customer
from app.customers import schemas, service

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("/me", response_model=schemas.CustomerProfileOut)
def get_profile(customer=Depends(get_current_customer)):
    return customer


@router.patch("/me", response_model=schemas.CustomerProfileOut)
def update_profile(payload: schemas.CustomerProfileUpdate, db: Session = Depends(get_db), customer=Depends(get_current_customer)):
    return service.update_profile(db, customer, payload)


@router.post("/addresses", response_model=schemas.AddressOut)
def add_address(payload: schemas.AddressCreate, db: Session = Depends(get_db), customer=Depends(get_current_customer)):
    return service.add_address(db, customer.id, payload)


@router.get("/addresses", response_model=list[schemas.AddressOut])
def list_addresses(db: Session = Depends(get_db), customer=Depends(get_current_customer)):
    return service.list_addresses(db, customer.id)


@router.delete("/addresses/{address_id}")
def delete_address(address_id: int, db: Session = Depends(get_db), customer=Depends(get_current_customer)):
    ok = service.delete_address(db, customer.id, address_id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Address not found")
    return {"message": "Address removed"}


@router.get("/nearby-stores", response_model=list[schemas.NearbyStoreOut])
def nearby_stores(latitude: float, longitude: float, radius_km: float = 10.0, db: Session = Depends(get_db)):
    return service.find_nearby_stores(db, latitude, longitude, radius_km)


@router.get("/search-products", response_model=list[schemas.ProductSearchResultOut])
def search_products(q: str, latitude: float | None = None, longitude: float | None = None, db: Session = Depends(get_db)):
    return service.search_products(db, q, latitude, longitude)
