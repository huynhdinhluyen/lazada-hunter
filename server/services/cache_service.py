import hashlib
import re
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from loguru import logger

from config.settings import settings
from core.redis_client import redis_client


def normalize_query_text(text: str) -> str:
    """
    Chuẩn hóa câu truy vấn tiếng Việt để gom các câu hỏi đồng nghĩa:
    Ví dụ: 'Tư vấn chuột không dây gaming 300k ạ?' -> 'chuột không dây gaming 300k'
    """
    s = text.lower().strip()
    # 1. Bỏ dấu câu và ký tự đặc biệt
    s = re.sub(r"[\?\.\,\!\@\#\$\%\^\&\*\(\)\-\_\+\=\;\:\'\"\/]", " ", s)

    # 2. Bảo vệ các cụm từ sản phẩm đặc thù chứa chữ 'không'
    s = s.replace("không dây", "khong_day")
    s = s.replace("tai nghe bluetooth", "tai_nghe_khong_day")
    s = s.replace("tai nghe không dây", "tai_nghe_khong_day")
    
    # 3. Chuẩn hóa từ đồng nghĩa mua sắm
    synonyms = [
        (r"\bchơi game\b", "gaming"),
        (r"\bphím cơ\b", "bàn phím cơ"),
        (r"\btầm\b", ""),
        (r"\bkhoảng\b", ""),
        (r"\bgiá\b", ""),
        (r"\bdưới\b", ""),
        (r"\btr\b", "triệu"),
        (r"\btriệu\b", "tr"),
    ]
    for pattern, rep in synonyms:
        s = re.sub(pattern, rep, s)

    # 4. Bỏ stop-words tiếng Việt thừa (từ xưng hô, đệm)
    stop_words = [
        "tư vấn", "cho mình", "cho em", "cho tôi", "hỏi", "tìm", "mua", "với", "nhé", 
        "ạ", "ơi", "ad", "shop", "giúp", "nào", "ổn", "ngon", "tốt", "được", "bạn ơi"
    ]
    for w in stop_words:
        s = re.sub(rf"\b{w}\b", "", s)

    # Khôi phục cụm từ đã bảo vệ
    s = s.replace("khong_day", "không dây")
    s = s.replace("tai_nghe_khong_day", "tai nghe không dây")

    # 5. Chuẩn hóa khoảng trắng
    return re.sub(r"\s+", " ", s).strip()


def compute_query_hash(normalized_text: str) -> str:
    """Tạo MD5 Hash từ câu truy vấn đã chuẩn hóa"""
    return hashlib.md5(normalized_text.encode("utf-8")).hexdigest()


class HotCacheService:
    """
    Dịch vụ Hot Cache & Semantic Deduplication trên Redis Cloud:
    - Lưu trữ hoàn toàn trên RAM Redis Cloud (độ trễ < 0.5ms, 0 write overhead trên PostgreSQL).
    - Áp dụng Dynamic Tiered TTL:
      * 2 giờ (7,200s) cho Giá & Gợi ý deal (bám sát khung giờ Flash Sale Lazada/Shopee).
      * 24 giờ (86,400s) cho Chitchat & Ngoài lề.
    - Quản lý Hit Count qua INCR trên Redis.
    """

    CACHE_PREFIX = "cache:query:"
    INDEX_KEY = "cache:active_keys"
    TOTAL_HITS_KEY = "stats:total_cache_hits"

    @classmethod
    async def get_query_cache(cls, raw_query: str) -> Optional[Dict[str, Any]]:
        """Lấy kết quả cache từ Redis Cloud. Trả về dict nếu Cache Hit."""
        normalized = normalize_query_text(raw_query)
        if not normalized:
            return None

        q_hash = compute_query_hash(normalized)
        cache_key = f"{cls.CACHE_PREFIX}{q_hash}"

        data = await redis_client.get_json(cache_key)
        if not data:
            return None

        # Tăng hit count bằng Redis Atomic Increment
        try:
            client = redis_client.get_client()
            await client.incr(cls.TOTAL_HITS_KEY)
            data["hit_count"] = data.get("hit_count", 0) + 1
            # Cập nhật lại hit count trong object nếu còn TTL
            ttl = await client.ttl(cache_key)
            if ttl > 0:
                await redis_client.set_json(cache_key, data, ex=ttl)
        except Exception as e:
            logger.debug(f"Không thể tăng hit count trên Redis: {e}")

        logger.info(f"⚡ [REDIS CACHE HIT] Tìm thấy '{normalized}' (Hash: {q_hash[:8]}, Hits: {data.get('hit_count', 1)})")
        return data

    @classmethod
    async def set_query_cache(
        cls,
        raw_query: str,
        intent: str,
        response_markdown: str,
        product_ids: Optional[List[int]] = None,
        ttl_seconds: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Lưu kết quả truy vấn mới vào Redis Cloud với TTL phù hợp.
        Mặc định: 7,200s (2h) cho deal hàng hóa / 86,400s (24h) cho chitchat.
        """
        normalized = normalize_query_text(raw_query)
        q_hash = compute_query_hash(normalized)
        cache_key = f"{cls.CACHE_PREFIX}{q_hash}"

        # Xác định TTL dựa vào bản chất câu hỏi (Tránh bỏ lỡ Flash Sale)
        if ttl_seconds is None:
            if intent in ["chitchat_out_of_scope", "safety_guard"]:
                ttl_seconds = settings.CACHE_CHITCHAT_TTL_SECONDS
            else:
                ttl_seconds = settings.CACHE_HOT_TTL_SECONDS  # 2 giờ

        cache_data = {
            "id": q_hash,
            "query_hash": q_hash,
            "raw_query": raw_query,
            "normalized_query": normalized,
            "intent": intent,
            "response_markdown": response_markdown,
            "product_ids": product_ids or [],
            "hit_count": 1,
            "ttl_seconds": ttl_seconds,
            "created_at": datetime.now(timezone.utc).isoformat()
        }

        # Lưu vào Redis với TTL tự hủy
        await redis_client.set_json(cache_key, cache_data, ex=ttl_seconds)

        # Lưu hash vào Index Set để quản lý danh sách
        try:
            client = redis_client.get_client()
            await client.sadd(cls.INDEX_KEY, q_hash)
        except Exception as e:
            logger.debug(f"Không thể cập nhật cache index: {e}")

        logger.debug(f"💾 [REDIS CACHE SAVED] '{normalized}' (Hash: {q_hash[:8]}, TTL: {ttl_seconds}s)")
        return cache_data

    @classmethod
    async def list_cached_queries(cls, limit: int = 50) -> List[Dict[str, Any]]:
        """Lấy danh sách các câu hỏi đang còn hạn trong Redis Hot Cache"""
        try:
            client = redis_client.get_client()
            all_hashes = await client.smembers(cls.INDEX_KEY)
            if not all_hashes:
                return []

            results = []
            stale_hashes = []

            for h in list(all_hashes):
                cache_key = f"{cls.CACHE_PREFIX}{h}"
                data = await redis_client.get_json(cache_key)
                if data:
                    results.append(data)
                else:
                    stale_hashes.append(h)

            # Dọn dẹp index nếu key đã hết hạn TTL
            if stale_hashes:
                await client.srem(cls.INDEX_KEY, *stale_hashes)

            # Sắp xếp theo số lượt hit giảm dần
            results.sort(key=lambda x: x.get("hit_count", 0), reverse=True)
            return results[:limit]

        except Exception as e:
            logger.error(f"Lỗi khi lấy danh sách cache từ Redis: {e}")
            return []

    @classmethod
    async def clear_all_cache(cls) -> int:
        """Xóa toàn bộ các mục Hot Cache trên Redis Cloud"""
        try:
            client = redis_client.get_client()
            all_hashes = await client.smembers(cls.INDEX_KEY)
            count = 0
            if all_hashes:
                keys_to_delete = [f"{cls.CACHE_PREFIX}{h}" for h in all_hashes]
                keys_to_delete.append(cls.INDEX_KEY)
                deleted = await client.delete(*keys_to_delete)
                count = max(0, deleted - 1)
            logger.info(f"🗑️ Đã dọn sạch {count} mục Hot Cache trên Redis Cloud.")
            return count
        except Exception as e:
            logger.error(f"Lỗi khi dọn dẹp cache trên Redis: {e}")
            return 0

    @classmethod
    async def delete_single_cache(cls, query_hash: str) -> bool:
        """Xóa một mục Cache cụ thể bằng Hash"""
        try:
            client = redis_client.get_client()
            cache_key = f"{cls.CACHE_PREFIX}{query_hash}"
            deleted = await client.delete(cache_key)
            await client.srem(cls.INDEX_KEY, query_hash)
            return deleted > 0
        except Exception as e:
            logger.error(f"Lỗi khi xóa cache mục {query_hash}: {e}")
            return False

    @classmethod
    async def get_cache_stats(cls) -> Dict[str, int]:
        """Lấy số liệu thống kê cache tức thời từ Redis"""
        try:
            client = redis_client.get_client()
            total_entries = await client.scard(cls.INDEX_KEY)
            total_hits_val = await client.get(cls.TOTAL_HITS_KEY)
            total_hits = int(total_hits_val) if total_hits_val else 0
            return {
                "total_cache_entries": total_entries,
                "total_cache_hits": total_hits
            }
        except Exception as e:
            logger.error(f"Lỗi khi đọc thống kê cache từ Redis: {e}")
            return {"total_cache_entries": 0, "total_cache_hits": 0}


cache_service = HotCacheService()
