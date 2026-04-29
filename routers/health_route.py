from fastapi import Depends, APIRouter, status
from redis import Redis
from typing import Annotated
from sqlalchemy.ext.asyncio import AsyncSession
from db import get_db
from redis_queue import get_redis

router = APIRouter()

@router.get("", status_code=status.HTTP_200_OK)
async def health(db: Annotated[AsyncSession, Depends(get_db)],
                 redis: Annotated[Redis, Depends(get_redis)]):
    return {"status": "ok"}
