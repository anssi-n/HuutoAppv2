import random
from datetime import datetime, UTC
import redis
from time import sleep
from sync_redis_queue import get_redis
from config import settings
from schemas import huutoapp_queue_schema
from common import common_types

def redis_queue_push(db: redis.Redis, message: str) -> None:
    db.lpush(settings.redis_queue_name, message)

def main(num_messages: int, delay: float = 1) -> None:

    db = get_redis()

    for i in range(num_messages):

        msg = huutoapp_queue_schema.QueueMessage(
            task = huutoapp_queue_schema.Task(
                task = common_types.TaskType(random.choice(tuple([val.value for val in common_types.TaskType]))),
                log_id = i,
                id = random.randrange(1000,2000),
                add_keywords = random.choice((0,1)),
            ),
            created_at=datetime.now(UTC),
            retries=0
        )

        message_json = msg.model_dump_json()
        redis_queue_push(db, message_json)
        sleep(delay)

if __name__ == "__main__":
    main(30, 0.1)
