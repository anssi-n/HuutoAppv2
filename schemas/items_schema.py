from datetime import datetime, UTC
from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator
import re
from image_utils import ImageType

class Title(BaseModel):
    title: list[str | int] = Field(min_length=16, max_length=16)
    add_keywords: bool
     
class CsvFile(BaseModel):
    headers: list[str] = Field(min_length=16, max_length=16)
    titles: list[Title] = Field(min_length=1) 
    
    @field_validator("headers", mode="before")
    def set_headers(cls, data: str) -> list[str]:
        return data.split("|")[:-1]

    @field_validator("titles", mode="before")
    def set_titles(cls, data: list[str]) -> list[dict[str,list[str] | str]]:
        return [{"title": line.split("|")[:-1], "add_keywords": line.split("|")[-1]} for line in data]

    def title_dump(self) -> list[tuple[dict[str,str | int],bool]]:
        result = []
        for element in self.titles:
            result.append(({k:v for k,v in zip(self.headers, element.title)},element.add_keywords))
        return result


class PublishResponse(BaseModel):
    task_id: int
    title: str | None = None
    item_id: int | None = None
    
class DeleteResponse(BaseModel):
    title: str
    item_id: int
    task_id: int | None = None

class SuccessResponse(BaseModel):
    title: str
    item_id: int
    task_id: int

class FailResponse(BaseModel):
    title: str
    reason: str

class PublishCsvResponse(BaseModel):
    success: list[SuccessResponse]
    fail: list[FailResponse]

class SuccessImageResponse(BaseModel):
    original_image_name: str
    new_image_name: str

class FailImageResponse(BaseModel):
    original_image_name: str
    reason: str

class UploadCsvImagesResponse(BaseModel):
    success: list[SuccessImageResponse]
    fail: list[FailImageResponse]


class ItemCreate(BaseModel):

    title: str = Field(min_length=1, max_length=60) 
    description: str
    quantity: int = Field(ge=1, le=5) 
    price: float = Field(gt=0)
    offers_allowed: bool
    slipcover: bool
    shipping_id: int
    country_id: int
    subtitle_id: int
    region_id: int 
    condition_id: int 
    packaging_id: int 
    media_format_id: int 
    genre_id: int
    discount_info_id: int | None = None

class ItemUpdate(BaseModel):

    title: str | None = Field(min_length=1, max_length=60, default=None) 
    description: str | None = None
    quantity: int | None = Field(ge=1, le=5, default=None) 
    price: float | None = Field(gt=0, default=None)
    offers_allowed: bool | None = None
    slipcover: bool | None = None
    add_keywords: bool | None = None
    shipping_id: int | None = None
    country_id: int | None = None
    subtitle_id: int | None = None
    region_id: int | None = None
    condition_id: int | None = None
    packaging_id: int | None = None
    media_format_id: int | None = None
    genre_id: int | None = None
    discount_info_id: int | None = None

"""
{
  "keywords": null,
  "huuto_id": null,
  "discount_info_id": null,
  "quantity": 1,
  "huuto_closing_time": null,
  "media_format_id": 1,
  "price": 20,
  "shipping_id": 1,
  "genre_id": 3,
  "offers_allowed": false,
  "country_id": 2,
  "id": 20,
  "description": "Description for Movie 20",
  "huuto_category_id": 1183,
  "subtitle_id": 1,
  "slipcover": true,
  "region_id": 1,
  "title": "Movie 20",
  "created_at": "2026-03-29T17:00:03.205296+00:00",
  "condition_id": 3,
  "updated_at": "2026-03-29T17:00:03.205305+00:00",
  "packaging_id": 3,
  "country": {
    "label": "Espanja",
    "id": 2,
    "value": "Espanja"
  },
  "discount_info": null,
  "subtitle": {
    "id": 1,
    "value": "suomi",
    "label": "suomi"
  },
  "media_format": {
    "id": 1,
    "label": "DVD",
    "value": "DVD"
  },
  "region": {
    "value": "region free",
    "label": "region free",
    "id": 1
  },
  "genre": {
    "value": "848",
    "id": 3,
    "label": "Dokumentit",
    "media_format_id": 2
  },
  "images": [
    {
      "filename": "image_20_1.jpg",
      "huuto_image_id": 129773,
      "item_id": 20,
      "id": 26
    }
  ],
  "condition": {
    "label": "Hyvä",
    "id": 3,
    "value": "good"
  },
  "shipping": {
    "label": "Helposti-kuori C5",
    "value": 3.8,
    "id": 1
  },
  "packaging": {
    "id": 3,
    "value": "digibook",
    "label": "digibook"
  }
}
"""

class BaseConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    value: str
    label: str

class RegionResponse(BaseConfigResponse):
    pass

class MediaFormatResponse(BaseConfigResponse):
    pass

class SubtitleResponse(BaseConfigResponse):
    pass

class CountryResponse(BaseConfigResponse):
    pass

class PackagingResponse(BaseConfigResponse):
    pass

class ConditionResponse(BaseConfigResponse):
    pass

class DiscountInfoResponse(BaseConfigResponse):
    pass

class GenreResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    value: int
    label: str

class ShippingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    value: float
    label: str

class ImageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    file_type: ImageType
    huuto_image_id: int | None

class ItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str = Field(min_length=1, max_length=60) 
    description: str
    quantity: int = Field(ge=1, le=5) 
    price: float = Field(gt=0)
    shipping: ShippingResponse
    packaging: PackagingResponse
    slipcover: bool
    country: CountryResponse
    subtitle: SubtitleResponse
    media_format: MediaFormatResponse
    region: RegionResponse
    genre: GenreResponse
    condition: ConditionResponse
    discount_info: DiscountInfoResponse | None
    images: list[ImageResponse]
    huuto_id: int | None
    created_at: datetime
    huuto_closing_time: datetime | None
    keywords: str | None = Field(exclude=True)

    @computed_field # type: ignore[prop-decorator]
    @property 
    def closed(self) -> bool | None:
        if self.huuto_id is None or self.huuto_closing_time is None:
            return None
        print(self.huuto_closing_time)
        print(datetime.now().astimezone())
        return self.huuto_closing_time < datetime.now(UTC).astimezone()

    @computed_field # type: ignore[prop-decorator]
    @property 
    def item_keywords(self) -> list[str]:
        if self.keywords is None:
            return []
        sections = re.findall(r"<\/b>:(?:&#09;|\s{1,})([,\w\s\-'()]*)<br>",self.keywords)
        if sections:
            return [keyword.strip() for kw in sections[1:] for keyword in kw.split(",")]
        else:
            return []

    @computed_field # type: ignore[prop-decorator]
    @property 
    def imdb_link(self) -> str | None:
        if self.keywords is None:
            return None
        href = re.findall(r"href=([\S]+)",self.keywords)
        if href:
            return href[0]
        return None

class PaginatedItemResponse(BaseModel):
   
    items: list[ItemResponse]
    total: int
    skip: int
    limit: int
    has_more: bool