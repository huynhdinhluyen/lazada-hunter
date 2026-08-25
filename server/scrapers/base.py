import abc
import asyncio
from typing import List, Optional, Any, Dict
from loguru import logger

from core.schemas import ProductCreate
from scrapers.anti_bot import human_delay
from scrapers.proxy_manager import proxy_manager
from config.settings import settings


class BaseScraper(abc.ABC):
    """
    Lớp cơ sở trừu tượng cho mọi crawler sàn thương mại điện tử
    Tích hợp:
    - Quản lý vòng đời kết nối
    - Tự động retry có backoff & jitter
    - Bắt lỗi WAF/Rate limit (403/429) để tự động gọi proxy_manager xoay IP
    """
    def __init__(self, platform_name: str):
        self.platform_name = platform_name
        self.max_retries = settings.CRAWLER_MAX_RETRIES
        self.min_delay = settings.CRAWLER_MIN_DELAY
        self.max_delay = settings.CRAWLER_MAX_DELAY

    @abc.abstractmethod
    async def search(self, keyword: str, page: int = 1, limit: int = 20) -> List[ProductCreate]:
        """Tìm kiếm sản phẩm theo từ khóa"""
        pass

    @abc.abstractmethod
    async def get_product_detail(self, product_url: str) -> Optional[ProductCreate]:
        """Lấy chi tiết sản phẩm theo URL"""
        pass

    async def execute_with_retry(self, action_func, *args, **kwargs) -> Any:
        """
        Thực thi một tác vụ cào với cơ chế tự động thử lại (Exponential Backoff + Jitter)
        và tự động xoay IP khi bị chặn.
        """
        attempt = 0
        while attempt < self.max_retries:
            attempt += 1
            try:
                # Tạo khoảng trễ giả lập người dùng trước mỗi request
                await human_delay(self.min_delay, self.max_delay)
                return await action_func(*args, **kwargs)
            except Exception as e:
                err_msg = str(e).lower()
                logger.warning(
                    f"[{self.platform_name.upper()}] Thử lần {attempt}/{self.max_retries} thất bại: {e}"
                )
                
                # Kiểm tra nếu bị chặn bởi Rate limit hoặc WAF (403, 429, captcha, bot detected)
                if any(x in err_msg for x in ["403", "429", "block", "captcha", "challenge", "forbidden"]):
                    logger.warning(f"[{self.platform_name.upper()}] Phát hiện WAF/Anti-bot, kích hoạt xoay IP...")
                    await proxy_manager.rotate_ip()
                
                if attempt >= self.max_retries:
                    logger.error(f"[{self.platform_name.upper()}] Đã hết số lần thử lại cho tác vụ.")
                    raise
                
                # Exponential backoff
                wait_time = (2 ** attempt) + (attempt * 0.5)
                logger.info(f"Chờ {wait_time:.1f}s trước khi thử lại...")
                await asyncio.sleep(wait_time)
