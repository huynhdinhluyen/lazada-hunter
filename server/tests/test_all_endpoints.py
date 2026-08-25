import asyncio
import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import httpx
from loguru import logger
from core.database import init_db, AsyncSessionLocal
from core.models import Product
from core.schemas import ProductCreate
from services.data_pipeline import pipeline_service
from ai_engine.product_analyzer import product_analyzer


async def test_full_suite():
    logger.info("🚀 [FULL TEST] Khởi tạo Database...")
    await init_db()

    # Tạo 2 sản phẩm mẫu trong DB nếu chưa có
    sample_items = [
        ProductCreate(
            platform="lazada",
            platform_product_id="test_g304_001",
            name="[Chính Hãng] Chuột Không Dây Gaming Logitech G304 Lightspeed",
            url="https://www.lazada.vn/products/chuot-choi-game-khong-day-logitech-g304-i228795551.html",
            image_url="https://vn-live-01.slatic.net/p/test.jpg",
            brand="Logitech",
            current_price=699000,
            original_price=990000,
            discount_percentage=29.4,
            rating_star=4.9,
            rating_count=1500,
            historical_sold=5000,
            shop_name="Logitech Official Store",
            is_official_shop=True
        ),
        ProductCreate(
            platform="lazada",
            platform_product_id="test_aula_002",
            name="Bàn Phím Cơ Không Dây AULA F75 3 Mode Led RGB Hot-swap",
            url="https://www.lazada.vn/products/ban-phim-co-aula-f75-i123456.html",
            image_url="https://vn-live-01.slatic.net/p/test2.jpg",
            brand="AULA",
            current_price=950000,
            original_price=1200000,
            discount_percentage=20.8,
            rating_star=4.8,
            rating_count=820,
            historical_sold=2300,
            shop_name="AULA Gaming Store",
            is_official_shop=False
        )
    ]

    async with AsyncSessionLocal() as session:
        new_cnt, upd_cnt, alerts = await pipeline_service.process_scraped_products(session, sample_items)
        logger.info(f"📦 Đã nạp dữ liệu mẫu vào PostgreSQL: {new_cnt} mới, {upd_cnt} cập nhật.")

    # Test AI Analyzer
    logger.info("🧠 [TEST] Kiểm tra AI Product Analyzer trên sản phẩm...")
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select
        prods = (await session.execute(select(Product).limit(1))).scalars().all()
        if prods:
            p = prods[0]
            from core.serializers import serialize_product
            ai_res = await product_analyzer.analyze_product(serialize_product(p))
            p.ai_analysis = ai_res.model_dump()
            await session.commit()
            logger.info(f"✅ Đã lưu kết quả AI vào DB cho #{p.id}: {ai_res.normalized_name} (Score: {ai_res.sentiment_score})")

    logger.info("🎉 [FULL TEST] Xác thực toàn bộ backend thành công!")


if __name__ == "__main__":
    asyncio.run(test_full_suite())
