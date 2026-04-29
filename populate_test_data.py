import asyncio
from sqlalchemy import delete, text
from models import items_model
import sys
import random

from db import AsyncSessionLocal, engine

NBR_OF_ITEMS = 50

async def clear_existing_data() -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(items_model.Image))
        await db.execute(text("ALTER SEQUENCE images_id_seq RESTART WITH 1;"))
        await db.execute(delete(items_model.HuutoItem))
        await db.execute(text("ALTER SEQUENCE huuto_items_id_seq RESTART WITH 1;"))
        await db.commit()
    print("Cleared existing data")

async def populate(nbr_of_items: int) -> None:

    await clear_existing_data()
 
    async with AsyncSessionLocal() as db:

        for i in range(1,nbr_of_items+1):
            new_item = items_model.HuutoItem(
                title=f"Movie {i}",
                description=f"Description for Movie {i}",
                quantity = 1,
                price = random.choice((2, 10, 20, 25, 30, 35)),
                offers_allowed = False,
                huuto_category_id = 1183,
                slipcover = random.choice((True,False)),
                shipping_id = random.choice((1,2,3,4)),
                country_id = random.choice((1,2,3,4)),
                subtitle_id = random.choice((1,2,3)),
                region_id = random.choice((1,2,3,4)),
                condition_id = random.choice((1,2,3,4)),
                packaging_id = random.choice((1,2,3,4)),
                media_format_id = random.choice((1,2,3)),
                genre_id = random.choice(list(range(1,47))),
            )
            db.add(new_item)
            await db.commit()

        for i in range(1,nbr_of_items+1):
            for j in range(1, random.randint(1,2)+1):
                file_type = random.choice(('fullsize','preview'))
                values = f"'image_{i}_{j}.jpg', '{file_type}', {random.randint(100000,200000)}, {i}"
                await db.execute(text(f"INSERT INTO images (filename, file_type, huuto_image_id, item_id) VALUES ({values})"))
                await db.commit()

    await engine.dispose()

if  __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio._WindowsSelectorEventLoopPolicy())
    asyncio.run(populate(NBR_OF_ITEMS))
