from math import radians, sin, cos, sqrt, atan2

from sqlalchemy.orm import Session

from app.models import Customer, Address, Store, Product, Inventory


def update_profile(db: Session, customer: Customer, data) -> Customer:
    for field, value in data.dict(exclude_unset=True).items():
        setattr(customer, field, value)
    db.commit()
    db.refresh(customer)
    return customer


def add_address(db: Session, customer_id: int, data) -> Address:
    if data.is_default:
        db.query(Address).filter(Address.customer_id == customer_id).update({"is_default": False})
    address = Address(customer_id=customer_id, **data.dict())
    db.add(address)
    db.commit()
    db.refresh(address)
    return address


def list_addresses(db: Session, customer_id: int) -> list[Address]:
    return db.query(Address).filter(Address.customer_id == customer_id).all()


def delete_address(db: Session, customer_id: int, address_id: int) -> bool:
    address = db.query(Address).filter(Address.id == address_id, Address.customer_id == customer_id).first()
    if not address:
        return False
    db.delete(address)
    db.commit()
    return True


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


def find_nearby_stores(db: Session, latitude: float, longitude: float, radius_km: float = 10.0) -> list[dict]:
    """Mock-ONDC discovery: real ONDC network integration replaces this query later —
    the response shape (store_id, distance, rating) stays the same either way."""
    stores = db.query(Store).all()
    results = []
    for store in stores:
        distance = _haversine_km(latitude, longitude, store.latitude, store.longitude)
        if distance <= radius_km:
            results.append({
                "store_id": store.id,
                "store_name": store.store_name,
                "address": store.address,
                "distance_km": round(distance, 2),
                "rating": store.rating,
            })
    return sorted(results, key=lambda r: r["distance_km"])


def search_products(db: Session, query: str, latitude: float | None = None, longitude: float | None = None) -> list[dict]:
    rows = (
        db.query(Product, Inventory, Store)
        .join(Inventory, Inventory.product_id == Product.id)
        .join(Store, Store.id == Inventory.store_id)
        .filter(Product.name.ilike(f"%{query}%"), Inventory.quantity > 0)
        .all()
    )
    results = [
        {
            "product_id": prod.id,
            "product_name": prod.name,
            "brand": prod.brand,
            "store_id": store.id,
            "store_name": store.store_name,
            "selling_price": float(inv.selling_price),
            "quantity_available": inv.quantity,
            "image_url": prod.image_url,
        }
        for prod, inv, store in rows
    ]

    if latitude is not None and longitude is not None:
        store_distance = {s.id: _haversine_km(latitude, longitude, s.latitude, s.longitude) for _, _, s in rows}
        results.sort(key=lambda r: store_distance.get(r["store_id"], 9999))

    return results
