from enum import StrEnum
from pydantic import BaseModel, HttpUrl, ConfigDict
from pydantic.alias_generators import to_camel
import datetime

class Status(StrEnum):
    DRAFT = "draft"
    PREVIEW = "preview"
    PUBLISHED = "published"
    CLOSED = "closed"
    OPEN = "open"

class Condition(StrEnum):
    NEW = "new"
    LIKE_NEW = "like-new"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    WEAK = "weak" 

class SalesMethod(StrEnum):
    AUCTION = "auction"
    BUY_NOW = "buy-now"

class DeliveryMethod(StrEnum):
    PICKUP = "pickup"
    SHIPMENT = "shipment"
    FETCH = "fetch"
    ITELLA = "itella"

class PaymentMethod(StrEnum):
    WIRE_TRANSFER = "wire-transfer"
    CASH = "cash"
    MOBILE_PAY = "mobile-pay"

class Token(BaseModel):
    expires: datetime.datetime
    startTime: datetime.datetime
    id: str

    @property
    def is_valid(self) -> bool:
        return (self.expires - datetime.datetime.now(datetime.timezone.utc)).total_seconds() > 0

class Authentication(BaseModel):
    token: Token

class AuthenticationResponse(BaseModel):
    authentication: Authentication

class ImageLink(BaseModel):
    image: HttpUrl

class ImageResponse(BaseModel):
    links: ImageLink

    @property
    def image_id(self) -> int:
        return int(str(self.links.image).split("/")[-1])

class HuutoItem(BaseModel):

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,        
    )

    title: str | None = None
    description: str | None = None
    quantity: int | None = None
    buy_now_price: float | None = None
    category_id: int | None = None
    condition: str | None = None
    offers_allowed: int | None = None
    postal_code: int | None = None
    sale_method: SalesMethod | None = None
    closing_time: str | None = None
    payment_methods: list[PaymentMethod] | None = None
    payment_terms: str | None = None
    delivery_methods: list[DeliveryMethod] | None = None
    delivery_price: float | None = None
    delivery_terms: str | None = None
    status: Status | None = None
    original_id: int | None = None

class ItemResponse(BaseModel):
    id: int