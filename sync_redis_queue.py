import redis
import socket
from redis.retry import Retry
from redis.backoff import ExponentialBackoff
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
                    decode_responses=True,

                    socket_timeout=45,           # Must be higher than brpop timeout
                    socket_connect_timeout=10,
                    socket_keepalive=True,
                    socket_keepalive_options={
                        socket.TCP_KEEPIDLE: 60,
                        socket.TCP_KEEPINTVL: 10,
                        socket.TCP_KEEPCNT: 6,
                    },
                    health_check_interval=30,    # Very important
                    retry_on_timeout=True,
                    retry=Retry(
                        ExponentialBackoff(base=0.1, cap=2.0),
                        retries=5,
                        supported_errors=(redis.exceptions.TimeoutError, redis.exceptions.ConnectionError)
                    )
    )          

    try:
        db.ping()
    except Exception as err:
        logger.info(f"Connection to Redis failed. {err}")
        raise 
    logger.info("Redis connection established.")
    return db
