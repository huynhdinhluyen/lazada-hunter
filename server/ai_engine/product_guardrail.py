"""
Product Integrity & Anti-Hallucination Guardrail System
Đảm bảo tính xác thực 100% cho dữ liệu sản phẩm, giá bán, lượt bán và đường link:
1. Input Grounding: Khóa chặt phạm vi dữ liệu được phép phân tích.
2. Deterministic Rendering: Tạo bảng đối chiếu sản phẩm chuẩn xác trực tiếp từ thực thể Product ORM.
3. Output Verification & Sanitization: Quét sạch mọi link bịa đặt, bảng giá giả mạo khi chưa có dữ liệu cào thực tế.
"""

import re
import urllib.parse
from typing import List, Any, Optional
from loguru import logger

from core.models import Product


class ProductIntegrityGuardrail:
    """
    Hệ thống Guardrail bảo vệ toàn vẹn dữ liệu E-Commerce:
    Ngăn chặn LLM bịa đặt (hallucinate) sản phẩm, giá cả, lượt mua và đường link 404.
    """

    @staticmethod
    def build_grounded_product_table(products: List[Product]) -> str:
        """
        Tạo bảng Markdown sản phẩm chuẩn xác 100% từ đối tượng Product thật đã cào.
        Tránh hoàn toàn việc LLM tự bịa giá hoặc gán sai số lượt bán.
        """
        if not products:
            return ""

        table = (
            "| # | Tên sản phẩm | Giá bán thực tế | Đã bán & Đánh giá | Gian hàng |\n"
            "| :-: | :--- | :--- | :--- | :--- |\n"
        )
        for idx, p in enumerate(products[:6], 1):
            price_str = f"**{p.current_price:,.0f} đ**"
            if p.original_price and p.original_price > p.current_price:
                disc = f" (-{p.discount_percentage:.0f}%)" if p.discount_percentage else ""
                price_str += f"<br>~~{p.original_price:,.0f} đ~~{disc}"

            sold_str = f"{p.historical_sold:,} đã bán" if p.historical_sold else "Mới lên sàn"
            rating_str = f"⭐ {p.rating_star:.1f}" if p.rating_star else "Chưa có đánh giá"
            shop_str = p.shop_name or ("Lazada Mall" if p.is_official_shop else "Gian hàng Lazada")
            
            p_url = p.url or f"https://www.lazada.vn/catalog/?q={urllib.parse.quote(p.name)}"
            table += f"| {idx} | **[{p.name}]({p_url})** | {price_str} | {sold_str}<br>{rating_str} | {shop_str} |\n"

        return table

    @staticmethod
    def sanitize_links(text: str, products: List[Any]) -> str:
        """
        Bảo vệ đường link chống Hallucination:
        - Giữ nguyên các link trùng khớp với sản phẩm thật đã cào.
        - Ánh xạ các link tự chế về đúng link thật (p.url) của sản phẩm tương ứng.
        - Chuyển các link không xác định thành link tìm kiếm chính xác trên Lazada (không để 404).
        """
        if not text:
            return text

        valid_urls = set()
        for p in (products or []):
            u = getattr(p, "url", None) or (p.get("url") if isinstance(p, dict) else None)
            if u:
                valid_urls.add(u.strip())

        def replace_link(match):
            label = match.group(1).strip()
            url = match.group(2).strip()

            # 1. Trùng khớp chính xác với link thật đã cào -> Giữ nguyên
            if url in valid_urls:
                return match.group(0)

            # 2. Tìm sản phẩm thật khớp nhất theo tên / nhãn
            label_clean = label.lower()
            best_product_url = None
            best_score = 0.0

            for p in (products or []):
                p_url = getattr(p, "url", None) or (p.get("url") if isinstance(p, dict) else None)
                p_name = getattr(p, "name", None) or (p.get("name") if isinstance(p, dict) else "")
                if not p_url or not p_name:
                    continue

                p_name_lower = p_name.lower()
                words = [w for w in label_clean.split() if len(w) > 2]
                if words:
                    matched_cnt = sum(1 for w in words if w in p_name_lower)
                    score = matched_cnt / len(words)
                    if score > best_score and score >= 0.4:
                        best_score = score
                        best_product_url = p_url

            if best_product_url:
                return f"[{label}]({best_product_url})"

            # 3. Fallback an toàn: Dẫn tới trang tìm kiếm chính xác của Lazada
            safe_query = urllib.parse.quote(label)
            return f"[{label}](https://www.lazada.vn/catalog/?q={safe_query})"

        return re.sub(r'\[([^\]]+)\]\((https?://[^\)]+)\)', replace_link, text)

    @classmethod
    def guard_recommendation_output(
        cls,
        llm_response: str,
        products: List[Product],
        user_query: str,
        search_kw: str
    ) -> str:
        """
        Guardrail kiểm duyệt đầu ra của AI trước khi gửi về Client:
        - Trường hợp 1: Có sản phẩm cào thật -> Làm sạch link và gắn bảng giá định danh chuẩn xác nếu cần.
        - Trường hợp 2: KHÔNG có sản phẩm cào thật -> Chặn đứng việc LLM bịa danh sách hàng giả lập trên Lazada.
        """
        if not llm_response:
            return ""

        # =====================================================================
        # TRƯỜNG HỢP 1: CÓ SẢN PHẨM THẬT TRONG CONTEXT
        # =====================================================================
        if products and len(products) > 0:
            cleaned = cls.sanitize_links(llm_response, products)
            return cleaned

        # =====================================================================
        # TRƯỜNG HỢP 2: KHÔNG CÓ SẢN PHẨM CÀO THẬT (Chống bịa sản phẩm & bịa giá)
        # =====================================================================
        logger.warning(f"🛡️ [GUARDRAIL TRIGGERED] Không có sản phẩm cào thực tế cho '{search_kw}'. Áp dụng bộ lọc Anti-Hallucination.")
        
        # Nếu LLM cố tình vẽ bảng markdown chứa danh sách sản phẩm bịa đặt "trên Lazada":
        # Phát hiện pattern bảng sản phẩm giả
        has_fake_product_table = bool(re.search(r"\|\s*Tên sản phẩm\s*\|\s*Giá\s*", llm_response, re.IGNORECASE))
        has_fake_listings = bool(re.search(r"\b(1\.|2\.|Top 1|Top 2)\s*\[.*\]\(http", llm_response))

        if has_fake_product_table or has_fake_listings:
            logger.info("🛡️ [GUARDRAIL INTERCEPT] Phát hiện bảng/danh sách sản phẩm bịa đặt từ LLM. Tự động chuyển đổi thành Hướng dẫn Mua sắm chuẩn.")
            safe_query = urllib.parse.quote(search_kw)
            return (
                f"### 💡 TƯ VẤN & TIÊU CHÍ CHỌN MUA: **{search_kw.upper()}**\n\n"
                f"Hiện tại hệ thống chưa đồng bộ sẵn danh sách các model **{search_kw}** trực tiếp trong kho dữ liệu. "
                f"Dưới đây là các tiêu chuẩn cốt lõi bạn nên lưu ý để chọn được sản phẩm ưng ý:\n\n"
                f"1. ⚙️ **Thông số & Chuẩn công nghệ:**\n"
                f"   - Ưu tiên các model đời mới, có hỗ trợ các chuẩn kết nối/tính năng hiện đại.\n"
                f"   - Chọn phiên bản phù hợp với không gian và nhu cầu sử dụng thực tế.\n\n"
                f"2. 🏷️ **Phân khúc giá tham khảo:**\n"
                f"   - **Phổ thông (Dưới 500k - 1tr):** Đáp ứng tốt các nhu cầu cơ bản hàng ngày.\n"
                f"   - **Tầm trung & Cao cấp (Trên 1.5tr - 3tr+):** Hiệu năng cao, độ bền vượt trội và nhiều tính năng nâng cao.\n\n"
                f"3. 🏪 **Kinh nghiệm mua hàng an toàn trên Lazada:**\n"
                f"   - Chọn mua tại các gian hàng **LazMall / Official Store** để đảm bảo chính hãng và bảo hành chính thức.\n"
                f"   - Kiểm tra kỹ số lượng đánh giá thực tế và lượt bán của shop.\n\n"
                f"👉 [Bấm vào đây để xem trực tiếp các mẫu **{search_kw}** bán chạy nhất trên Lazada](https://www.lazada.vn/catalog/?q={safe_query})\n\n"
                f"*(Bạn cũng có thể dán đường link sản phẩm Lazada cụ thể vào đây để mình bóc tách và phân tích giá chi tiết nhé!)*"
            )

        # Nếu LLM trả về bài tư vấn chung hợp lý, chỉ cần làm sạch link
        return cls.sanitize_links(llm_response, [])


product_guardrail = ProductIntegrityGuardrail()
