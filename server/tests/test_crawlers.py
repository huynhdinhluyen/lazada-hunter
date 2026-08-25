import asyncio
import sys
from pathlib import Path

# Đảm bảo root project nằm trong sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from loguru import logger
from sqlalchemy import select, func

from core.database import init_db, AsyncSessionLocal
from scrapers.lazada_scraper import LazadaScraper
from services.data_pipeline import pipeline_service
from core.models import Product, PriceHistory


async def run_crawler_verification():
    logger.info("==================================================================")
    logger.info(" BẮT ĐẦU KIỂM THỬ THỰC TẾ: LAZADA CRAWLER & POSTGRESQL")
    logger.info("==================================================================")

    # 1. Khởi tạo Database PostgreSQL
    logger.info("[1/4] Khởi tạo Database PostgreSQL & Schema...")
    await init_db()
    logger.info("✅ Database PostgreSQL đã sẵn sàng.")

    keyword = "chuot khong day"
    limit = 10
    
    # 2. Test Lazada Crawler
    logger.info(f"\n[2/4] Tiến hành test Lazada Crawler với từ khóa: '{keyword}' (Lấy {limit} sản phẩm)...")
    lazada_scraper = LazadaScraper()
    lazada_products = []
    try:
        lazada_products = await lazada_scraper.search(keyword=keyword, page=1, limit=limit)
        logger.info(f"✅ [LAZADA] Thu thập thành công {len(lazada_products)} sản phẩm.")
        for idx, p in enumerate(lazada_products[:5], 1):
            logger.info(f"   {idx}. [{p.platform.upper()}] {p.name[:45]}... | Giá: {p.current_price:,.0f}đ | Đã bán: {p.historical_sold:,} | Shop: {p.shop_name or 'N/A'}")
    except Exception as e:
        logger.error(f"❌ [LAZADA] Lỗi khi cào: {e}")

    # 3. Đẩy dữ liệu vào PostgreSQL qua Data Pipeline
    logger.info(f"\n[3/4] Đưa {len(lazada_products)} sản phẩm vào PostgreSQL qua Data Pipeline...")
    
    if lazada_products:
        async with AsyncSessionLocal() as session:
            new_cnt, upd_cnt, alerts = await pipeline_service.process_scraped_products(session, lazada_products)
            logger.info(f"✅ Kết quả Pipeline: {new_cnt} sản phẩm mới, {upd_cnt} sản phẩm cập nhật, {len(alerts)} cảnh báo giá.")

    # 4. Kiểm tra trực tiếp dữ liệu trong PostgreSQL
    logger.info("\n[4/4] Kiểm tra trực tiếp dữ liệu đã lưu trong PostgreSQL...")
    async with AsyncSessionLocal() as session:
        prod_count = (await session.execute(select(func.count(Product.id)))).scalar_one()
        history_count = (await session.execute(select(func.count(PriceHistory.id)))).scalar_one()
        
        recent_prods = (await session.execute(select(Product).order_by(Product.id.desc()).limit(10))).scalars().all()
        
        logger.info(f"📊 Thống kê Database PostgreSQL:")
        logger.info(f"   - Tổng số sản phẩm trong bảng 'products': {prod_count}")
        logger.info(f"   - Tổng số bản ghi trong bảng 'price_history': {history_count}")
        logger.info(f"   - 10 sản phẩm mới nhất:")
        for idx, p in enumerate(recent_prods, 1):
            logger.info(f"     {idx}. [ID: {p.id}] [{p.platform.upper()}] {p.name[:50]} | Giá: {p.current_price:,.0f}đ | Shop: {p.shop_name}")


if __name__ == "__main__":
    asyncio.run(run_crawler_verification())
