from fastapi import Depends, APIRouter

from typing import Annotated
from sqlalchemy.ext.asyncio import AsyncSession

from item_config import get_item_config, ItemConfig
from db import get_db

router = APIRouter()

@router.get("", response_model=ItemConfig)
async def get_config(db: Annotated[AsyncSession, Depends(get_db)]):
    item_config = await get_item_config(db)
    return item_config