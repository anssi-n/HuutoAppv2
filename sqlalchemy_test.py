from db import sync_engine
from schemas import huutoapp_queue_schema
from common import common_types
from typing import Sequence
import httpx
import re
import json
from typing import Any
from sqlalchemy import select, cast, Text, VARCHAR, text, String
from sqlalchemy.orm import Session, selectinload
from models import items_model, task_log_model
from sqlalchemy.orm.attributes import flag_modified

parent_id = "fe2f459b-4582-4e4a-8da5-8cfa3b4f38c4"
# with Session(sync_engine) as session:
#     # results = session.query(task_log_model.TaskLog).filter(task_log_model.TaskLog.details["parent_id"].cast(Text) == parent_id).all()
#     result = session.execute(select(task_log_model.TaskLog).filter(task_log_model.TaskLog.details["parent_id"].cast(String) == "fe2f459b-4582-4e4a-8da5-8cfa3b4f38c4"))
#     # results = session.query(task_log_model.TaskLog).filter(task_log_model.TaskLog.details["parent_id"].cast(VARCHAR) == parent_id).all()
#     log = result.scalars().all()
#     print(log)

#     # result = session.execute(text("SELECT * FROM task_log WHERE details->>'parent_id'='fe2f459b-4582-4e4a-8da5-8cfa3b4f38c4'")).all()
#     # for log in result:
#     #     print(log.id)
#     #     print(log)


def get_parent_log_id(parent_id: str) -> int | None:
    with Session(sync_engine) as session:
        result = session.execute(text("SELECT * FROM task_log WHERE details->>'parent_id' = :parent_id"), {'parent_id': parent_id}).first()
        if result is not None:
            return result.id
    return None
    

print(get_parent_log_id(parent_id))