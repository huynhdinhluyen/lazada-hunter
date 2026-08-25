import asyncio
import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from loguru import logger
from core.database import init_db, AsyncSessionLocal
from core.models import Product
from core.serializers import serialize_product
from ai_engine.model_router import model_router, TaskComplexity
from ai_engine.product_analyzer import product_analyzer
from services.telegram_service import telegram_service


async def test_full_system():
    logger.info("🧪 [TEST] Khởi tạo Database...")
    await init_db()

    # 1. Test Dynamic Model Router
    logger.info("🧪 [TEST 1] Kiểm tra Dynamic Model Router...")
    prompt = "Trả về đúng JSON: {\"status\": \"ok\", \"model_tested\": \"llama3\"}"
    try:
        json_res, model_used = await model_router.generate_json(
            prompt=prompt,
            complexity=TaskComplexity.LOW
        )
        logger.info(f"✅ Model Router hoạt động: {model_used} -> {json_res}")
    except Exception as e:
        logger.error(f"❌ Model Router lỗi: {e}")

    # 2. Test Product Analyzer
    logger.info("🧪 [TEST 2] Kiểm tra AI Product Analyzer...")
    sample_product = {
        "id": 999,
        "name": "[Chính Hãng 100%] Chuột Không Dây Gaming Logitech G304 Lightspeed 12000 DPI Cảm Biến Hero",
        "current_price": 699000,
        "original_price": 990000,
        "discount_percentage": 29.4,
        "rating_star": 4.9,
        "rating_count": 1420,
        "historical_sold": 4500,
        "brand": "Logitech",
        "shop_name": "Logitech Official Flagship Store",
        "is_official_shop": True,
        "shop_location": "TP. Hồ Chí Minh",
        "url": "https://www.lazada.vn/products/chuot-choi-game-khong-day-logitech-g304-i228795551.html",
        "raw_data": {
            "highlights": [
                "Cảm biến Hero 12.000 DPI thế hệ mới",
                "Công nghệ không dây Lightspeed siêu nhanh 1ms",
                "Thời lượng pin 250h với 1 viên pin AA",
                "Trọng lượng nhẹ 99g"
            ],
            "reviews": [
                "Chuột cầm rất đầm tay, pin xài 3 tháng chưa hết, kết nối không delay tí nào.",
                "Rất ưng ý, hàng chính hãng check serial chuẩn. Nút click hơi to một chút nhưng chấp nhận được.",
                "Chuột nhẹ, mắt đọc mượt, chơi CS2 và Valorant cực kỳ chuẩn xác."
            ]
        }
    }

    try:
        ai_res = await product_analyzer.analyze_product(sample_product)
        logger.info("✅ AI Product Analyzer thành công!")
        logger.info(f"   • Tên chuẩn hóa: {ai_res.normalized_name}")
        logger.info(f"   • Điểm cảm xúc: {ai_res.sentiment_score}/10")
        logger.info(f"   • Ưu điểm: {ai_res.pros}")
        logger.info(f"   • Nhược điểm: {ai_res.cons}")
        logger.info(f"   • Giá tối ưu: {ai_res.recommended_price_optimal:,.0f} đ")
        logger.info(f"   • Model đã dùng: {ai_res.model_used}")
    except Exception as e:
        logger.error(f"❌ AI Product Analyzer lỗi: {e}")

    # 3. Test Telegram Bulletin Formatter
    logger.info("🧪 [TEST 3] Kiểm tra Telegram Bulletin Formatter...")
    try:
        bulletin_ok = await telegram_service.send_product_bulletin(
            product=sample_product,
            ai_data=ai_res.model_dump() if 'ai_res' in locals() else None
        )
        logger.info(f"✅ Gửi Bản Tin Telegram: {bulletin_ok}")
    except Exception as e:
        logger.error(f"❌ Gửi Telegram lỗi: {e}")

    logger.info("🎉 [TEST] Toàn bộ bài test Backend & AI đã hoàn tất!")


if __name__ == "__main__":
    asyncio.run(test_full_system())
