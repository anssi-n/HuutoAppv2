from pydantic import BaseModel
from datetime import datetime
from common import common_types

class Task(BaseModel):
    task: common_types.TaskType
    log_id: int
    id: int
    add_keywords: int | None = None
        
class QueueMessage(BaseModel):
    task: Task
    created_at: datetime
    retries: int