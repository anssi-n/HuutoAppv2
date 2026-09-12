import math

from fastapi.responses import HTMLResponse
from fastapi import APIRouter, Depends, Query, Request
from fastapi.templating import Jinja2Templates
from typing import Annotated
from sqlalchemy.ext.asyncio import AsyncSession
from db import get_db
from models import items_model
from item_config import get_item_config
from routers.items_route import fetch_items
from schemas import items_schema

router = APIRouter()

templates = Jinja2Templates(directory="templates")


@router.get("/", include_in_schema=False, response_class=HTMLResponse)
async def home(request: Request,
               db: Annotated[AsyncSession, Depends(get_db)],
               skip: Annotated[int, Query(ge=0)] = 0,
               limit: Annotated[int, Query(ge=1, le=100)] = 20,
               search: Annotated[str | None, Query()] = None,
               order_by: Annotated[str, Query(pattern=items_model.order_by_pattern)] = "title",
               media_format_id: Annotated[int | None, Query()] = None,
               genre_id: Annotated[int | None, Query()] = None,
               condition_id: Annotated[int | None, Query()] = None):

    items, total, has_more = await fetch_items(db, skip, limit, search, order_by,
                                               media_format_id, genre_id, condition_id)

    total_pages = math.ceil(total / limit) if limit else 1
    current_page = min(skip // limit + 1, total_pages) if limit else 1
    pages = [p for p in range(1, total_pages + 1)
             if p == 1 or p == total_pages or abs(p - current_page) <= 2]

    config = await get_item_config(db)

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "items": [items_schema.ItemResponse.model_validate(item) for item in items],
            "total": total,
            "skip": skip,
            "limit": limit,
            "search": search or "",
            "order_by": order_by,
            "has_more": has_more,
            "total_pages": total_pages,
            "current_page": current_page,
            "pages": pages,
            "prev_skip": max(0, skip - limit),
            "next_skip": skip + limit,
            "config": config,
            "mf_filter": str(media_format_id) if media_format_id is not None else "",
            "genre_filter": str(genre_id) if genre_id is not None else "",
            "cond_filter": str(condition_id) if condition_id is not None else "",
        }
    )


@router.get("/new", include_in_schema=False)
async def new_item(request: Request,
                   db: Annotated[AsyncSession, Depends(get_db)]):

    config = await get_item_config(db)

    return templates.TemplateResponse(
        request=request,
        name="new_item.html",
        context={"config": config}
    )


@router.get("/import", include_in_schema=False)
async def import_csv_page(request: Request,
                          db: Annotated[AsyncSession, Depends(get_db)]):

    config = await get_item_config(db)

    return templates.TemplateResponse(
        request=request,
        name="csv_import.html",
        context={"config": config}
    )