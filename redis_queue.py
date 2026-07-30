from redis.asyncio import Redis, ConnectionPool
from config import settings


REDIS_URL = f"redis://:{settings.redis_password.get_secret_value()}@{settings.redis_host}:{settings.redis_port}/{settings.redis_db_number}"

class RedisClient:
    def __init__(self) -> None:
        self.pool: ConnectionPool | None = None
        self.client: Redis | None = None

    async def connect(self) -> None:
        self.pool = ConnectionPool.from_url(
            REDIS_URL,
            max_connections=50,
            decode_responses=True,
            socket_timeout=20,           # Needed after redis library update from  7.4.0 to 8.0.1
            socket_connect_timeout=10,
            socket_keepalive=True,
            health_check_interval=30,    # Very important in K8s
            retry_on_timeout=True           
        )
        
        self.client = Redis(connection_pool=self.pool)

    async def disconnect(self) -> None:
        if self.client:
            await self.client.close()
        if self.pool:
            await self.pool.disconnect()
    
    def get_client(self) -> Redis | None:
        if self.client:
            return self.client
        return None

redis_client = RedisClient()

async def get_redis() -> Redis | None:
    return redis_client.get_client()