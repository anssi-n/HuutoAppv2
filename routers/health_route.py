from fastapi import Depends, APIRouter, status, HTTPException
from redis.asyncio import Redis
from typing import Annotated
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from db import get_db
from redis_queue import get_redis

router = APIRouter()

@router.get("", status_code=status.HTTP_200_OK)
async def health():
    return {"status": "ok"}

@router.get("/ready", status_code=status.HTTP_200_OK)
async def readiness(db: Annotated[AsyncSession, Depends(get_db)],
                    redis: Annotated[Redis | None, Depends(get_redis)]):
    try:
        result = await db.execute(text("SELECT 1"))
        if result.scalar_one_or_none() != 1:
            raise HTTPException(status_code=503, detail="database not ready")
        if redis is None or not await redis.ping():
            raise HTTPException(status_code=503, detail="redis not ready")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"dependency not ready: {exc}") from exc
    return {"status": "ready"}
