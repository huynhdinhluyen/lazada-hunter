from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from loguru import logger

from core.models import Product
from services.cache_service import cache_service, normalize_query_text, compute_query_hash


class QueryCacheManager:
    """
    Quản lý Semantic Cache giữa các người dùng (Cross-User Cache) qua Redis Cloud:
    - 100% In-Memory trên Redis Cloud (< 0.5ms)
    - Tự động nhận diện khi User B hỏi lại câu của User A
    - Tự động hết hạn (TTL 2h cho deal/giá, 24h cho chitchat)
    - Lấy trực tiếp danh sách Product entities từ PostgreSQL nếu có product_ids
    """

    @staticmethod
    async def get_cached_response(
        session: AsyncSession, 
        raw_query: str
    ) -> Optional[Tuple[Dict[str, Any], List[Product]]]:
        """
        Tra cứu cache trong Redis Cloud.
        Trả về (CacheDict, Danh sách Product) nếu Cache Hit và còn hạn.
        """
        cache_entry = await cache_service.get_query_cache(raw_query)
        if not cache_entry:
            return None

        # Lấy danh sách sản phẩm liên quan từ PostgreSQL nếu có
        products = []
        product_ids = cache_entry.get("product_ids", [])
        if product_ids:
            try:
                prod_stmt = select(Product).where(Product.id.in_(product_ids))
                prod_res = await session.execute(prod_stmt)
                products = list(prod_res.scalars().all())
            except Exception as e:
                logger.warning(f"Lỗi khi nạp products từ DB cho cache: {e}")

        return cache_entry, products

    @staticmethod
    async def save_cache(
        session: AsyncSession,
        raw_query: str,
        intent: str,
        response_markdown: str,
        product_ids: Optional[List[int]] = None,
        ttl_seconds: Optional[int] = None
    ) -> Dict[str, Any]:
        """Lưu kết quả truy vấn mới vào Redis Cloud với TTL phù hợp"""
        return await cache_service.set_query_cache(
            raw_query=raw_query,
            intent=intent,
            response_markdown=response_markdown,
            product_ids=product_ids or [],
            ttl_seconds=ttl_seconds
        )


query_cache_manager = QueryCacheManager()
