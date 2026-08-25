import argparse
import asyncio
import sys
import uuid
from pathlib import Path

# Đảm bảo root path trong sys.path
root_dir = Path(__file__).resolve().parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import warnings

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

if sys.platform == "win32":
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from loguru import logger
from core.database import init_db, AsyncSessionLocal
from scrapers.shopee_scraper import ShopeeScraper
from scrapers.lazada_scraper import LazadaScraper
from services.data_pipeline import pipeline_service
from core.models import Product, PriceHistory
from core.schemas import ChatRequest
from ai_engine.shopping_assistant import shopping_assistant
from sqlalchemy import select, func


async def crawl_command(keyword: str, platform: str, limit: int):
    """Lệnh cào sản phẩm theo từ khóa và lưu vào PostgreSQL"""
    logger.info(f"🚀 Bắt đầu tác vụ cào dữ liệu cho từ khóa: '{keyword}' (Sàn: {platform.upper()}, Số lượng: {limit})")
    await init_db()

    products = []
    
    # 1. Cào Lazada
    if platform in ["lazada", "all"]:
        lazada = LazadaScraper()
        try:
            laz_items = await lazada.search(keyword=keyword, limit=limit)
            products.extend(laz_items)
            logger.info(f"✅ [LAZADA] Thu thập được {len(laz_items)} sản phẩm.")
        except Exception as e:
            logger.error(f"❌ [LAZADA] Lỗi: {e}")

    # 2. Cào Shopee
    if platform in ["shopee", "all"]:
        shopee = ShopeeScraper()
        try:
            shp_items = await shopee.search(keyword=keyword, limit=limit)
            products.extend(shp_items)
            logger.info(f"✅ [SHOPEE] Thu thập được {len(shp_items)} sản phẩm.")
        except Exception as e:
            logger.error(f"❌ [SHOPEE] Lỗi: {e}")

    # 3. Đẩy vào PostgreSQL
    if products:
        async with AsyncSessionLocal() as session:
            new_cnt, upd_cnt, alerts = await pipeline_service.process_scraped_products(session, products)
            logger.info(f"📦 Pipeline Database: {new_cnt} mới, {upd_cnt} cập nhật, {len(alerts)} cảnh báo biến động giá.")

    # 4. Hiển thị bảng kết quả
    async with AsyncSessionLocal() as session:
        recent_prods = (
            await session.execute(
                select(Product)
                .filter(Product.name.ilike(f"%{keyword.split()[0]}%"))
                .order_by(Product.id.desc())
                .limit(limit)
            )
        ).scalars().all()

        print("\n" + "=" * 115)
        print(f"{'ID':<4} | {'SAN':<8} | {'TEN SAN PHAM':<45} | {'GIA HIEN TAI':<15} | {'DA BAN':<10} | {'DANH GIA':<8}")
        print("=" * 115)
        for p in recent_prods:
            short_name = (p.name[:42] + "...") if len(p.name) > 45 else p.name
            price_str = f"{p.current_price:,.0f} đ"
            sold_str = f"{p.historical_sold:,}" if p.historical_sold else "0"
            rating_str = f"{p.rating_star}*" if p.rating_star else "N/A"
            print(f"{p.id:<4} | {p.platform.upper():<8} | {short_name:<45} | {price_str:<15} | {sold_str:<10} | {rating_str:<8}")
        print("=" * 115 + "\n")


async def chat_interactive_session():
    """Chế độ Chat tương tác trực tiếp qua dòng lệnh (CLI Chatbot)"""
    await init_db()
    session_id = str(uuid.uuid4())
    print("\n" + "=" * 80)
    print("🤖 CHÀO MỪNG BẠN ĐẾN VỚI AI SHOPPING ASSISTANT (Shopee / Lazada Smart Advisor)")
    print("💡 Nhập bất kỳ câu hỏi mua sắm nào (Gõ 'exit' hoặc 'quit' để thoát).")
    print(f"🔑 Session ID: {session_id}")
    print("=" * 80 + "\n")

    while True:
        try:
            user_input = input("\n👤 Bạn: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ["exit", "quit", "q"]:
                print("👋 Tạm biệt bạn! Chúc bạn săn được nhiều deal hời!")
                break

            print("\n🤖 AI Assistant đang suy nghĩ và tổng hợp dữ liệu...\n")
            
            async with AsyncSessionLocal() as db_session:
                req = ChatRequest(message=user_input, session_id=session_id)
                res = await shopping_assistant.chat(db_session, req)
                
                cache_badge = " [⚡ CACHE HIT]" if res.cached else ""
                print(f"--- [INTENT: {res.intent.upper()}]{cache_badge} ---")
                print(res.message)
                print("-" * 50)

        except (KeyboardInterrupt, EOFError):
            print("\n👋 Tạm biệt bạn!")
            break
        except Exception as e:
            logger.error(f"Lỗi phiên chat: {e}")


def main():
    parser = argparse.ArgumentParser(description="E-Commerce Intelligent Crawler & AI Assistant CLI")
    subparsers = parser.add_subparsers(dest="command", help="Lệnh thực thi")

    # Command: init-db
    subparsers.add_parser("init-db", help="Khởi tạo database PostgreSQL và tạo schema")

    # Command: crawl
    crawl_parser = subparsers.add_parser("crawl", help="Cào dữ liệu sản phẩm")
    crawl_parser.add_argument("-k", "--keyword", type=str, default="chuot khong day", help="Từ khóa tìm kiếm")
    crawl_parser.add_argument("-p", "--platform", type=str, default="all", choices=["shopee", "lazada", "all"], help="Sàn TMĐT")
    crawl_parser.add_argument("-l", "--limit", type=int, default=10, help="Số lượng sản phẩm lấy mỗi sàn")

    # Command: server
    server_parser = subparsers.add_parser("server", help="Khởi động FastAPI REST API Server")
    server_parser.add_argument("--host", type=str, default="0.0.0.0", help="Địa chỉ host")
    server_parser.add_argument("--port", type=int, default=8000, help="Cổng chạy server")
    server_parser.add_argument("--reload", action="store_true", default=True, help="Bật chế độ Auto-Reload (Mặc định: True)")
    server_parser.add_argument("--no-reload", dest="reload", action="store_false", help="Tắt chế độ Auto-Reload")

    # Command: chat
    subparsers.add_parser("chat", help="Khởi động giao diện Chatbot Trợ lý Mua sắm tương tác trực tiếp")

    # Command: test
    subparsers.add_parser("test", help="Chạy bộ kiểm thử toàn diện")

    args = parser.parse_args()

    if args.command == "server":
        import uvicorn
        logger.info(f"🌐 Khởi chạy API Server tại http://{args.host}:{args.port} (Swagger docs: http://{args.host}:{args.port}/docs)")
        uvicorn.run("api.server:app", host=args.host, port=args.port, reload=args.reload, loop="asyncio")
    elif args.command == "init-db":
        asyncio.run(init_db())
    elif args.command == "crawl":
        asyncio.run(crawl_command(args.keyword, args.platform, args.limit))
    elif args.command == "chat":
        asyncio.run(chat_interactive_session())
    elif args.command == "test" or not args.command:
        from tests.test_chat_assistant import run_comprehensive_chat_tests
        asyncio.run(run_comprehensive_chat_tests())


if __name__ == "__main__":
    main()
