from fastapi import HTTPException, status, Depends, Query, UploadFile, Form, APIRouter
from starlette.concurrency import run_in_threadpool
from redis.asyncio import Redis

from typing import Annotated, Any, Sequence
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from pydantic import ValidationError
from datetime import datetime, UTC
from models import items_model, task_log_model
from common import common_types
from schemas import items_schema, huutoapp_queue_schema
from db import get_db
from redis_queue import get_redis
from PIL import UnidentifiedImageError
from image_utils import delete_image, process_image, generate_preview, ImageType, ImagePhase, IMAGE_DIR
from config import settings
from item_config import get_item_config
from logger import logger

router = APIRouter()

ORDER_BY_COLUMNS: dict[str, Any] = {
    "title": func.regexp_replace(func.lower(items_model.HuutoItem.title), '^(a|an|the) ', '', 'i'),
    "price": items_model.HuutoItem.price,
    "format": items_model.MediaFormat.label,
    "genre": items_model.Genre.label,
    "condition": items_model.Condition.label,
}

ORDER_BY_JOINS: dict[str, Any] = {
    "format": items_model.HuutoItem.media_format,
    "genre": items_model.HuutoItem.genre,
    "condition": items_model.HuutoItem.condition,
}

async def fetch_items(db: AsyncSession,
                      skip: int = 0,
                      limit: int = 10,
                      search: str | None = None,
                      order_by: str = "title",
                      media_format_id: int | None = None,
                      genre_id: int | None = None,
                      condition_id: int | None = None) -> tuple[Sequence[items_model.HuutoItem], int, bool]:

    select_stm = select(items_model.HuutoItem).options(selectinload(items_model.HuutoItem.shipping),
                                      selectinload(items_model.HuutoItem.country),
                                      selectinload(items_model.HuutoItem.subtitle),
                                      selectinload(items_model.HuutoItem.region),
                                      selectinload(items_model.HuutoItem.condition),
                                      selectinload(items_model.HuutoItem.packaging),
                                      selectinload(items_model.HuutoItem.discount_info),
                                      selectinload(items_model.HuutoItem.media_format),
                                      selectinload(items_model.HuutoItem.genre),
                                      selectinload(items_model.HuutoItem.images)).offset(skip).limit(limit)

    count_stm = select(func.count()).select_from(items_model.HuutoItem)
    if search is not None:
        count_stm = count_stm.where(func.concat(items_model.HuutoItem.keywords,items_model.HuutoItem.title,items_model.HuutoItem.description).ilike(f"%{search}%"))
    if media_format_id is not None:
        count_stm = count_stm.where(items_model.HuutoItem.media_format_id == media_format_id)
    if genre_id is not None:
        count_stm = count_stm.where(items_model.HuutoItem.genre_id == genre_id)
    if condition_id is not None:
        count_stm = count_stm.where(items_model.HuutoItem.condition_id == condition_id)
    count_result = await db.execute(count_stm)
    total = count_result.scalar() or 0
    logger.info(f"Total number of items {total}.")

    if search is not None:
        select_stm = select_stm.where(func.concat(items_model.HuutoItem.keywords,items_model.HuutoItem.title,items_model.HuutoItem.description).ilike(f"%{search}%"))
    if media_format_id is not None:
        select_stm = select_stm.where(items_model.HuutoItem.media_format_id == media_format_id)
    if genre_id is not None:
        select_stm = select_stm.where(items_model.HuutoItem.genre_id == genre_id)
    if condition_id is not None:
        select_stm = select_stm.where(items_model.HuutoItem.condition_id == condition_id)

    for order_by_rule in order_by.split(","):
        descending = order_by_rule.startswith("-")
        column_name = order_by_rule[1:] if descending else order_by_rule
        join = ORDER_BY_JOINS.get(column_name)
        if join is not None:
            select_stm = select_stm.outerjoin(join)
        column = ORDER_BY_COLUMNS.get(column_name)
        if column is not None:
            select_stm = select_stm.order_by(desc(column) if descending else column)

    result = await db.execute(select_stm)
    items = result.scalars().all()
    has_more = skip + len(items) < total

    return items, total, has_more

@router.get("", response_model=items_schema.PaginatedItemResponse)
async def get_items(db: Annotated[AsyncSession, Depends(get_db)], 
                    skip: Annotated[int, Query(ge=0)] = 0, 
                    limit: Annotated[int, Query(ge=1, le=100)] = 10,
                    search: Annotated[str | None, Query()] = None,
                    order_by: Annotated[str , Query(pattern=items_model.order_by_pattern)] = "title",
                    media_format_id: Annotated[int | None, Query()] = None,
                    genre_id: Annotated[int | None, Query()] = None,
                    condition_id: Annotated[int | None, Query()] = None):

    items, total, has_more = await fetch_items(db, skip, limit, search, order_by,
                                               media_format_id, genre_id, condition_id)

    return items_schema.PaginatedItemResponse(
        items=[items_schema.ItemResponse.model_validate(item) for item in items],
        total=total,
        skip=skip,
        limit=limit,
        has_more=has_more
    )

@router.get("/{item_id}", response_model=items_schema.ItemResponse)
async def get_item(item_id: int, db: Annotated[AsyncSession, Depends(get_db)]):

    result = await db.execute(select(items_model.HuutoItem).
                              options(selectinload(items_model.HuutoItem.shipping),
                                      selectinload(items_model.HuutoItem.country),
                                      selectinload(items_model.HuutoItem.subtitle),
                                      selectinload(items_model.HuutoItem.region),
                                      selectinload(items_model.HuutoItem.condition),
                                      selectinload(items_model.HuutoItem.packaging),
                                      selectinload(items_model.HuutoItem.discount_info),
                                      selectinload(items_model.HuutoItem.media_format),
                                      selectinload(items_model.HuutoItem.genre),
                                      selectinload(items_model.HuutoItem.images)
                                      ).
                              where(items_model.HuutoItem.id == item_id))
    item = result.scalars().first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    return item

@router.post("", response_model=items_schema.ItemResponse, status_code=status.HTTP_201_CREATED)
async def create_item(item: items_schema.ItemCreate, 
                      db: Annotated[AsyncSession, Depends(get_db)]):

    result = await db.execute(select(items_model.Genre).where(items_model.Genre.id == item.genre_id))
    category = result.scalars().one()

    new_item = items_model.HuutoItem(
        title = item.title,
        description = item.description,
        quantity = item.quantity,
        price = item.price,
        offers_allowed = item.offers_allowed,
        slipcover = item.slipcover,
        huuto_category_id = category.value,
        images = [],
        shipping_id = item.shipping_id,
        country_id = item.country_id,
        subtitle_id = item.subtitle_id,
        region_id = item.region_id,
        condition_id = item.condition_id,
        packaging_id = item.packaging_id,
        discount_info_id = item.discount_info_id,
        media_format_id = item.media_format_id,
        genre_id = item.genre_id
    )

    db.add(new_item)
    await db.commit()
    await db.refresh(new_item, attribute_names=["images","shipping", "country", "subtitle", "region", "condition", "packaging", "discount_info", "media_format", "genre"])
    return new_item

@router.post("/publish/csv", response_model=items_schema.PublishCsvResponse, status_code=status.HTTP_201_CREATED)
async def publish_csv(csv: UploadFile,
                      db: Annotated[AsyncSession, Depends(get_db)],
                      redis: Annotated[Redis, Depends(get_redis)]):

    if csv.content_type != "text/csv":
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Incorrect content type, text/csv expected.")

    try:
        content = await csv.read()
        csv_lines = [line.strip() for line in content.decode().split("\n")]
        csv_file = items_schema.CsvFile.model_validate({"headers": csv_lines[0], "titles": csv_lines[1:]})
    except ValidationError as err:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=f"Incorrectly formatted csv file: {str(err)}")

    configs = await get_item_config(db)

    response = items_schema.PublishCsvResponse(success=[], fail=[])

    for title, add_keywords in csv_file.title_dump():

        try:
            #print(f"Adding title {title}. Add keywords to title={add_keywords}")
            
            images = title.get("images", None)
            title.pop("images")

            huuto_category_id = configs.get_huuto_category(title["media_format"], title["genre"])
            if huuto_category_id is not None:
                title["huuto_category_id"] =  huuto_category_id

            for attribute in title:
                if id := configs.get_id(attribute, title[attribute]):
                    title[attribute] = id

            #print(f"Title after conversions {title}")
            
            new_item = items_model.HuutoItem(
                title = title["title"],
                description = title["description"],
                quantity = title["quantity"], 
                price = title["price"],
                offers_allowed = bool(int(title["offers_allowed"])), 
                slipcover = bool(int(title["slipcover"])), 
                images = [],
                discount_info_id = int(title["discount_info"]) or None,  

                huuto_category_id = title["huuto_category_id"],
                shipping_id = title["shipping"],
                country_id = title["country"],
                subtitle_id = title["subtitles"],
                region_id = title["region"],
                condition_id = title["condition"],
                packaging_id = title["packaging"],
                media_format_id = title["media_format"],
                genre_id = title["genre"]
            )

            db.add(new_item)

            if images is not None:
                for image in str(images).split(";"):
                    img_type, filename = image.split(":")
                    if img_type not in ("preview","fullsize"):
                        raise AttributeError(f"Incorrect image type {img_type} for image {filename} in title {new_item.title}")

                    if not (IMAGE_DIR / filename).exists():
                        raise ValueError(f"Image {filename} in title {new_item.title} does not exist!")

                    if img_type == "preview":
                        preview_filename = generate_preview(filename)
                        new_item.images.append(items_model.Image(filename=preview_filename, file_type="preview", item_id=new_item.id))
                    new_item.images.append(items_model.Image(filename=filename, file_type="fullsize", item_id=new_item.id))
                    await db.commit()

            await db.refresh(new_item, attribute_names=["images","shipping", "country", "subtitle", "region", "condition", "packaging", "discount_info", "media_format", "genre"])

            task_id = await create_queue_msg(
                new_item.id,
                common_types.TaskType.AddItem,
                add_keywords,
                {"item_id": new_item.id},
                db,
                redis
            )

            response.success.append(items_schema.SuccessResponse(
                title=new_item.title,
                item_id=new_item.id,
                task_id=task_id
            ))

        except Exception as err:
            logger.error(f"Adding title {title} failed with {str(err)}")
            response.fail.append(items_schema.FailResponse(
                title = str(title["title"]),
                reason = str(err)
            ))
            await db.rollback()

    return response


@router.patch("/publish/csvimages", response_model=items_schema.UploadCsvImagesResponse, status_code=status.HTTP_201_CREATED)
async def upload_csvimages(
    images: list[UploadFile],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)]):

    response = items_schema.UploadCsvImagesResponse(success=[], fail=[])

    for image in images:
        try:
            content = await image.read()

            if len(content) > settings.max_image_size:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Image file too large. Maximum size is {settings.max_image_size // (1024 * 1024)}MB",
                )   

            full_filename, _ = await run_in_threadpool(process_image, "fullsize", content, keep_filename=True, original_filename=image.filename)

            response.success.append(items_schema.SuccessImageResponse(
                original_image_name=str(full_filename),
                new_image_name=str(full_filename),
            ))

        except Exception as err:
            logger.error(f"Adding image {image.filename} failed with {str(err)}")
            response.fail.append(items_schema.FailImageResponse(
                original_image_name = str(image.filename),
                reason = str(err)
            ))

    return response


@router.post("/publish/{item_id}", response_model=items_schema.PublishResponse, status_code=status.HTTP_201_CREATED)
async def publish_item(item_id: int,
                       add_keywords: Annotated[int, Query(ge=0,le=1 )],
                       db: Annotated[AsyncSession, Depends(get_db)],
                       redis: Annotated[Redis, Depends(get_redis)]):

    result = await db.execute(select(items_model.HuutoItem).where(items_model.HuutoItem.id == item_id))
    item = result.scalars().first()
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
 
    task_id = await create_queue_msg(
        item.id,
        common_types.TaskType.AddItem,
        add_keywords,
        {"item_id": item.id},
        db,
        redis
    )

    return items_schema.PublishResponse(task_id=task_id, item_id=item.id, title=item.title)


@router.post("/relist/all", response_model=items_schema.PublishResponse, status_code=status.HTTP_201_CREATED)
async def relist_all_items(db: Annotated[AsyncSession, Depends(get_db)],
                           redis: Annotated[Redis, Depends(get_redis)]):

    task_id = await create_queue_msg(
        0,
        common_types.TaskType.RelistAllItems,
        0,
        {},
        db,
        redis
    )

    return items_schema.PublishResponse(task_id=task_id)

@router.post("/relist/{item_id}", response_model=items_schema.PublishResponse, status_code=status.HTTP_201_CREATED)
async def relist_item(item_id: int,
                      add_keywords: Annotated[int, Query(ge=0,le=1 )],
                      db: Annotated[AsyncSession, Depends(get_db)],
                      redis: Annotated[Redis, Depends(get_redis)]):

    result = await db.execute(select(items_model.HuutoItem).where(items_model.HuutoItem.id == item_id))
    item = result.scalars().first()
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
 
    if item.huuto_closing_time is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Item is not yet published to Huuto.net. Unable to relist.")

    # if item.huuto_closing_time > datetime.now(UTC):
    #     raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Item is still active in Huuto.net.")

    task_id = await create_queue_msg(
        item.id,
        common_types.TaskType.RelistItem,
        add_keywords,
        {"item_id": item.id},
        db,
        redis
    )

    return items_schema.PublishResponse(task_id=task_id, item_id=item.id, title=item.title)

@router.patch("/{item_id}", response_model=items_schema.ItemResponse)
async def update_item(item_id: int, item_data: items_schema.ItemUpdate, db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(items_model.HuutoItem).where(items_model.HuutoItem.id == item_id))
    item = result.scalars().first()
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
       
    update_data = item_data.model_dump(exclude_unset=True) # exlude_unset = True -> get only values the client has sent. Not default Nones
    for field, value in update_data.items():
       setattr(item, field, value)

    await db.commit()
    await db.refresh(item, attribute_names=["images", "shipping", "country", "subtitle", "region", "condition", "packaging", "discount_info", "media_format", "genre"])
    return item

@router.delete("/all", status_code=status.HTTP_204_NO_CONTENT)
async def delete_all_items(db: Annotated[AsyncSession, Depends(get_db)],
                           redis: Annotated[Redis, Depends(get_redis)]):

    result = await db.execute(select(items_model.HuutoItem))
    items = result.scalars().all()

    for item in items:
        await db.delete(item)
        await db.commit()

        for image in item.images:
            delete_image(image.filename)

        _ = await create_queue_msg(
            item.id,
            common_types.TaskType.CloseItem,
            0,
            {"item_id": item.id},
            db,
            redis
        )


@router.delete("/{item_id}", response_model=items_schema.DeleteResponse, status_code=status.HTTP_200_OK)
async def delete_item(item_id: int, 
                      db: Annotated[AsyncSession, Depends(get_db)],
                      redis: Annotated[Redis, Depends(get_redis)]):

    result = await db.execute(select(items_model.HuutoItem).where(items_model.HuutoItem.id == item_id))
    item = result.scalars().first()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Huuto item not found",
        )

    await db.delete(item)
    await db.commit()

    for image in item.images:
        delete_image(image.filename)

    if item.huuto_id:
        task_id = await create_queue_msg(
            item.huuto_id,
            common_types.TaskType.CloseItem,
            0,
            {"huuto_id": item.huuto_id},
            db,
            redis
        )
    else:
        task_id = None

    return items_schema.DeleteResponse(
        title = item.title,
        item_id = item.id,
        task_id = task_id
    )

@router.patch("/{item_id}/image", response_model=items_schema.ItemResponse)
async def add_item_image(
    item_id: int,
    image: UploadFile,
    image_type: Annotated[ImageType, Form()],
    phase: Annotated[ImagePhase, Form()],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)]):

    result = await db.execute(select(items_model.HuutoItem).
                              options(selectinload(items_model.HuutoItem.shipping),
                                      selectinload(items_model.HuutoItem.country),
                                      selectinload(items_model.HuutoItem.subtitle),
                                      selectinload(items_model.HuutoItem.region),
                                      selectinload(items_model.HuutoItem.condition),
                                      selectinload(items_model.HuutoItem.packaging),
                                      selectinload(items_model.HuutoItem.discount_info),
                                      selectinload(items_model.HuutoItem.media_format),
                                      selectinload(items_model.HuutoItem.genre),
                                      selectinload(items_model.HuutoItem.images)
                                      ).
                              where(items_model.HuutoItem.id == item_id))
    item = result.scalars().first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    content = await image.read()

    if len(content) > settings.max_image_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Image file too large. Maximum size is {settings.max_image_size // (1024 * 1024)}MB",
        )   

    try:
        full_filename, preview_filename = await run_in_threadpool(process_image, image_type, content)
    except UnidentifiedImageError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid image file. Please upload a valid image (JPEG, PNG, GIF, WebP).",
        ) from err

    item.images.append(items_model.Image(filename=full_filename, file_type="fullsize", item_id=item.id))
    if preview_filename:
        for img in item.images:
            if img.file_type == "preview":
                delete_image(img.filename)
        item.images = [img for img in item.images if img.file_type != "preview"]
        item.images.append(items_model.Image(filename=preview_filename, file_type="preview", item_id=item.id))

    await db.commit()
    await db.refresh(item, attribute_names=["images"])

    if phase == "update":
        _ = await create_queue_msg(
        item.id,
        common_types.TaskType.AddImage,
        0,
        {"image_name": full_filename},
        db,
        redis
        )

    return item


@router.delete("/{item_id}/image/{image_id}", response_model=items_schema.ItemResponse)
async def delete_item_image(item_id: int, 
                            image_id: int, 
                            db: Annotated[AsyncSession, Depends(get_db)],
                            redis: Annotated[Redis, Depends(get_redis)]):

    result = await db.execute(select(items_model.HuutoItem).
                              options(selectinload(items_model.HuutoItem.shipping),
                                      selectinload(items_model.HuutoItem.country),
                                      selectinload(items_model.HuutoItem.subtitle),
                                      selectinload(items_model.HuutoItem.region),
                                      selectinload(items_model.HuutoItem.condition),
                                      selectinload(items_model.HuutoItem.packaging),
                                      selectinload(items_model.HuutoItem.discount_info),
                                      selectinload(items_model.HuutoItem.media_format),
                                      selectinload(items_model.HuutoItem.genre),
                                      selectinload(items_model.HuutoItem.images)
                                      ).
                              where(items_model.HuutoItem.id == item_id))
    item = result.scalars().first()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Huuto item not found",
        )

    huuto_image_id: int | None = None
    for image in item.images:
        if image.id == image_id:
            delete_image(image.filename)
            huuto_image_id = image.huuto_image_id
            break
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image not found",
        )

    item.images = [image for image in item.images if image.id != image_id ]

    if huuto_image_id is not None:
        _ = await create_queue_msg(
            item.id,
            common_types.TaskType.DeleteImage,
            0,
            {"huuto_image_id": huuto_image_id},
            db,
            redis
        )

    await db.commit()
    await db.refresh(item, attribute_names=["images", "shipping", "country", "subtitle", "region", "condition", "packaging", "discount_info", "media_format", "genre"])

    return item


async def create_queue_msg(id: int,
                           task_type: common_types.TaskType,
                           add_keywords: int,
                           details: dict[str,Any],
                           db: AsyncSession,
                           redis: Redis) -> int:
    # Create task log entry
    task_log = task_log_model.TaskLog(
        task = task_type,
        status = common_types.TaskStatus.ongoing,
        details = details)

    db.add(task_log)
    await db.commit()
    await db.refresh(task_log)
    
    queue_msg = huutoapp_queue_schema.QueueMessage(
        task = huutoapp_queue_schema.Task(
            task = task_type,
            log_id = task_log.id,
            id = id, 
            add_keywords = add_keywords
        ),
        created_at = datetime.now(UTC),
        retries = 0

    )
    await redis.lpush(settings.redis_queue_name, queue_msg.model_dump_json()) # type: ignore 
    return task_log.id