import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from loguru import logger
from sqlalchemy import select, distinct
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config.settings import settings
from core.database import AsyncSessionLocal
from core.models import UserWatchlist, Product
from services.crawler_service import crawler_service
from services.data_pipeline import pipeline_service
from services.telegram_service import telegram_service


class WatchlistPriceTrackerService:
    """
    Dịch vụ Cron Job chạy ngầm định kỳ (Background Scheduled Worker):
    - Tự động quét và đối soát giá toàn bộ sản phẩm đang được người dùng theo dõi (Watchlist)
    - Tự động cào dữ liệu mới nhất từ Lazada
    - Ghi nhận lịch sử biến động giá (PriceHistory)
    - Tự động gửi cảnh báo qua Telegram Bot khi phát hiện giảm giá >= ngưỡng cấu hình
    """

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.is_running = False
        self.last_run_at: Optional[datetime] = None
        self.last_checked_count: int = 0
        self.last_alerts_count: int = 0
        self._is_checking: bool = False

    def start(self):
        """Khởi động Background Scheduler"""
        if not self.is_running:
            try:
                interval = max(settings.WATCHLIST_CRON_INTERVAL_MINUTES, 5)
                self.scheduler.add_job(
                    self.check_watchlist_prices,
                    "interval",
                    minutes=interval,
                    id="watchlist_price_tracker",
                    replace_existing=True,
                )
                self.scheduler.start()
                self.is_running = True
                logger.info(f"⏰ [WATCHLIST CRON] Đã kích hoạt Cron Job quét giá Watchlist (Chu kỳ: {interval} phút/lần)")
            except Exception as e:
                logger.error(f"❌ [WATCHLIST CRON] Không thể khởi động Scheduler: {e}")

    def stop(self):
        """Dừng Scheduler khi tắt server"""
        if self.is_running:
            try:
                self.scheduler.shutdown(wait=False)
                self.is_running = False
                logger.info("🛑 [WATCHLIST CRON] Đã dừng Scheduler quét giá Watchlist.")
            except Exception as e:
                logger.warning(f"Lỗi khi dừng Scheduler: {e}")

    async def check_watchlist_prices(self) -> Dict[str, Any]:
        """Thực thi tác vụ quét giá toàn bộ sản phẩm trong Watchlist"""
        if self._is_checking:
            logger.info("⏳ [WATCHLIST CRON] Tác vụ quét giá đang chạy, bỏ qua lượt gọi trùng lặp.")
            return {"status": "in_progress", "message": "Quá trình quét giá đang diễn ra"}

        self._is_checking = True
        self.last_run_at = datetime.now(timezone.utc)
        logger.info("🔍 [WATCHLIST CRON] Bắt đầu quét cập nhật giá sản phẩm trong Watchlist...")

        total_checked = 0
        total_alerts = 0

        try:
            # 1. Lấy danh sách Product ID duy nhất đang được theo dõi
            async with AsyncSessionLocal() as session:
                stmt = select(distinct(UserWatchlist.product_id))
                res = await session.execute(stmt)
                watched_product_ids = [row[0] for row in res.all()]

                if not watched_product_ids:
                    logger.info("📭 [WATCHLIST CRON] Chưa có sản phẩm nào trong Watchlist cần quét.")
                    self.last_checked_count = 0
                    self.last_alerts_count = 0
                    return {
                        "status": "completed",
                        "checked_count": 0,
                        "alerts_count": 0,
                        "message": "Không có sản phẩm trong Watchlist"
                    }

                # Lấy chi tiết các sản phẩm cần check
                prod_stmt = select(Product).where(Product.id.in_(watched_product_ids))
                prod_res = await session.execute(prod_stmt)
                watched_products = prod_res.scalars().all()
                total_checked = len(watched_products)

            logger.info(f"📋 [WATCHLIST CRON] Tìm thấy {total_checked} sản phẩm trong Watchlist. Tiến hành cào cập nhật giá...")

            # 2. Cào cập nhật từng sản phẩm (Tuần tự hoặc theo mảng URL để tránh bị block)
            for idx, p in enumerate(watched_products, 1):
                if not p.url:
                    continue

                try:
                    logger.debug(f"🔍 [WATCHLIST CRON] ({idx}/{total_checked}) Cập nhật giá: {p.name[:35]}...")
                    scraped_items = await crawler_service.scrape_products(
                        keyword_or_url=p.url,
                        platform=p.platform or "lazada",
                        input_mode="single_url"
                    )

                    if scraped_items:
                        async with AsyncSessionLocal() as db_session:
                            pipeline_res = await pipeline_service.process_scraped_products(
                                db_session, scraped_items
                            )
                            # Kiểm tra nếu có cảnh báo giảm giá
                            if pipeline_res.price_alerts:
                                for alert in pipeline_res.price_alerts:
                                    total_alerts += 1
                                    if settings.TELEGRAM_NOTIFY_ON_PRICE_DROP:
                                        await telegram_service.send_price_drop_alert(alert)

                    await asyncio.sleep(2.0)  # Delay an toàn chống anti-bot

                except Exception as item_err:
                    logger.warning(f"⚠️ [WATCHLIST CRON] Lỗi cập nhật sản phẩm #{p.id}: {item_err}")

            self.last_checked_count = total_checked
            self.last_alerts_count = total_alerts
            logger.info(
                f"✅ [WATCHLIST CRON] Hoàn tất quét giá {total_checked} sản phẩm. "
                f"Phát hiện & thông báo {total_alerts} deal giảm giá sâu!"
            )

            return {
                "status": "completed",
                "checked_count": total_checked,
                "alerts_count": total_alerts,
                "timestamp": self.last_run_at.isoformat()
            }

        except Exception as e:
            logger.error(f"❌ [WATCHLIST CRON] Lỗi tác vụ quét giá Watchlist: {e}")
            return {
                "status": "error",
                "error": str(e),
                "checked_count": total_checked,
                "alerts_count": total_alerts
            }
        finally:
            self._is_checking = False

    def get_status(self) -> Dict[str, Any]:
        """Lấy trạng thái hoạt động hiện tại của Scheduler"""
        return {
            "is_running": self.is_running,
            "interval_minutes": settings.WATCHLIST_CRON_INTERVAL_MINUTES,
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "last_checked_count": self.last_checked_count,
            "last_alerts_count": self.last_alerts_count,
            "is_checking": self._is_checking
        }


watchlist_scheduler = WatchlistPriceTrackerService()
