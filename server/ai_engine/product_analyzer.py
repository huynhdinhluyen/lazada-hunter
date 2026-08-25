import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from loguru import logger

from core.schemas import ProductAIAnalysisResult
from ai_engine.model_router import model_router, TaskComplexity


PRODUCT_ANALYSIS_SYSTEM_PROMPT = """
Bạn là Chuyên gia Cao Cấp về Phân Tích Dữ Liệu E-Commerce và Trí Tuệ Thị Trường (E-Commerce Intelligence & Market Analyst) chuyên sâu về sàn TMĐT Lazada Việt Nam.

Nhiệm vụ của bạn:
1. TIẾP NHẬN dữ liệu sản phẩm thực tế vừa cào được (Tên gốc, Giá bán, Giá gốc, Đánh giá sao, Lượt bán, Thông số kỹ thuật, Đánh giá/Reviews của khách hàng).
2. CHUẨN HÓA & DỊCH THUẬT:
   - Làm sạch tên sản phẩm, loại bỏ các từ khóa rác/SEO spam như "[Chính hãng]", "Freeship Max", "Sale sốc", "Xả kho"... Dịch thuật sang tiếng Việt chuẩn mực nếu là tiếng Anh/tiếng Trung.
   - Chuẩn hóa ngành hàng/danh mục cụ thể.
3. PHÂN TÍCH ƯU / NHƯỢC ĐIỂM TỪ ĐÁNH GIÁ (REVIEWS):
   - Bóc tách khách quan những điểm khách hàng khen nhiều nhất (Ưu điểm).
   - Chỉ ra thẳng thắn các nhược điểm, lỗi vặt, hoặc điểm cần lưu ý từ phản hồi của người mua thực tế.
4. ĐÁNH GIÁ CHẤT LƯỢNG & ĐIỂM CẢM XÚC:
   - Tóm tắt cô đọng chất lượng sản phẩm (độ bền, tính năng, hoàn thiện).
   - Cho điểm cảm xúc / mức độ hài lòng khách hàng (thang điểm 1.0 đến 10.0).
5. GỢI Ý ĐỊNH GIÁ CẠNH TRANH:
   - Dựa trên giá bán hiện tại và phân khúc thị trường, gợi ý khoảng giá bán cạnh tranh nhất (min, max, optimal) để tối ưu doanh số hoặc giúp người mua biết giá này có hời hay không.
6. KẾT LUẬN & ĐỐI TƯỢNG:
   - Xác định rõ phân khúc khách hàng phù hợp nhất.
   - Đưa ra lời khuyên mua sắm / nhập hàng dứt khoát.

QUY TẮC BẮT BUỘC:
- BẮT BUỘC trả về ĐÚNG định dạng JSON Schema sau, không kèm bất kỳ văn bản giải thích nào ngoài khối JSON.
"""

PRODUCT_ANALYSIS_USER_PROMPT_TEMPLATE = """
Dưới đây là thông tin sản phẩm thu thập từ sàn TMĐT Lazada:
- Tên sản phẩm: {name}
- Giá hiện tại: {current_price:,.0f} VNĐ
- Giá niêm yết/Giá gốc: {original_price}
- Giảm giá: {discount_percentage}%
- Điểm đánh giá: {rating_star} / 5 sao ({rating_count} lượt đánh giá)
- Lượt bán thực tế: {historical_sold} sản phẩm
- Thương hiệu: {brand}
- Gian hàng: {shop_name} ({shop_type})
- Vị trí shop: {shop_location}
- Thông số kỹ thuật / Mô tả:
{specs_text}
- Trích đoạn đánh giá của người mua thực tế:
{reviews_text}

Hãy phân tích toàn diện và trả về JSON theo đúng cấu trúc sau:
{{
    "normalized_name": "Tên sản phẩm sạch gọn, chuẩn tiếng Việt (vd: Chuột Không Dây Logitech G304 Lightspeed)",
    "category_standardized": "Danh mục chuẩn hóa (vd: Thiết bị ngoại vi / Chuột máy tính)",
    "specs_summary": [
        "Cảm biến Hero 12.000 DPI độ chính xác cao",
        "Kết nối không dây Lightspeed độ trễ siêu thấp 1ms",
        "Thời lượng pin lên tới 250 giờ với 1 viên pin AA",
        "Trọng lượng siêu nhẹ chỉ 99g"
    ],
    "quality_summary": "Tóm tắt 2-3 câu ngắn gọn về chất lượng hoàn thiện, hiệu năng thực tế và độ bền.",
    "pros": [
        "Ưu điểm 1 bóc tách từ reviews khách hàng",
        "Ưu điểm 2 bóc tách từ thông số",
        "Ưu điểm 3..."
    ],
    "cons": [
        "Nhược điểm 1 hoặc điểm người dùng phàn nàn",
        "Nhược điểm 2..."
    ],
    "sentiment_score": 8.5,
    "competitive_price_analysis": "Phân tích 2-3 câu về mức giá hiện tại so với thị trường và tính cạnh tranh.",
    "recommended_price_min": {price_min},
    "recommended_price_max": {price_max},
    "recommended_price_optimal": {price_optimal},
    "target_audience": "Game thủ bán chuyên, học sinh - sinh viên hoặc nhân viên văn phòng cần chuột bền bỉ.",
    "buying_verdict": "Đáng mua trong tầm giá / Cân nhắc chờ đợt sale tiếp theo / Rất hời."
}}
"""


class ProductAnalyzer:
    """
    AI Product Intelligence & Normalization Module:
    - Bóc tách, dịch thuật, chuẩn hóa dữ liệu sản phẩm
    - Phân tích ưu/nhược điểm từ đánh giá của khách hàng (Reviews)
    - Tóm tắt chất lượng và gợi ý mức giá cạnh tranh chuẩn JSON
    - Điều phối xoay model qua DynamicModelRouter (NVIDIA NIM -> Gemini -> Heuristic Fallback)
    """

    async def analyze_product(self, product_dict: Any) -> ProductAIAnalysisResult:
        """Thực hiện phân tích AI cho 1 sản phẩm"""
        if hasattr(product_dict, "model_dump"):
            product_dict = product_dict.model_dump()
        elif hasattr(product_dict, "__dict__") and not isinstance(product_dict, dict):
            from core.serializers import serialize_product
            product_dict = serialize_product(product_dict)

        name = product_dict.get("name", "Sản phẩm")
        current_price = float(product_dict.get("current_price") or 0.0)
        orig_price = product_dict.get("original_price")
        orig_price_str = f"{float(orig_price):,.0f} VNĐ" if orig_price else "Chưa có dữ liệu"
        discount = product_dict.get("discount_percentage") or 0.0
        rating_star = float(product_dict.get("rating_star") or 0.0)
        rating_count = int(product_dict.get("rating_count") or 0)
        sold = int(product_dict.get("historical_sold") or 0)
        brand = product_dict.get("brand") or "Không rõ thương hiệu"
        shop_name = product_dict.get("shop_name") or "Gian hàng Lazada"
        is_official = product_dict.get("is_official_shop", False)
        shop_type = "Shop Chính Hãng LazMall" if is_official else "Shop Uy Tín"
        shop_loc = product_dict.get("shop_location") or "Việt Nam"

        # Bóc tách thông số kỹ thuật từ raw_data nếu có
        raw_data = product_dict.get("raw_data") or {}
        specs_list = []
        if isinstance(raw_data, dict):
            if "description" in raw_data:
                specs_list.append(str(raw_data["description"])[:300])
            if "highlights" in raw_data and isinstance(raw_data["highlights"], list):
                specs_list.extend([str(h) for h in raw_data["highlights"][:4]])
        specs_text = "\n".join([f"- {s}" for s in specs_list]) if specs_list else "- Đang cập nhật từ gian hàng."

        # Bóc tách đánh giá thực tế
        reviews_list = raw_data.get("reviews") or []
        if isinstance(reviews_list, list) and reviews_list:
            reviews_text = "\n".join([f"- \"{r}\"" for r in reviews_list[:5]])
        else:
            reviews_text = f"- Đánh giá chung: {rating_star}/5 sao dựa trên {rating_count} lượt nhận xét từ người mua trên sàn."

        # Tính toán mức giá tham chiếu sơ bộ
        base_p = current_price if current_price > 0 else 100000.0
        p_min = round(base_p * 0.9, -3)
        p_max = round(base_p * 1.1, -3)
        p_opt = round(base_p * 0.95, -3)

        user_prompt = PRODUCT_ANALYSIS_USER_PROMPT_TEMPLATE.format(
            name=name,
            current_price=current_price,
            original_price=orig_price_str,
            discount_percentage=discount,
            rating_star=rating_star,
            rating_count=rating_count,
            historical_sold=sold,
            brand=brand,
            shop_name=shop_name,
            shop_type=shop_type,
            shop_location=shop_loc,
            specs_text=specs_text,
            reviews_text=reviews_text,
            price_min=p_min,
            price_max=p_max,
            price_optimal=p_opt,
        )

        try:
            logger.info(f"🧠 [AI ANALYZER] Bắt đầu phân tích sản phẩm: '{name[:40]}...'")
            json_data, model_used = await model_router.generate_json(
                prompt=user_prompt,
                system_prompt=PRODUCT_ANALYSIS_SYSTEM_PROMPT,
                complexity=TaskComplexity.HIGH,
                temperature=0.15,
            )

            result = ProductAIAnalysisResult(
                normalized_name=json_data.get("normalized_name") or name,
                category_standardized=json_data.get("category_standardized") or "Đồ dùng & Công nghệ",
                specs_summary=json_data.get("specs_summary") or ["Thông số đang được cập nhật"],
                quality_summary=json_data.get("quality_summary") or f"Sản phẩm đạt mức đánh giá {rating_star} sao với {sold} lượt bán.",
                pros=json_data.get("pros") or ["Giá cả cạnh tranh trên sàn", "Mẫu mã phổ biến"],
                cons=json_data.get("cons") or ["Nên tham khảo thêm đánh giá thực tế trước khi đặt"],
                sentiment_score=float(json_data.get("sentiment_score") or (rating_star * 2.0 if rating_star > 0 else 7.5)),
                competitive_price_analysis=json_data.get("competitive_price_analysis") or "Mức giá hiện tại nằm trong khoảng giá chuẩn của thị trường.",
                recommended_price_min=float(json_data.get("recommended_price_min") or p_min),
                recommended_price_max=float(json_data.get("recommended_price_max") or p_max),
                recommended_price_optimal=float(json_data.get("recommended_price_optimal") or p_opt),
                target_audience=json_data.get("target_audience") or "Người tiêu dùng mua sắm trực tuyến",
                buying_verdict=json_data.get("buying_verdict") or "Đáng cân nhắc theo nhu cầu",
                model_used=model_used,
                analyzed_at=datetime.now(timezone.utc).isoformat(),
            )
            logger.info(f"✅ [AI ANALYZER] Hoàn tất phân tích qua {model_used} (Score: {result.sentiment_score}/10)")
            return result

        except Exception as e:
            logger.warning(f"⚠️ [AI ANALYZER] Lỗi khi gọi LLM: {e}. Kích hoạt Fallback Heuristic Generator...")
            return self._generate_heuristic_fallback(product_dict, name, current_price, rating_star, sold, p_min, p_max, p_opt)

    def _generate_heuristic_fallback(
        self,
        product_dict: Dict[str, Any],
        name: str,
        price: float,
        rating: float,
        sold: int,
        p_min: float,
        p_max: float,
        p_opt: float
    ) -> ProductAIAnalysisResult:
        """Tạo kết quả phân tích chuẩn tắc bằng thuật toán Heuristic khi LLM không khả dụng (Resilience)"""
        # Làm sạch tên đơn giản
        clean_name = name
        for tag in ["[Chính Hãng]", "[Freeship]", "[Mã Giảm]", "[Flash Sale]", "[Chính hãng 100%]"]:
            clean_name = clean_name.replace(tag, "").strip()

        score = round(min(10.0, max(5.0, (rating * 2.0) if rating > 0 else 7.8)), 1)
        
        return ProductAIAnalysisResult(
            normalized_name=clean_name,
            category_standardized="Sản phẩm TMĐT Lazada",
            specs_summary=[
                f"Giá niêm yết hiện tại: {price:,.0f} VNĐ",
                f"Lượng tiêu thụ thực tế: {sold:,} sản phẩm đã bán",
                f"Điểm uy tín gian hàng: {rating} / 5.0 sao"
            ],
            quality_summary=f"Sản phẩm có độ uy tín ổn định trên sàn Lazada với {sold:,} đơn hàng đã giao và điểm đánh giá {rating} sao.",
            pros=[
                f"Lượt bán cao ({sold:,} sản phẩm), chứng minh nhu cầu thị trường lớn",
                "Mức giá trực tuyến dễ tiếp cận so với mua trực tiếp",
                "Có hỗ trợ các mã giảm giá và giao hàng tận nơi"
            ],
            cons=[
                "Cần kiểm tra kỹ chính sách đổi trả và bảo hành từ gian hàng",
                "Thời gian giao hàng có thể phụ thuộc vào đơn vị vận chuyển"
            ],
            sentiment_score=score,
            competitive_price_analysis=f"Mức giá {price:,.0f} đ được đánh giá là hợp lý. Mức giá khuyến nghị cạnh tranh dao động từ {p_min:,.0f} đ đến {p_max:,.0f} đ.",
            recommended_price_min=p_min,
            recommended_price_max=p_max,
            recommended_price_optimal=p_opt,
            target_audience="Khách hàng mua sắm trực tuyến tìm kiếm mức giá tối ưu",
            buying_verdict="Đáng mua nếu giá nằm trong mức khuyến nghị",
            model_used="Heuristic AI Rule Engine (Fallback)",
            analyzed_at=datetime.now(timezone.utc).isoformat(),
        )


product_analyzer = ProductAnalyzer()
