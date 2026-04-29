import redis
from config import settings
from logger import logger
from custom_retry import retry

REDIS_URL = f"redis://:{settings.redis_password.get_secret_value()}@{settings.redis_host}:{settings.redis_port}/{settings.redis_db_number}"

@retry(retries=5, delay=10)
def get_redis() -> redis.Redis:
    db = redis.Redis(
                    host=settings.redis_host,
                    port=settings.redis_port,
                    db=settings.redis_db_number,
                    password=settings.redis_password.get_secret_value(),
                    decode_responses=True
    )          

    try:
        db.ping()
    except Exception as err:
        logger.info(f"Connection to Redis failed. {err}")
        raise 
    logger.info("Redis connection established.")
    return db
