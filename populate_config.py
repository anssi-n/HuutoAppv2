import asyncio
import json
from sqlalchemy import delete, text
from models import items_model
import sys

from db import AsyncSessionLocal, engine

async def clear_existing_data() -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(items_model.HuutoItem))
        await db.execute(text("ALTER SEQUENCE huuto_items_id_seq RESTART WITH 1;"))
        await db.execute(delete(items_model.Packaging))
        await db.execute(text("ALTER SEQUENCE packagings_id_seq RESTART WITH 1;"))
        await db.execute(delete(items_model.Condition))
        await db.execute(text("ALTER SEQUENCE conditions_id_seq RESTART WITH 1;"))
        await db.execute(delete(items_model.Country))
        await db.execute(text("ALTER SEQUENCE countries_id_seq RESTART WITH 1;"))
        await db.execute(delete(items_model.Genre))
        await db.execute(text("ALTER SEQUENCE genres_id_seq RESTART WITH 1;"))
        await db.execute(delete(items_model.MediaFormat))
        await db.execute(text("ALTER SEQUENCE media_formats_id_seq RESTART WITH 1;"))
        await db.execute(delete(items_model.Region))
        await db.execute(text("ALTER SEQUENCE regions_id_seq RESTART WITH 1;"))
        await db.execute(delete(items_model.Shipping))
        await db.execute(text("ALTER SEQUENCE shipping_id_seq RESTART WITH 1;"))
        await db.execute(delete(items_model.Subtitle))
        await db.execute(text("ALTER SEQUENCE subtitles_id_seq RESTART WITH 1;"))
        await db.commit()
    print("Cleared existing data")

async def populate() -> None:

    await clear_existing_data()
 
    async with AsyncSessionLocal() as db:
        with open("item_config.json","r",encoding="utf-8") as f:
            configs = json.loads(f.read())
        for table in configs:
            for row in configs[table]:
                if table in items_model.items_model_map:
                    print(f"Populating table {table} row with values {tuple(row)}")
                    values = ",".join((f"'{val}'" for val in row))
                    print(values)
                    await db.execute(text(f"INSERT INTO {table} (value, label) VALUES ({values})"))
                else:
                    print(f"Error: No model found for table {table} in items_model_map")

        result = await db.execute(text("SELECT id, label FROM media_formats"))
        formats = {k:v for v,k in result}
        print(formats)

        with open("movie_categories.json","r",encoding="utf-8") as f:
            categories = json.loads(f.read())

        for format in categories:
            for category, category_id in sorted(categories[format].items(),key=lambda x:x[0]):
                values = f"{category_id}, '{category}', {formats[format]}"
                sql = f"INSERT INTO genres (value, label, media_format_id) VALUES ({values})"
                await db.execute(text(sql))

        await db.commit()

        # new_item = models.HuutoItem(
        #     title="Movie 1",
        #     description="Description for Movie 1",
        #     quantity = 1,
        #     price = 30,
        #     offers_allowed = False,
        #     huuto_category_id = 1183,
        #     slipcover = True,
        #     shipping_id = 1,
        #     country_id = 1,
        #     subtitle_id = 1,
        #     region_id = 1,
        #     condition_id = 1,
        #     packaging_id = 1,
        #     media_format_id = 1,
        #     genre_id = 26,
        # )
        # print(new_item)
        # db.add(new_item)
        # await db.commit()
        # await db.refresh(new_item, attribute_names=["shipping", "country", "subtitle", "region", "condition", "packaging", "discount_info", "media_format", "genre"])
        # print(new_item.shipping.label)

    await engine.dispose()

if  __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio._WindowsSelectorEventLoopPolicy())


    asyncio.run(populate())
