import httpx
import re
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from loguru import logger

from config.settings import settings


class TelegramNotificationService:
    """
    Dịch vụ gửi thông báo tức thì qua Telegram Bot (HTML formatted):
    - Cảnh báo giảm giá sâu / Sale ảo
    - Báo cáo kết quả tác vụ cào dữ liệu (Crawler Jobs)
    - Tự động lấy Chat ID từ /getUpdates khi người dùng gõ /start
    - Kiểm tra trạng thái kết nối Telegram Bot
    """

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None
        self._cached_chat_id: Optional[str] = settings.TELEGRAM_CHAT_ID

    @staticmethod
    def _clean_url(raw_url: Optional[str]) -> str:
        """Đảm bảo URL gửi lên Telegram luôn là link tuyệt đối và chuẩn domain lazada.vn"""
        if not raw_url:
            return "https://www.lazada.vn"
        u = str(raw_url).strip()
        u = re.sub(r"https?://(www\.)?la+zada\.[a-z\.]+", "https://www.lazada.vn", u)
        if u.startswith("//"):
            u = "https:" + u
        elif u.startswith("/"):
            u = f"https://www.lazada.vn{u}"
        elif not u.startswith("http"):
            u = f"https://www.lazada.vn/products/{u}"
        return u

    def _get_base_url(self) -> Optional[str]:
        token = settings.get_telegram_token()
        if not token:
            return None
        return f"https://api.telegram.org/bot{token}"

    async def get_bot_info(self) -> Dict[str, Any]:
        """Kiểm tra tính hợp lệ của Telegram Bot Token và lấy thông tin Bot"""
        base_url = self._get_base_url()
        if not base_url:
            return {
                "is_configured": False,
                "is_connected": False,
                "error": "Chưa cấu hình TELEGRAM_BOT_TOKEN trong .env",
                "bot_info": None,
                "chat_id": self._cached_chat_id
            }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(f"{base_url}/getMe")
                data = res.json()
                if data.get("ok"):
                    bot = data.get("result", {})
                    return {
                        "is_configured": True,
                        "is_connected": True,
                        "bot_info": {
                            "id": bot.get("id"),
                            "name": bot.get("first_name"),
                            "username": bot.get("username"),
                            "link": f"https://t.me/{bot.get('username')}" if bot.get("username") else None
                        },
                        "chat_id": self._cached_chat_id,
                        "notify_on_price_drop": settings.TELEGRAM_NOTIFY_ON_PRICE_DROP,
                        "price_drop_threshold": settings.PRICE_DROP_ALERT_THRESHOLD_PERCENT
                    }
                else:
                    return {
                        "is_configured": True,
                        "is_connected": False,
                        "error": data.get("description", "Lỗi kết nối Telegram API"),
                        "bot_info": None,
                        "chat_id": self._cached_chat_id
                    }
        except Exception as e:
            logger.error(f"Lỗi khi kiểm tra Telegram Bot: {e}")
            return {
                "is_configured": True,
                "is_connected": False,
                "error": str(e),
                "bot_info": None,
                "chat_id": self._cached_chat_id
            }

    async def auto_discover_chat_id(self) -> Optional[str]:
        """Tự động tìm Chat ID gần nhất từ /getUpdates (khi user gõ /start cho Bot)"""
        base_url = self._get_base_url()
        if not base_url:
            return None

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(f"{base_url}/getUpdates")
                data = res.json()
                if data.get("ok") and data.get("result"):
                    updates = data.get("result", [])
                    if updates:
                        last_update = updates[-1]
                        message = last_update.get("message") or last_update.get("channel_post") or {}
                        chat = message.get("chat", {})
                        discovered_id = str(chat.get("id"))
                        if discovered_id:
                            self._cached_chat_id = discovered_id
                            logger.info(f"🎯 [TELEGRAM] Đã tự động phát hiện Chat ID: {discovered_id}")
                            return discovered_id
        except Exception as e:
            logger.warning(f"Lỗi auto discover Telegram Chat ID: {e}")
        return self._cached_chat_id

    async def send_message(
        self,
        text: str,
        chat_id: Optional[str] = None,
        parse_mode: str = "HTML",
        disable_preview: bool = False
    ) -> Dict[str, Any]:
        """Gửi tin nhắn văn bản tùy chỉnh qua Telegram"""
        base_url = self._get_base_url()
        if not base_url:
            return {"success": False, "error": "TELEGRAM_BOT_TOKEN chưa được cấu hình"}

        target_chat_id = chat_id or self._cached_chat_id
        if not target_chat_id:
            # Thử auto-discover
            target_chat_id = await self.auto_discover_chat_id()

        if not target_chat_id:
            return {
                "success": False,
                "error": "Chưa có Chat ID. Hãy gõ /start vào Bot trên Telegram hoặc nhập Chat ID."
            }

        payload = {
            "chat_id": target_chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": disable_preview
        }

        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                res = await client.post(f"{base_url}/sendMessage", json=payload)
                data = res.json()
                if data.get("ok"):
                    logger.info(f"✅ [TELEGRAM] Đã gửi thông báo tới Chat ID: {target_chat_id}")
                    return {"success": True, "message_id": data.get("result", {}).get("message_id")}
                else:
                    err = data.get("description", "Không gửi được tin nhắn")
                    logger.warning(f"❌ [TELEGRAM] Lỗi gửi: {err}")
                    return {"success": False, "error": err}
        except Exception as e:
            logger.error(f"❌ [TELEGRAM] Exception khi gửi: {e}")
            return {"success": False, "error": str(e)}

    async def send_photo(
        self,
        photo_url: str,
        caption: str,
        chat_id: Optional[str] = None,
        parse_mode: str = "HTML"
    ) -> Dict[str, Any]:
        """Gửi ảnh kèm caption HTML qua Telegram (fallback về send_message nếu ảnh lỗi)"""
        base_url = self._get_base_url()
        if not base_url:
            return {"success": False, "error": "TELEGRAM_BOT_TOKEN chưa được cấu hình"}

        target_chat_id = chat_id or self._cached_chat_id
        if not target_chat_id:
            target_chat_id = await self.auto_discover_chat_id()

        if not target_chat_id:
            return {"success": False, "error": "Chưa có Chat ID"}

        # Đảm bảo caption không vượt quá 1024 ký tự theo quy định của Telegram sendPhoto
        safe_caption = caption[:1020] + "..." if len(caption) > 1024 else caption

        payload = {
            "chat_id": target_chat_id,
            "photo": photo_url,
            "caption": safe_caption,
            "parse_mode": parse_mode
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(f"{base_url}/sendPhoto", json=payload)
                data = res.json()
                if data.get("ok"):
                    logger.info(f"✅ [TELEGRAM] Đã gửi ảnh sản phẩm tới Chat ID: {target_chat_id}")
                    return {"success": True, "message_id": data.get("result", {}).get("message_id")}
                else:
                    logger.warning(f"⚠️ [TELEGRAM] sendPhoto thất bại: {data.get('description')}. Chuyển sang gửi tin nhắn văn bản...")
                    return await self.send_message(text=caption, chat_id=target_chat_id)
        except Exception as e:
            logger.warning(f"⚠️ [TELEGRAM] Lỗi khi gửi ảnh: {e}. Fallback về sendMessage...")
            return await self.send_message(text=caption, chat_id=target_chat_id)

    async def send_product_bulletin(
        self,
        product: Dict[str, Any],
        ai_data: Optional[Dict[str, Any]] = None,
        chat_id: Optional[str] = None
    ) -> bool:
        """
        Tự động format Bản Tin Tóm Tắt Sản Phẩm E-Commerce (kèm ảnh/giá/link/AI insights)
        gửi trực tiếp vào nhóm chat Telegram.
        """
        name = (ai_data.get("normalized_name") if ai_data else None) or product.get("name", "Sản phẩm Lazada")
        price = float(product.get("current_price") or 0.0)
        orig_price = product.get("original_price")
        discount = product.get("discount_percentage")
        sold = int(product.get("historical_sold") or 0)
        rating = float(product.get("rating_star") or 0.0)
        review_count = int(product.get("rating_count") or 0)
        shop_name = product.get("shop_name") or "Gian hàng Lazada"
        url = self._clean_url(product.get("url"))
        image_url = product.get("image_url") or ""

        # Price tag
        price_str = f"<b>{price:,.0f} ₫</b>"
        if orig_price and float(orig_price) > price:
            disc_str = f" (-{discount:.0f}%)" if discount else ""
            price_str += f" <s>{float(orig_price):,.0f} ₫</s>{disc_str}"

        # Rating line
        rating_str = f"{rating:.1f}★" if rating > 0 else "Chưa có đánh giá"
        if review_count > 0:
            rating_str += f" ({review_count:,} nhận xét)"

        # AI Summary block
        ai_section = ""
        if ai_data:
            quality = ai_data.get("quality_summary") or ""
            pros = ai_data.get("pros") or []
            cons = ai_data.get("cons") or []
            sentiment = ai_data.get("sentiment_score") or 8.0
            price_analysis = ai_data.get("competitive_price_analysis") or ""
            p_opt = ai_data.get("recommended_price_optimal") or 0.0
            verdict = ai_data.get("buying_verdict") or "Đáng cân nhắc"
            target = ai_data.get("target_audience") or "Người mua sắm trực tuyến"

            pros_bullets = "\n".join([f"  • {p}" for p in pros[:3]]) if pros else "  • Mẫu mã đa dạng"
            cons_bullets = "\n".join([f"  • {c}" for c in cons[:2]]) if cons else "  • Cần kiểm tra kỹ thời gian giao hàng"

            opt_price_text = f"<b>{p_opt:,.0f} ₫</b>" if p_opt > 0 else "Theo thị trường"

            ai_section = (
                f"\n💡 <b>TÓM TẮT CHẤT LƯỢNG (AI {sentiment}/10):</b>\n"
                f"{quality}\n\n"
                f"✅ <b>ƯU ĐIỂM NỔI BẬT:</b>\n"
                f"{pros_bullets}\n\n"
                f"⚠️ <b>NHƯỢC ĐIỂM / LƯU Ý:</b>\n"
                f"{cons_bullets}\n\n"
                f"🏷️ <b>GỢI Ý ĐỊNH GIÁ:</b> {price_analysis} (Mức tối ưu: {opt_price_text})\n"
                f"🎯 <b>Phù hợp:</b> {target}\n"
                f"🏆 <b>Đánh giá:</b> <b>{verdict}</b>\n"
            )

        caption = (
            f"🔥 <b>BẢN TIN PHÂN TÍCH SẢN PHẨM LAZADA</b> 🔥\n\n"
            f"📦 <b>Sản phẩm:</b> <b>{name}</b>\n"
            f"💰 <b>Giá bán:</b> {price_str}\n"
            f"⭐ <b>Đánh giá:</b> {rating_str} | <b>Đã bán:</b> {sold:,}\n"
            f"🏪 <b>Gian hàng:</b> {shop_name}\n"
            f"{ai_section}\n"
            f"🔗 <a href=\"{url}\">👉 Nhấn vào đây để xem trực tiếp trên Lazada</a>\n"
            f"<i>⏱️ {datetime.now().strftime('%H:%M %d/%m/%Y')} | Powered by Lazada Hunter AI</i>"
        )

        if image_url and image_url.startswith("http"):
            res = await self.send_photo(photo_url=image_url, caption=caption, chat_id=chat_id)
        else:
            res = await self.send_message(text=caption, chat_id=chat_id)

    async def send_watchlist_saved_alert(
        self,
        product: Dict[str, Any],
        user_id: str,
        chat_id: Optional[str] = None
    ) -> bool:
        """Gửi thông báo khi người dùng lưu sản phẩm vào danh sách theo dõi"""
        name = product.get("name", "Sản phẩm Lazada")
        price = float(product.get("current_price") or 0.0)
        orig_price = product.get("original_price")
        discount = product.get("discount_percentage")
        shop_name = product.get("shop_name") or "Gian hàng Lazada"
        url = self._clean_url(product.get("url"))
        image_url = product.get("image_url") or ""
        rating = float(product.get("rating_star") or 0.0)
        sold = int(product.get("historical_sold") or 0)
        ai_data = product.get("ai_analysis")

        price_str = f"<b>{price:,.0f} ₫</b>"
        if orig_price and float(orig_price) > price:
            disc_str = f" (-{discount:.0f}%)" if discount else ""
            price_str += f" <s>{float(orig_price):,.0f} ₫</s>{disc_str}"

        rating_str = f"{rating:.1f}★" if rating > 0 else "Chưa có đánh giá"

        ai_summary_line = ""
        if ai_data and isinstance(ai_data, dict):
            quality = ai_data.get("quality_summary")
            if quality:
                ai_summary_line = f"💡 <b>Tóm tắt AI:</b> <i>{quality}</i>\n"

        caption = (
            f"📌 <b>NGƯỜI DÙNG ĐÃ LƯU SẢN PHẨM VÀO THEO DÕI</b> 📌\n\n"
            f"👤 <b>Người dùng:</b> <code>{user_id}</code>\n"
            f"📦 <b>Sản phẩm:</b> <b>{name}</b>\n"
            f"💰 <b>Giá hiện tại:</b> {price_str}\n"
            f"⭐ <b>Đánh giá:</b> {rating_str} | <b>Đã bán:</b> {sold:,}\n"
            f"🏪 <b>Gian hàng:</b> {shop_name}\n"
            f"{ai_summary_line}\n"
            f"🔔 <i>Hệ thống sẽ theo dõi biến động giá và gửi cảnh báo khi giá giảm sâu!</i>\n\n"
            f"🔗 <a href=\"{url}\">👉 Mở xem sản phẩm trên Lazada</a>\n"
            f"<i>⏱️ {datetime.now().strftime('%H:%M:%S %d/%m/%Y')} | Lazada Hunter</i>"
        )

        if image_url and image_url.startswith("http"):
            res = await self.send_photo(photo_url=image_url, caption=caption, chat_id=chat_id)
        else:
            res = await self.send_message(text=caption, chat_id=chat_id)

        return res.get("success", False)

    async def send_price_drop_alert(self, alert: Dict[str, Any], chat_id: Optional[str] = None) -> bool:
        """Gửi thông báo cảnh báo giảm giá sản phẩm sâu (Chỉ gửi khi new_price < old_price)"""
        old_price = float(alert.get("old_price") or 0.0)
        new_price = float(alert.get("new_price") or 0.0)
        drop_percent = float(alert.get("drop_percent") or 0.0)

        # Đảm bảo tuyệt đối: Chỉ gửi khi giá thực sự giảm so với trước đó và giá mới hợp lệ (> 0)
        if new_price >= old_price or old_price <= 0 or new_price <= 0 or drop_percent <= 0:
            logger.debug(f"Bỏ qua thông báo Telegram vì giá không giảm: {old_price} -> {new_price}")
            return False

        product_name = alert.get("product_name", "Sản phẩm")
        url = self._clean_url(alert.get("url"))
        shop_name = alert.get("shop_name") or "Gian hàng Lazada"

        text = (
            f"🚨 <b>CẢNH BÁO GIẢM GIÁ SÂU (LAZADA)</b> 🚨\n\n"
            f"📦 <b>Sản phẩm:</b> {product_name}\n"
            f"🏪 <b>Shop:</b> {shop_name}\n\n"
            f"💰 <b>Giá cũ:</b> <s>{old_price:,.0f} ₫</s>\n"
            f"🔥 <b>Giá mới:</b> <b>{new_price:,.0f} ₫</b>\n"
            f"📉 <b>Mức giảm:</b> <tg-spoiler><b>-{drop_percent:.1f}%</b></tg-spoiler>\n\n"
            f"🔗 <a href=\"{url}\">👉 Nhấn vào đây để xem deal trên Lazada</a>\n"
            f"<i>⏱️ Thời gian phát hiện: {datetime.now().strftime('%H:%M:%S %d/%m/%Y')}</i>"
        )

        res = await self.send_message(text=text, chat_id=chat_id)
        return res.get("success", False)

    async def send_crawl_job_report(
        self,
        job_id: int,
        keyword: str,
        platform: str,
        total_found: int,
        total_saved: int,
        price_alerts_count: int = 0,
        chat_id: Optional[str] = None
    ) -> bool:
        """Gửi báo cáo tổng kết sau khi hoàn thành tác vụ cào dữ liệu"""
        text = (
            f"🕷️ <b>BÁO CÁO CÀO DỮ LIỆU HOÀN TẤT</b> (Job #{job_id})\n\n"
            f"🔍 <b>Đầu vào:</b> <code>{keyword}</code>\n"
            f"🌐 <b>Sàn TMĐT:</b> {platform.upper()}\n"
            f"📦 <b>Tìm thấy:</b> {total_found} sản phẩm\n"
            f"💾 <b>Lưu/Cập nhật DB:</b> {total_saved} sản phẩm\n"
            f"🚨 <b>Phát hiện giảm giá:</b> {price_alerts_count} deal\n\n"
            f"<i>⏱️ Hoàn tất lúc: {datetime.now().strftime('%H:%M:%S %d/%m/%Y')}</i>"
        )
        res = await self.send_message(text=text, chat_id=chat_id)
        return res.get("success", False)

    async def send_test_notification(self, chat_id: Optional[str] = None) -> Dict[str, Any]:
        """Gửi tin nhắn kiểm tra kết nối bot"""
        text = (
            f"🎉 <b>E-COMMERCE INTELLIGENT CRAWLER</b>\n\n"
            f"✅ <b>Kết nối Telegram Bot thành công!</b>\n"
            f"Hệ thống đã sẵn sàng tự động phát cảnh báo giảm giá, săn deal Flash Sale, phân tích AI và báo cáo tiến trình cào dữ liệu Lazada trực tiếp tới bạn.\n\n"
            f"<i>🤖 Bot: @lazamerce_alert_bot | {datetime.now().strftime('%H:%M:%S %d/%m/%Y')}</i>"
        )
        return await self.send_message(text=text, chat_id=chat_id)

    def set_chat_id(self, new_chat_id: str):
        """Cập nhật Chat ID đang hoạt động"""
        self._cached_chat_id = new_chat_id.strip()


telegram_service = TelegramNotificationService()
