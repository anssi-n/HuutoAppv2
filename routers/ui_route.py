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
               order_by: Annotated[str, Query(pattern=items_model.order_by_pattern)] = "title"):

    items, total, has_more = await fetch_items(db, skip, limit, search, order_by)

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
            "prev_skip": max(0, skip - limit),
            "next_skip": skip + limit,
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