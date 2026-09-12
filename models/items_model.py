from datetime import UTC, datetime
from typing import Literal, get_args
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Float, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db import Base

OrderByColumns = Literal["title","price","format","genre","condition"]
order_by_pattern=f"^(-?(?:{'|'.join(get_args(OrderByColumns))}))(?:,(-?(?:{'|'.join(get_args(OrderByColumns))})))*$"

class DiscountInfo(Base):
    __tablename__ = "discount_infos"

    value: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str] = mapped_column(String(30), nullable=False)
    items: Mapped[list[HuutoItem]] = relationship(back_populates="discount_info")

class Packaging(Base):
    __tablename__ = "packagings"

    value: Mapped[str] = mapped_column(String(30), nullable=False)
    label: Mapped[str] = mapped_column(String(30), nullable=False)
    items: Mapped[list[HuutoItem]] = relationship(back_populates="packaging")

class Condition(Base):
    __tablename__ = "conditions"

    value: Mapped[str] = mapped_column(String(30), nullable=False)
    label: Mapped[str] = mapped_column(String(30), nullable=False)
    items: Mapped[list[HuutoItem]] = relationship(back_populates="condition")

class MediaFormat(Base):
    __tablename__ = "media_formats"

    value: Mapped[str] = mapped_column(String(30), nullable=False)
    label: Mapped[str] = mapped_column(String(30), nullable=False)
    items: Mapped[list[HuutoItem]] = relationship(back_populates="media_format")
    genres: Mapped[list[Genre]] = relationship(back_populates="media_format")

class Genre(Base):
    __tablename__ = "genres"

    value: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str] = mapped_column(String(30), nullable=False)
    media_format_id: Mapped[int] = mapped_column(ForeignKey("media_formats.id"), nullable=False)
    items: Mapped[list[HuutoItem]] = relationship(back_populates="genre")
    media_format: Mapped[MediaFormat] = relationship(back_populates="genres")

class Region(Base):
    __tablename__ = "regions"

    value: Mapped[str] = mapped_column(String(30), nullable=False)
    label: Mapped[str] = mapped_column(String(30), nullable=False)
    items: Mapped[list[HuutoItem]] = relationship(back_populates="region")

class Subtitle(Base):
    __tablename__ = "subtitles"

    value: Mapped[str] = mapped_column(String(30), nullable=False)
    label: Mapped[str] = mapped_column(String(30), nullable=False)
    items: Mapped[list[HuutoItem]] = relationship(back_populates="subtitle")

class Country(Base):
    __tablename__ = "countries"

    value: Mapped[str] = mapped_column(String(30), nullable=False)
    label: Mapped[str] = mapped_column(String(30), nullable=False)
    items: Mapped[list[HuutoItem]] = relationship(back_populates="country")

class Shipping(Base):
    __tablename__ = "shipping"

    value: Mapped[float] = mapped_column(Float, nullable=False)
    label: Mapped[str] = mapped_column(String(30), nullable=False)
    items: Mapped[list[HuutoItem]] = relationship(back_populates="shipping")

class Image(Base):
    __tablename__ = "images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    filename: Mapped[str] = mapped_column(String(200), nullable=False)
    file_type: Mapped[str] = mapped_column(String(30), nullable=False)
    huuto_image_id: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    item_id: Mapped[int] = mapped_column(ForeignKey("huuto_items.id"), nullable=False)
    owner: Mapped[HuutoItem] = relationship(back_populates="images")

class HuutoItem(Base):
    __tablename__ = "huuto_items"

    title: Mapped[str] = mapped_column(String(60), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    keywords: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    offers_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    huuto_category_id: Mapped[int] = mapped_column(Integer, nullable=False)
    images: Mapped[list[Image]] = relationship(back_populates="owner", cascade="all, delete-orphan")
    slipcover: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))

    huuto_id: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    huuto_closing_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)

    shipping_id: Mapped[int] = mapped_column(Integer, ForeignKey("shipping.id"))
    shipping: Mapped[Shipping] = relationship(back_populates="items")

    country_id: Mapped[int] = mapped_column(Integer, ForeignKey("countries.id"))
    country: Mapped[Country] = relationship(back_populates="items")

    subtitle_id: Mapped[int] = mapped_column(Integer, ForeignKey("subtitles.id"), nullable=False)
    subtitle: Mapped[Subtitle] = relationship(back_populates="items")

    region_id: Mapped[int] = mapped_column(Integer, ForeignKey("regions.id"), nullable=False)
    region: Mapped[Region] = relationship(back_populates="items")

    condition_id: Mapped[int] = mapped_column(Integer, ForeignKey("conditions.id"), nullable=False)
    condition: Mapped[Condition] = relationship(back_populates="items")

    packaging_id: Mapped[int] = mapped_column(Integer, ForeignKey("packagings.id"), nullable=False)
    packaging: Mapped[Packaging] = relationship(back_populates="items")

    discount_info_id: Mapped[int] = mapped_column(Integer, ForeignKey("discount_infos.id"), nullable=True, default=None)
    discount_info: Mapped[DiscountInfo] = relationship(back_populates="items")

    media_format_id: Mapped[int] = mapped_column(Integer, ForeignKey("media_formats.id"), nullable=False)
    media_format: Mapped[MediaFormat] = relationship(back_populates="items")

    genre_id: Mapped[int] = mapped_column(Integer, ForeignKey("genres.id"), nullable=False)
    genre: Mapped[Genre] = relationship(back_populates="items")

items_model_map = {
    'discount_infos': DiscountInfo,
    'packagings': Packaging,
    'conditions': Condition,
    'media_formats': MediaFormat,
    'genres': Genre,
    'regions': Region,
    'subtitles': Subtitle,
    'countries': Country,
    'shipping': Shipping  
}
