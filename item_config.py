from models import items_model
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

class ConfigElement(BaseModel):
    label: str
    value: str | int | float
    id: int
    media_format_id: int | None = None

class ItemConfig(BaseModel):
    country: list[ConfigElement]
    condition: list[ConfigElement] 
    media_format: list[ConfigElement]  
    genre: list[ConfigElement]  
    region: list[ConfigElement]  
    subtitles: list[ConfigElement] 
    packaging: list[ConfigElement]  
    shipping: list[ConfigElement] 
    discount_info: list[ConfigElement] 

    def get_id(self, attribute: str, value: str | int) -> int | None:
        # print(f"Getting id for {attribute} with value {value}")
        config_element_list: list[ConfigElement] | None = getattr(self, attribute, None)
        if config_element_list is None:
            return None
        
        for c in config_element_list:
             if c.label == value:
                  return c.id
        return None      

    def get_huuto_category(self, format: str | int, genre: str | int) -> int | None:

        media_format_id = None
        for el in self.media_format:
             if el.value == format:
                  media_format_id = el.id
                  break
        if not media_format_id:
            return None
         
        huuto_category = None
        for el in self.genre:
            if el.media_format_id == media_format_id and genre == el.label:
                huuto_category = int(el.value)
                break
        return huuto_category


async def get_item_config(db: AsyncSession) -> ItemConfig:

        config = {}

        result = await db.execute(select(items_model.Genre))
        values = result.scalars().all()
        config['genre'] = [ConfigElement(id=el.id, label=el.label, value=el.value, media_format_id=el.media_format_id) for el in values]

        result = await db.execute(select(items_model.Country))
        values = result.scalars().all()
        config['country'] = [ConfigElement(id=el.id, label=el.label, value=el.value) for el in values]

        result = await db.execute(select(items_model.Condition))
        values = result.scalars().all()
        config['condition'] = [ConfigElement(id=el.id, label=el.label, value=el.value) for el in values]

        result = await db.execute(select(items_model.MediaFormat))
        values = result.scalars().all()
        config['media_format'] = [ConfigElement(id=el.id, label=el.label, value=el.value) for el in values]

        result = await db.execute(select(items_model.Region))
        values = result.scalars().all()
        config['region'] = [ConfigElement(id=el.id, label=el.label, value=el.value) for el in values]

        result = await db.execute(select(items_model.Subtitle))
        values = result.scalars().all()
        config['subtitles'] = [ConfigElement(id=el.id, label=el.label, value=el.value) for el in values]

        result = await db.execute(select(items_model.Packaging))
        values = result.scalars().all()
        config['packaging'] = [ConfigElement(id=el.id, label=el.label, value=el.value) for el in values]

        result = await db.execute(select(items_model.Shipping))
        values = result.scalars().all()
        config['shipping'] = [ConfigElement(id=el.id, label=el.label, value=el.value) for el in values]

        result = await db.execute(select(items_model.DiscountInfo))
        values = result.scalars().all()
        config['discount_info'] = [ConfigElement(id=el.id, label=el.label, value=el.value) for el in values]

        return ItemConfig.model_validate(config) 