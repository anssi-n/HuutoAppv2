from fastapi import HTTPException, status, Depends, Query, APIRouter

from typing import Annotated
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from common import common_types
from schemas import tasklog_schema
from models import task_log_model

from db import get_db

router = APIRouter()

@router.get("", response_model=tasklog_schema.PaginatedTaskLogResponse)
async def get_task_logs(db: Annotated[AsyncSession, Depends(get_db)], 
                        skip: Annotated[int, Query(ge=0)] = 0, 
                        limit: Annotated[int, Query(ge=1, le=100)] = 10,
                        status: common_types.TaskStatus | None = None):

    count_query = select(func.count()).select_from(task_log_model.TaskLog)
    log_query = select(task_log_model.TaskLog).order_by(task_log_model.TaskLog.id).offset(skip).limit(limit)

    if status is not None:
        count_query = count_query.where(task_log_model.TaskLog.status == status)
        log_query = log_query.where(task_log_model.TaskLog.status == status)

    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0
    result = await db.execute(log_query)

    logs = result.scalars().all()
    has_more = skip + len(logs) < total                               

    return tasklog_schema.PaginatedTaskLogResponse(
        items=[tasklog_schema.TaskLogResponse.model_validate(log) for log in logs],
        total=total,
        skip=skip,
        limit=limit,
        has_more=has_more
    )

@router.get("/{log_id}", response_model=tasklog_schema.TaskLogResponse)
async def get_log(log_id: int, db: Annotated[AsyncSession, Depends(get_db)]):

    result = await db.execute(select(task_log_model.TaskLog).
                              where(task_log_model.TaskLog.id == log_id))
    log = result.scalars().first()
    if not log:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Log entry not found")
    return log