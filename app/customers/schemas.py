from pydantic import BaseModel


class CustomerProfileUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None
    profile_image_url: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class CustomerProfileOut(BaseModel):
    id: int
    name: str | None
    email: str
    phone: str | None
    profile_image_url: str | None

    class Config:
        from_attributes = True


class AddressCreate(BaseModel):
    label: str
    address_text: str
    latitude: float | None = None
    longitude: float | None = None
    is_default: bool = False


class AddressOut(BaseModel):
    id: int
    label: str
    address_text: str
    latitude: float | None
    longitude: float | None
    is_default: bool

    class Config:
        from_attributes = True


class NearbyStoreOut(BaseModel):
    store_id: int
    store_name: str
    address: str
    distance_km: float
    rating: float


class ProductSearchResultOut(BaseModel):
    product_id: int
    product_name: str
    brand: str | None
    store_id: int
    store_name: str
    selling_price: float
    quantity_available: int
