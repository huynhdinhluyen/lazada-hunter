import json
from typing import Optional, Any
import redis.asyncio as aioredis
from loguru import logger

from config.settings import settings


class RedisClientManager:
    """
    Quản lý kết nối tập trung tới Redis Cloud (In-Memory Hot Cache & Task Queue)
    - Connection Pooling tự động
    - Tự động serialize / deserialize JSON
    - Thao tác non-blocking với AsyncIO
    - Graceful error handling (không làm crash ứng dụng nếu mất kết nối)
    """

    def __init__(self):
        self._pool: Optional[aioredis.ConnectionPool] = None
        self._client: Optional[aioredis.Redis] = None

    def get_client(self) -> aioredis.Redis:
        """Khởi tạo hoặc trả về client Redis với Connection Pool an toàn"""
        if self._client is None:
            pwd = settings.get_redis_password()
            self._pool = aioredis.ConnectionPool(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                password=pwd,
                username=settings.REDIS_USERNAME or None,
                db=settings.REDIS_DB,
                decode_responses=settings.REDIS_DECODE_RESPONSE,
                max_connections=20,
                socket_timeout=5.0,
                socket_connect_timeout=5.0,
            )
            self._client = aioredis.Redis(connection_pool=self._pool)
            logger.info(f"⚡ Đã khởi tạo Redis Async Client Pool tới {settings.REDIS_HOST}:{settings.REDIS_PORT}")
        return self._client

    async def ping(self) -> bool:
        """Kiểm tra tình trạng kết nối tới Redis"""
        try:
            client = self.get_client()
            return await client.ping()
        except Exception as e:
            logger.warning(f"⚠️ Không thể ping tới Redis Cloud: {e}")
            return False

    async def get_json(self, key: str) -> Optional[Any]:
        """Đọc và tự động parse JSON từ Redis"""
        try:
            client = self.get_client()
            val = await client.get(key)
            if val:
                return json.loads(val)
            return None
        except Exception as e:
            logger.error(f"Lỗi khi đọc JSON từ Redis (Key: {key}): {e}")
            return None

    async def set_json(self, key: str, value: Any, ex: Optional[int] = None) -> bool:
        """Serialize JSON và lưu vào Redis với TTL tự hủy (ex tính bằng giây)"""
        try:
            client = self.get_client()
            json_str = json.dumps(value, ensure_ascii=False)
            await client.set(key, json_str, ex=ex)
            return True
        except Exception as e:
            logger.error(f"Lỗi khi ghi JSON vào Redis (Key: {key}): {e}")
            return False

    async def close(self):
        """Đóng kết nối khi ứng dụng tắt"""
        if self._client:
            await self._client.aclose()
            self._client = None
        if self._pool:
            await self._pool.disconnect()
            self._pool = None
            logger.info("🛑 Đã đóng kết nối Redis Pool an toàn.")


redis_client = RedisClientManager()
