import json
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from loguru import logger

from config.settings import settings
from core.redis_client import redis_client


class JobQueueService:
    """
    Quản lý Hàng Đợi và Vòng Đời Tác Vụ Cào Dữ Liệu trên Redis Cloud:
    - 0 write overhead trên PostgreSQL
    - Tự động phân bổ và theo dõi trạng thái: PENDING -> RUNNING -> COMPLETED / FAILED
    - Tự động hết hạn sau 24h (JOB_TTL_SECONDS) để giải phóng RAM
    """

    JOB_KEY_PREFIX = "job:"
    JOB_QUEUE_KEY = "queue:scrape_jobs"
    RECENT_JOBS_KEY = "jobs:recent_ids"
    JOB_SEQ_KEY = "seq:job_id"
    TOTAL_JOBS_KEY = "stats:total_scrape_jobs"

    @classmethod
    async def create_job(
        cls, 
        keyword_or_url: str, 
        platform: str, 
        limit: int = 40
    ) -> Dict[str, Any]:
        """Tạo mới một Job cào dữ liệu và đưa vào hàng đợi Redis"""
        client = redis_client.get_client()

        # Tạo Job ID tăng dần
        job_id = await client.incr(cls.JOB_SEQ_KEY)
        await client.incr(cls.TOTAL_JOBS_KEY)

        now_iso = datetime.now(timezone.utc).isoformat()
        job_data = {
            "id": job_id,
            "keyword_or_url": keyword_or_url,
            "platform": platform,
            "limit": limit,
            "status": "pending",
            "total_items_found": 0,
            "total_items_saved": 0,
            "error_message": None,
            "started_at": None,
            "finished_at": None,
            "created_at": now_iso
        }

        job_key = f"{cls.JOB_KEY_PREFIX}{job_id}"
        await redis_client.set_json(job_key, job_data, ex=settings.JOB_TTL_SECONDS)

        # Lưu ID vào danh sách gần đây
        await client.lpush(cls.RECENT_JOBS_KEY, job_id)
        await client.ltrim(cls.RECENT_JOBS_KEY, 0, 99)  # Giữ tối đa 100 job gần nhất

        # Đẩy vào queue để worker xử lý nếu cần
        await client.lpush(cls.JOB_QUEUE_KEY, json.dumps({"job_id": job_id, "keyword": keyword_or_url, "platform": platform, "limit": limit}))

        logger.info(f"🕷️ [REDIS JOB QUEUE] Đã tạo Job #{job_id} cho từ khóa '{keyword_or_url}' ({platform.upper()})")
        return job_data

    @classmethod
    async def update_job(
        cls,
        job_id: int,
        status: str,
        total_items_found: int = 0,
        total_items_saved: int = 0,
        error_message: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Cập nhật trạng thái tiến trình của Job trên Redis"""
        job_key = f"{cls.JOB_KEY_PREFIX}{job_id}"
        job_data = await redis_client.get_json(job_key)
        if not job_data:
            return None

        now_iso = datetime.now(timezone.utc).isoformat()
        job_data["status"] = status
        
        if status == "running" and not job_data.get("started_at"):
            job_data["started_at"] = now_iso
        
        if status in ["completed", "failed"]:
            job_data["finished_at"] = now_iso
            job_data["total_items_found"] = total_items_found
            job_data["total_items_saved"] = total_items_saved
            if error_message:
                job_data["error_message"] = error_message

        # Cập nhật lại vào Redis với TTL
        client = redis_client.get_client()
        ttl = await client.ttl(job_key)
        ex = ttl if ttl > 0 else settings.JOB_TTL_SECONDS
        await redis_client.set_json(job_key, job_data, ex=ex)

        return job_data

    @classmethod
    async def get_job(cls, job_id: int) -> Optional[Dict[str, Any]]:
        """Lấy thông tin chi tiết một Job"""
        job_key = f"{cls.JOB_KEY_PREFIX}{job_id}"
        return await redis_client.get_json(job_key)

    @classmethod
    async def list_jobs(cls, limit: int = 50) -> List[Dict[str, Any]]:
        """Lấy danh sách các Job gần nhất từ Redis"""
        try:
            client = redis_client.get_client()
            job_ids = await client.lrange(cls.RECENT_JOBS_KEY, 0, limit - 1)
            if not job_ids:
                return []

            jobs = []
            for jid in job_ids:
                job_key = f"{cls.JOB_KEY_PREFIX}{jid}"
                data = await redis_client.get_json(job_key)
                if data:
                    jobs.append(data)

            return jobs
        except Exception as e:
            logger.error(f"Lỗi khi đọc danh sách job từ Redis: {e}")
            return []

    @classmethod
    async def get_total_job_count(cls) -> int:
        """Lấy tổng số job đã thực thi"""
        try:
            client = redis_client.get_client()
            val = await client.get(cls.TOTAL_JOBS_KEY)
            return int(val) if val else 0
        except Exception as e:
            logger.error(f"Lỗi khi đọc tổng số job từ Redis: {e}")
            return 0


job_queue_service = JobQueueService()
