from datetime import datetime, timedelta
from pydantic import BaseModel, ConfigDict, computed_field,  Json, field_validator
from typing import Any
import json
from common import common_types

class TaskLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task: common_types.TaskType
    status: common_types.TaskStatus
    start_time: datetime
    end_time: datetime | None = None
    details: Json[Any] | None = None

    @computed_field # type: ignore[prop-decorator]
    @property 
    def duration(self) -> timedelta | None:
        if self.end_time is not None:
            return self.end_time - self.start_time
        return None

    @field_validator("details", mode="before")
    @classmethod
    def details_json(cls, value: dict) -> str:
        res = json.dumps(value)
        return res

class PaginatedTaskLogResponse(BaseModel):
   
    items: list[TaskLogResponse]
    total: int
    skip: int
    limit: int
    has_more: bool