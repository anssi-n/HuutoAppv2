from datetime import datetime, UTC
from sqlalchemy import DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column
from db import Base
from common import common_types

class TaskLog(Base):
    __tablename__ = "task_log"

    task: Mapped[common_types.TaskType]
    status: Mapped[common_types.TaskStatus]
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    details: Mapped[JSON] = mapped_column(JSON, nullable=True, default=None)
    