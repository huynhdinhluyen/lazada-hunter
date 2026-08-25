import re
from typing import List, Optional
from loguru import logger

from core.schemas import ProductCreate
from scrapers.lazada_scraper import LazadaScraper


class CrawlerService:
    """
    Dịch vụ điều phối Scraper (Mặc định Lazada Việt Nam):
    - Tự động nhận diện đầu vào: Từ khóa tìm kiếm, Link sản phẩm đơn lẻ hoặc Danh sách link (Batch URLs)
    - Cào dữ liệu sản phẩm, giá, đánh giá, thông số và lượt bán từ Lazada
    - Xử lý anti-bot, stealth JS và user-agent rotation
    - Tái sử dụng cho cả Background Worker, API Endpoint và Live Scraper
    """

    @staticmethod
    async def scrape_products(
        keyword_or_url: str, 
        platform: str = "lazada", 
        limit: int = 20,
        input_mode: str = "keyword",
        urls: Optional[List[str]] = None
    ) -> List[ProductCreate]:
        """Thực hiện cào dữ liệu từ Lazada theo từ khóa, link đơn lẻ hoặc danh sách link"""
        collected: List[ProductCreate] = []
        lazada = LazadaScraper()

        # 1. Nếu có mảng urls cụ thể được truyền vào
        if urls and len(urls) > 0:
            logger.info(f"🔗 [CRAWLER SERVICE] Bắt đầu cào danh sách {len(urls)} URLs...")
            try:
                items = await lazada.get_multiple_products_by_urls(urls)
                collected.extend(items)
            except Exception as e:
                logger.error(f"❌ [CRAWLER SERVICE] Lỗi cào danh sách URLs: {e}")
            return collected

        clean_input = keyword_or_url.strip()
        
        # 2. Nhận diện nếu input chứa nhiều dòng link (Batch URLs)
        raw_lines = [line.strip() for line in clean_input.splitlines() if line.strip()]
        if len(raw_lines) > 1 and any("http" in line or "lazada.vn" in line for line in raw_lines):
            logger.info(f"📋 [CRAWLER SERVICE] Phát hiện danh sách {len(raw_lines)} URLs dạng đa dòng...")
            try:
                items = await lazada.get_multiple_products_by_urls(raw_lines)
                collected.extend(items)
            except Exception as e:
                logger.error(f"❌ [CRAWLER SERVICE] Lỗi cào đa dòng URLs: {e}")
            return collected

        # 3. Nhận diện nếu là 1 link URL đơn lẻ
        if "http://" in clean_input or "https://" in clean_input or "lazada.vn" in clean_input or input_mode == "single_url":
            logger.info(f"🔗 [CRAWLER SERVICE] Phát hiện link đơn lẻ: {clean_input[:70]}...")
            try:
                item = await lazada.get_product_detail(clean_input)
                if item:
                    collected.append(item)
            except Exception as e:
                logger.error(f"❌ [CRAWLER SERVICE] Lỗi cào link đơn lẻ: {e}")
            return collected

        # 4. Ngược lại là từ khóa tìm kiếm (Keyword)
        logger.info(f"🔍 [CRAWLER SERVICE] Tìm kiếm theo từ khóa: '{clean_input}' (Limit: {limit})...")
        try:
            items = await lazada.search(keyword=clean_input, limit=limit)
            collected.extend(items)
        except Exception as e:
            logger.warning(f"❌ [CRAWLER SERVICE] Lỗi cào dữ liệu Lazada ({clean_input}): {e}")

        logger.info(f"📦 [CRAWLER SERVICE] Thu thập được {len(collected)} sản phẩm từ LAZADA.")
        return collected


crawler_service = CrawlerService()

