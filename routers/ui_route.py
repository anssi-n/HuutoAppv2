import math

from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.templating import Jinja2Templates
from typing import Annotated
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from db import get_db
from models import items_model
from item_config import get_item_config
from routers.items_route import fetch_items
from schemas import items_schema
from config import settings

router = APIRouter()

templates = Jinja2Templates(directory="templates")


@router.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return RedirectResponse(
        f"/media/icons/{settings.favicon_file}",
        status_code=status.HTTP_308_PERMANENT_REDIRECT,
    )


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
            "favicon_file": settings.favicon_file,
        }
    )


@router.get("/new", include_in_schema=False)
async def new_item(request: Request,
                   db: Annotated[AsyncSession, Depends(get_db)]):

    config = await get_item_config(db)

    return templates.TemplateResponse(
        request=request,
        name="new_item.html",
        context={"config": config, "favicon_file": settings.favicon_file}
    )


@router.get("/import", include_in_schema=False)
async def import_csv_page(request: Request,
                          db: Annotated[AsyncSession, Depends(get_db)]):

    config = await get_item_config(db)

    return templates.TemplateResponse(
        request=request,
        name="csv_import.html",
        context={"config": config, "favicon_file": settings.favicon_file}
    )


@router.get("/stats", include_in_schema=False)
async def statistics(request: Request,
                     db: Annotated[AsyncSession, Depends(get_db)]):

    stat_query = {}

    for key, table, join_col in (
        ("format", items_model.MediaFormat, items_model.HuutoItem.media_format_id),
        ("genre", items_model.Genre, items_model.HuutoItem.genre_id),
        ("condition", items_model.Condition, items_model.HuutoItem.condition_id),
    ):
        group_cols = [table.label] if key == "genre" else [table.label, table.id]
        stmt = (
            select(table.label,
                   func.count(items_model.HuutoItem.id),
                   func.sum(items_model.HuutoItem.price))
            .join(items_model.HuutoItem, join_col == table.id)
            .group_by(*group_cols)
            .order_by(func.count(items_model.HuutoItem.id).desc())
        )
        rows = (await db.execute(stmt)).all()
        stat_query[key] = [
            {"label": r[0], "count": r[1], "total": round(float(r[2] or 0), 2)}
            for r in rows
        ]

    grand_count, grand_total = (await db.execute(
        select(func.count(items_model.HuutoItem.id), func.sum(items_model.HuutoItem.price))
    )).one()

    return templates.TemplateResponse(
        request=request,
        name="statistics.html",
        context={
            "formats": stat_query["format"],
            "genres": stat_query["genre"],
            "conditions": stat_query["condition"],
            "grand_count": grand_count or 0,
            "grand_total": round(float(grand_total or 0), 2),
            "favicon_file": settings.favicon_file,
        }
    )