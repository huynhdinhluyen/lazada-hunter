import json
import uuid
import re
import urllib.parse
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, or_
from sqlalchemy.sql import func
from loguru import logger

from config.settings import settings
from core.models import Product, ChatSession, ChatMessage
from core.schemas import ChatIntentEnum, ChatRequest, ChatResponse, ProductResponse, IntentClassificationResult
from ai_engine.intent_classifier import intent_classifier
from ai_engine.query_cache import query_cache_manager
from ai_engine.prompts import (
    SYSTEM_ROLE_PROMPT,
    CLARIFICATION_PROMPT_TEMPLATE,
    UNREALISTIC_PROMPT_TEMPLATE,
    CHITCHAT_REDIRECT_PROMPT,
    COMPARISON_SYNTHESIS_PROMPT,
    RECOMMENDATION_SYNTHESIS_PROMPT
)
from ai_engine.model_router import model_router, TaskComplexity
from services.crawler_service import crawler_service
from services.data_pipeline import pipeline_service
from services.embedding_service import embedding_service
from services.qdrant_store import qdrant_store
from ai_engine.product_guardrail import product_guardrail

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None

try:
    from openai import AsyncOpenAI
except ImportError:
    AsyncOpenAI = None


def serialize_product(p: Product) -> ProductResponse:
    """Helper chuyển đổi an toàn từ SQLAlchemy Product ORM sang Pydantic ProductResponse"""
    return ProductResponse(
        id=p.id,
        platform=p.platform,
        platform_product_id=p.platform_product_id,
        sku=p.sku,
        name=p.name,
        url=p.url,
        image_url=p.image_url,
        brand=p.brand,
        category=p.category,
        current_price=p.current_price,
        original_price=p.original_price,
        discount_percentage=p.discount_percentage,
        rating_star=p.rating_star,
        rating_count=p.rating_count,
        historical_sold=p.historical_sold,
        stock=p.stock,
        shop_id=p.shop_id,
        shop_name=p.shop_name,
        shop_location=p.shop_location,
        is_official_shop=p.is_official_shop or False,
        created_at=p.created_at or func.now(),
        updated_at=p.updated_at or func.now(),
        variants=[]
    )


class ShoppingAssistant:
    """
    Core Orchestrator điều phối toàn bộ luồng Chat Trợ Lý Mua Sắm:
    - Quản lý phiên hội thoại đa lượt (Multi-turn Context)
    - Router 3 tầng: Fast-Path Guardrails -> Semantic Cache -> LLM Structured Outputs
    - Tự động gọi Crawler thu thập giá live trên Shopee/Lazada
    - Tổng hợp câu trả lời Markdown sắc bén bằng NVIDIA NIM (Llama 3.1 8B / 3.3 70B) hoặc Gemini
    """
    def __init__(self):
        self.gemini_key = settings.get_gemini_api_key()
        self.gemini_client = None
        if self.gemini_key and genai:
            try:
                self.gemini_client = genai.Client(api_key=self.gemini_key)
            except Exception as e:
                logger.warning(f"Không thể khởi tạo Gemini Client trong ShoppingAssistant: {e}")

        self.nvidia_key = settings.get_nvidia_api_key()
        self.nvidia_client = None
        if self.nvidia_key and AsyncOpenAI:
            try:
                self.nvidia_client = AsyncOpenAI(
                    base_url=settings.NVIDIA_BASE_URL,
                    api_key=self.nvidia_key
                )
            except Exception as e:
                logger.warning(f"Không thể khởi tạo NVIDIA Client trong ShoppingAssistant: {e}")

    async def _generate_text(self, prompt: str, model: Optional[str] = None, temperature: float = 0.2) -> Optional[str]:
        """Gọi Dynamic Model Router (NVIDIA NIM -> Gemini Failover) để sinh câu trả lời Markdown"""
        if model and (model.startswith("fallback") or "heuristic" in model):
            return None

        try:
            content, model_used = await model_router.generate_text(
                prompt=prompt,
                system_prompt="You are a professional, helpful E-Commerce Shopping Assistant in Vietnam.",
                complexity=TaskComplexity.LOW,
                temperature=temperature,
                max_tokens=1000,
            )
            return content
        except Exception as e:
            logger.warning(f"Lỗi khi gọi AI Model Router trong ShoppingAssistant: {e}")
            return None

    async def chat(self, session: AsyncSession, request: ChatRequest) -> ChatResponse:
        """Xử lý một tin nhắn từ người dùng và trả về phản hồi chuẩn hóa"""
        raw_msg = request.message.strip()
        session_id = request.session_id or str(uuid.uuid4())
        selected_model = request.model or settings.DEFAULT_AI_MODEL

        # 1. Khởi tạo hoặc lấy ChatSession từ DB
        chat_sess = await self._get_or_create_session(session, session_id, request.user_id)

        # 2. Lấy lịch sử hội thoại gần nhất
        history = await self._get_session_history(session, session_id)

        # =====================================================================
        # TẦNG 1: FAST-PATH GUARDRAILS (Sub-millisecond, 0 Token LLM)
        # =====================================================================
        fast_guardrail = intent_classifier.guardrails.evaluate(raw_msg)
        if fast_guardrail:
            logger.debug(f"⚡ [FAST-PATH GUARDRAIL TRIGGERED] Intent: {fast_guardrail.intent.value.upper()}")
            intent = fast_guardrail.intent
            response_text = ""
            if intent == ChatIntentEnum.SAFETY_GUARD:
                response_text = "🛡️ Yêu cầu của bạn không phù hợp với tiêu chuẩn an toàn hoặc nằm ngoài chức năng Trợ lý Mua sắm E-Commerce. Hãy cho tôi biết món đồ bạn đang muốn tìm nhé!"
            elif intent == ChatIntentEnum.CHITCHAT_OUT_OF_SCOPE:
                response_text = await self._handle_chitchat(raw_msg, model=selected_model)

            await self._save_message(session, session_id, "user", raw_msg, intent.value)
            await self._save_message(session, session_id, "assistant", response_text, intent.value)

            return ChatResponse(
                session_id=session_id,
                intent=intent.value,
                message=response_text,
                cached=False,
                recommended_products=[]
            )

        # =====================================================================
        # TẦNG 1.5: DIRECT LAZADA PRODUCT LINK PASTE (Auto-Crawl & Deep AI Analysis)
        # =====================================================================
        url_match = re.search(r"https?://[^\s]*(?:lazada\.vn|la+zada)[^\s]*", raw_msg, re.IGNORECASE)
        if url_match or (raw_msg.startswith("http") and ("/products/" in raw_msg or "pdp-" in raw_msg)):
            extracted_url = url_match.group(0) if url_match else raw_msg.strip()
            logger.info(f"🔗 [CHAT URL DETECTED] Người dùng dán link trực tiếp: {extracted_url}")
            await self._save_message(session, session_id, "user", raw_msg, "url_analysis")
            response_text, products = await self._handle_product_url_analysis(
                session, extracted_url, raw_msg, model=selected_model
            )
            await self._save_message(
                session, session_id, "assistant", response_text, "url_analysis",
                metadata={"recommended_count": len(products)}
            )
            prod_responses = [serialize_product(p) for p in products]
            return ChatResponse(
                session_id=session_id,
                intent="url_analysis",
                message=response_text,
                cached=False,
                recommended_products=prod_responses
            )

        # =====================================================================
        # TẦNG 2: SEMANTIC CACHE (Cross-User Deduplication & Fast Retrieval)
        # =====================================================================
        if not request.force_refresh:
            cached_result = await query_cache_manager.get_cached_response(session, raw_msg)
            if cached_result:
                cache_entry, prods = cached_result
                cached_intent = cache_entry.get("intent", "recommendation")
                cached_msg = cache_entry.get("response_markdown", "")

                # Lưu tin nhắn vào session hiện tại
                await self._save_message(session, session_id, "user", raw_msg, cached_intent)
                await self._save_message(session, session_id, "assistant", cached_msg, cached_intent)

                prod_responses = [serialize_product(p) for p in prods]
                return ChatResponse(
                    session_id=session_id,
                    intent=cached_intent,
                    message=cached_msg,
                    cached=True,
                    recommended_products=prod_responses
                )

        # =====================================================================
        # TẦNG 3: LLM STRUCTURED OUTPUTS (Primary LLM & Fallback Engine)
        # =====================================================================
        classification = await intent_classifier.classify(raw_msg, history, model=selected_model)
        intent = classification.intent
        logger.info(f"🎯 [INTENT CLASSIFIED] '{raw_msg[:35]}...' -> {intent.value.upper()} (Model: {selected_model}, Confidence: {classification.confidence})")

        # Lưu tin nhắn user
        await self._save_message(session, session_id, "user", raw_msg, intent.value)

        # Xử lý điều hướng theo từng Intent
        response_text = ""
        recommended_products: List[Product] = []
        comparison_data: Optional[Dict[str, Any]] = None

        if intent == ChatIntentEnum.CLARIFICATION_NEEDED:
            response_text = await self._handle_clarification(raw_msg, classification, model=selected_model)

        elif intent == ChatIntentEnum.UNREALISTIC_CONSTRAINTS:
            response_text = await self._handle_unrealistic(raw_msg, classification, model=selected_model)

        elif intent == ChatIntentEnum.COMPARISON:
            response_text, comparison_data = await self._handle_comparison(session, classification, model=selected_model)

        elif intent == ChatIntentEnum.RECOMMENDATION:
            response_text, recommended_products = await self._handle_recommendation(session, raw_msg, classification, model=selected_model)

        # 6. Lưu tin nhắn Assistant vào DB
        await self._save_message(
            session, session_id, "assistant", response_text, intent.value,
            metadata={"recommended_count": len(recommended_products)}
        )

        # 7. Lưu vào QueryCache nếu là câu hỏi mới có giá trị
        if intent in [ChatIntentEnum.RECOMMENDATION, ChatIntentEnum.COMPARISON]:
            prod_ids = [p.id for p in recommended_products]
            await query_cache_manager.save_cache(
                session=session,
                raw_query=raw_msg,
                intent=intent.value,
                response_markdown=response_text,
                product_ids=prod_ids
            )

        prod_responses = [serialize_product(p) for p in recommended_products]
        return ChatResponse(
            session_id=session_id,
            intent=intent.value,
            message=response_text,
            cached=False,
            recommended_products=prod_responses,
            comparison_data=comparison_data
        )

    # =========================================================================
    # INTENT HANDLERS
    # =========================================================================

    async def _handle_product_url_analysis(
        self,
        session: AsyncSession,
        product_url: str,
        user_query: str,
        model: str = "meta/llama-3.1-8b-instruct"
    ) -> Tuple[str, List[Product]]:
        """Cào dữ liệu trực tiếp từ Link Lazada và thực hiện AI Phân tích chuyên sâu trả về trong khung Chat"""
        clean_url = str(product_url).strip()
        clean_url = re.sub(r"https?://(www\.)?la+zada\.[a-z\.]+", "https://www.lazada.vn", clean_url)
        if not clean_url.startswith("http"):
            clean_url = f"https://www.lazada.vn/products/{clean_url}" if not clean_url.startswith("www.") else f"https://{clean_url}"

        # 1. Kiểm tra xem sản phẩm đã có trong DB chưa
        prod_id_match = re.search(r"-i(\d+)", clean_url)
        platform_prod_id = prod_id_match.group(1) if prod_id_match else None

        product: Optional[Product] = None
        if platform_prod_id:
            stmt = select(Product).where(Product.platform_product_id == platform_prod_id)
            res = await session.execute(stmt)
            product = res.scalar_one_or_none()

        # 2. Nếu chưa có, tiến hành cào trực tiếp từ Lazada
        if not product:
            logger.info(f"🕷️ [CHAT CRAWLER] Sản phẩm chưa có trong DB. Bắt đầu cào trực tiếp từ Lazada: {clean_url}")
            try:
                scraped_items = await crawler_service.scrape_products(
                    keyword_or_url=clean_url, platform="lazada", input_mode="single_url"
                )
                if scraped_items:
                    pipeline_res = await pipeline_service.process_scraped_products(session, scraped_items)
                    if pipeline_res.products:
                        prod_id = pipeline_res.products[0].id
                        stmt = select(Product).where(Product.id == prod_id)
                        res = await session.execute(stmt)
                        product = res.scalar_one_or_none()
            except Exception as crawl_err:
                logger.error(f"❌ [CHAT CRAWLER] Lỗi cào sản phẩm: {crawl_err}")

        if not product:
            return (
                f"⚠️ **Không thể truy xuất dữ liệu từ đường link được cung cấp:**\n\n"
                f"🔗 `{clean_url}`\n\n"
                f"Có thể sản phẩm đã hết hàng, bị ẩn hoặc Lazada đang yêu cầu xác minh. "
                f"Bạn hãy kiểm tra lại đường link hoặc gửi tên sản phẩm để mình tìm kiếm và tư vấn nhé!",
                []
            )

        # 3. Chạy AI Phân tích chuyên sâu nếu sản phẩm chưa có phân tích
        from ai_engine.product_analyzer import product_analyzer
        ai_data = product.ai_analysis
        if not ai_data or not isinstance(ai_data, dict) or not ai_data.get("quality_summary"):
            try:
                logger.info(f"🧠 [CHAT AI ANALYZER] Bắt đầu phân tích AI chuyên sâu cho #{product.id} ({product.name[:30]})...")
                p_dict = serialize_product(product)
                ai_res = await product_analyzer.analyze_product(p_dict)
                ai_data = ai_res.model_dump()
                product.ai_analysis = ai_data
                session.add(product)
                await session.commit()
                await session.refresh(product)
            except Exception as ai_err:
                logger.warning(f"Lỗi AI Analyzer: {ai_err}")

        # 4. Soạn thảo bản tin phân tích Markdown trả về khung chat
        name = (ai_data.get("normalized_name") if ai_data else None) or product.name
        price = product.current_price or 0.0
        orig_price = product.original_price
        discount = product.discount_percentage
        rating = product.rating_star or 0.0
        sold = product.historical_sold or 0
        shop = product.shop_name or "Gian hàng Lazada"

        price_tag = f"**{price:,.0f} đ**"
        if orig_price and orig_price > price:
            disc_str = f" (-{discount:.0f}%)" if discount else ""
            price_tag += f" ~~{orig_price:,.0f} đ~~{disc_str}"

        ai_section = ""
        if ai_data and isinstance(ai_data, dict):
            quality = ai_data.get("quality_summary") or "Sản phẩm có độ hoàn thiện tốt, đáp ứng tốt nhu cầu."
            pros = ai_data.get("pros") or []
            cons = ai_data.get("cons") or []
            sentiment = ai_data.get("sentiment_score") or 8.5
            specs = ai_data.get("specs_summary") or []
            price_eval = ai_data.get("competitive_price_analysis") or "Mức giá hiện tại là cạnh tranh trên thị trường."
            p_opt = ai_data.get("recommended_price_optimal") or 0.0
            p_min = ai_data.get("recommended_price_min") or 0.0
            p_max = ai_data.get("recommended_price_max") or 0.0
            verdict = ai_data.get("buying_verdict") or "Rất đáng mua trong phân khúc giá này."
            target = ai_data.get("target_audience") or "Người tiêu dùng mua sắm trực tuyến."

            specs_md = "\n".join([f"- ⚙️ {s}" for s in specs[:5]]) if specs else ""
            if specs_md:
                specs_md = f"#### 📋 Thông số kỹ thuật cốt lõi:\n{specs_md}\n\n"

            pros_md = "\n".join([f"- ✅ **{p}**" for p in pros[:4]]) if pros else "- ✅ Độ hoàn thiện tốt, tính năng ổn định."
            cons_md = "\n".join([f"- ⚠️ {c}" for c in cons[:3]]) if cons else "- ⚠️ Nên đối chiếu thêm các voucher giảm giá để có deal tốt nhất."

            pricing_md = f"#### 🏷️ Phân tích định giá & Khuyến nghị:\n{price_eval}"
            if p_opt > 0:
                pricing_md += f"\n- 🎯 **Mức giá mua tối ưu:** `{p_opt:,.0f} đ`"
            if p_min > 0 and p_max > 0:
                pricing_md += f" *(Khoảng giá hợp lý: `{p_min:,.0f} đ` – `{p_max:,.0f} đ`)*"

            ai_section = (
                f"#### 💡 Tóm tắt chất lượng (Điểm AI: {sentiment}/10)\n"
                f"{quality}\n\n"
                f"{specs_md}"
                f"#### 🌟 Ưu điểm nổi bật (Bóc tách từ đánh giá thực tế):\n"
                f"{pros_md}\n\n"
                f"#### ⚠️ Nhược điểm & Điểm cần lưu ý:\n"
                f"{cons_md}\n\n"
                f"{pricing_md}\n\n"
                f"#### 🏆 Kết luận & Lời khuyên:\n"
                f"**{verdict}**\n\n"
                f"🎯 *Phù hợp với:* {target}"
            )
        else:
            ai_section = (
                f"💡 **Đánh giá tổng quan:** Sản phẩm đã được đồng bộ vào hệ thống. "
                f"Bạn có thể xem chi tiết thông số hoặc theo dõi biến động giá qua các nút chức năng bên dưới."
            )

        response_text = (
            f"### 🔍 KẾT QUẢ CÀO & PHÂN TÍCH LINK SẢN PHẨM LAZADA\n\n"
            f"📦 **Tên sản phẩm:** **{name}**\n"
            f"💰 **Giá bán:** {price_tag}\n"
            f"⭐ **Đánh giá:** `{rating:.1f}★` | 🔥 **Đã bán:** `{sold:,}` | 🏪 **Gian hàng:** `{shop}`\n\n"
            f"---\n\n"
            f"{ai_section}\n\n"
            f"👉 *Bạn có thể bấm nút **Lịch sử giá**, **Lưu theo dõi** hoặc **Xem** trực tiếp ở thẻ sản phẩm bên dưới!*"
        )

        return response_text, [product]

    async def _handle_clarification(
        self, 
        raw_msg: str, 
        classification: IntentClassificationResult,
        model: str = "meta/llama-3.1-8b-instruct"
    ) -> str:
        """Xử lý thiếu thông tin cụ thể: Hỏi lại các tiêu chí then chốt"""
        prod_type = classification.entities.product_type or "sản phẩm"
        brand = classification.entities.brand
        missing = ", ".join(classification.entities.missing_criteria) if classification.entities.missing_criteria else "Ngân sách, Nhu cầu cụ thể"

        prompt = (
            f"{SYSTEM_ROLE_PROMPT}\n\n"
            f"{CLARIFICATION_PROMPT_TEMPLATE.format(user_query=raw_msg, product_type=prod_type, brand=brand, missing_criteria=missing)}"
        )
        ai_res = await self._generate_text(prompt, model=model)
        if ai_res:
            return ai_res

        # Fallback Template
        brand_text = f" ({brand})" if brand else ""
        return (
            f"Chào bạn! Để mình tư vấn **{prod_type}{brand_text}** ưng ý và đúng nhu cầu nhất, bạn giúp mình làm rõ thêm vài tiêu chí nhé:\n\n"
            f"1. 💰 **Ngân sách tối đa của bạn là bao nhiêu?** (VD: Dưới 500k, 1 - 2 triệu, Flagship...)\n"
            f"2. 🎯 **Nhu cầu sử dụng chính:** (VD: Chụp ảnh, Làm việc, Chơi game...)\n"
            f"3. ⚙️ **Phiên bản / Dung lượng mong muốn:** (VD: 128GB, 256GB, bản thường hay bản Pro...)\n\n"
            f"👉 *Bạn có thể trả lời nhanh ví dụ: 'Tầm 15 triệu, bản 256GB' để mình lọc deal tốt nhất nhé!*"
        )

    async def _handle_unrealistic(
        self, 
        raw_msg: str, 
        classification: IntentClassificationResult,
        model: str = "meta/llama-3.1-8b-instruct"
    ) -> str:
        """Xử lý ngân sách phi thực tế: Cảnh báo giá và gợi ý giải pháp thay thế"""
        budget_max = classification.entities.budget_max or 0
        reason = classification.entities.unrealistic_reason or "Mức giá này quá thấp so với giá trị thực tế của sản phẩm"

        prompt = (
            f"{SYSTEM_ROLE_PROMPT}\n\n"
            f"{UNREALISTIC_PROMPT_TEMPLATE.format(user_query=raw_msg, budget_max=f'{budget_max:,.0f}', unrealistic_reason=reason)}"
        )
        ai_res = await self._generate_text(prompt, model=model)
        if ai_res:
            return ai_res

        # Fallback Template
        budget_str = f"{budget_max:,.0f} đ" if budget_max > 0 else "mức giá trên"
        return (
            f"⚠️ **Lưu ý về giá thị trường:**\n\n"
            f"Mức ngân sách **{budget_str}** cho yêu cầu của bạn là **không khả thi trên thị trường hiện nay** ({reason}).\n\n"
            f"🛑 **Lưu ý an toàn:**\n"
            f"- Nếu bạn thấy nơi nào bán sản phẩm này với giá trên, 99.9% là **hàng dựng, hàng nhái kém chất lượng hoặc chiêu trò lừa cọc/đổi trả**.\n\n"
            f"💡 **Phương án gợi ý thay thế tối ưu:**\n"
            f"1. **Mua hàng Cũ / Like New chính hãng:** Chọn các đời máy trước có kiểm định uy tín.\n"
            f"2. **Chuyển sang phân khúc phù hợp:** Với tầm tiền `{budget_str}`, bạn hoàn toàn có thể chọn các dòng sản phẩm chất lượng tốt từ các thương hiệu phổ thông (Xiaomi, Baseus, Dareu, E-Dra...).\n\n"
            f"👉 Bạn có muốn mình tìm các mẫu sản phẩm tốt nhất trong đúng tầm ngân sách `{budget_str}` không?"
        )

    async def _handle_chitchat(self, raw_msg: str, model: str = "meta/llama-3.1-8b-instruct") -> str:
        """Xử lý trò chuyện ngoài lề: Từ chối ngắn gọn và điều hướng lại mua sắm"""
        prompt = (
            f"{SYSTEM_ROLE_PROMPT}\n\n"
            f"{CHITCHAT_REDIRECT_PROMPT.format(user_query=raw_msg)}"
        )
        ai_res = await self._generate_text(prompt, model=model)
        if ai_res:
            return ai_res

        # Fallback Template
        return (
            "Chào bạn! Mình là **Trợ lý Săn Deal & Mua sắm E-Commerce**. "
            "Mình chỉ chuyên về tìm kiếm sản phẩm, so sánh giá cả và tư vấn chọn đồ công nghệ trên Shopee/Lazada thôi. "
            "Hôm nay bạn đang cần tìm mua hoặc so sánh món đồ nào, cứ bảo mình nhé! 🛒"
        )

    async def _handle_comparison(
        self, 
        session: AsyncSession, 
        classification: IntentClassificationResult,
        model: str = "meta/llama-3.1-8b-instruct"
    ) -> Tuple[str, Dict[str, Any]]:
        """Xử lý chế độ so sánh: Cào cả 2 sản phẩm và tạo bảng đối chiếu thông số & giá live"""
        prods_to_compare = classification.entities.products_to_compare
        if len(prods_to_compare) < 2:
            prods_to_compare = ["Sản phẩm A", "Sản phẩm B"]

        prod_a_name = prods_to_compare[0]
        prod_b_name = prods_to_compare[1]

        logger.info(f"🔄 [COMPARISON MODE] Bắt đầu cào dữ liệu cho: '{prod_a_name}' vs '{prod_b_name}'")

        # Cào dữ liệu cho cả 2 sản phẩm (an toàn với try-except)
        prods_a = []
        prods_b = []
        try:
            lazada = LazadaScraper()
            prods_a = await lazada.search(prod_a_name, limit=3)
            prods_b = await lazada.search(prod_b_name, limit=3)
            all_crawled = prods_a + prods_b
            if all_crawled:
                await pipeline_service.process_scraped_products(session, all_crawled)
        except Exception as e:
            logger.warning(f"Live crawler gặp sự cố khi so sánh: {e}")

        # Lấy thông tin đại diện
        top_a = prods_a[0] if prods_a else None
        top_b = prods_b[0] if prods_b else None

        a_price = f"{top_a.current_price:,.0f}" if top_a else "Đang cập nhật"
        a_sold = f"{top_a.historical_sold:,}" if top_a else "0"
        a_rating = f"{top_a.rating_star}" if top_a else "4.8"

        b_price = f"{top_b.current_price:,.0f}" if top_b else "Đang cập nhật"
        b_sold = f"{top_b.historical_sold:,}" if top_b else "0"
        b_rating = f"{top_b.rating_star}" if top_b else "4.8"

        comparison_data = {
            "product_a": {"name": prod_a_name, "price": a_price, "sold": a_sold, "rating": a_rating, "url": top_a.url if top_a else None},
            "product_b": {"name": prod_b_name, "price": b_price, "sold": b_sold, "rating": b_rating, "url": top_b.url if top_b else None},
        }

        prompt = (
            f"{SYSTEM_ROLE_PROMPT}\n\n"
            f"{COMPARISON_SYNTHESIS_PROMPT.format(prod_a_name=prod_a_name, prod_a_price=a_price, prod_a_sold=a_sold, prod_a_rating=a_rating, prod_b_name=prod_b_name, prod_b_price=b_price, prod_b_sold=b_sold, prod_b_rating=b_rating)}"
        )
        ai_res = await self._generate_text(prompt, model=model)
        if ai_res:
            prods_for_sanitize = [p for p in (prods_a + prods_b) if p]
            cleaned_text = self._sanitize_markdown_links(ai_res, prods_for_sanitize)
            return cleaned_text, comparison_data

        # Fallback Comparison Table
        text = (
            f"### ⚔️ BẢNG ĐỐI CHIẾU SO SÁNH: {prod_a_name.upper()} VS {prod_b_name.upper()}\n\n"
            f"| Tiêu chí | **{prod_a_name}** | **{prod_b_name}** |\n"
            f"| :--- | :--- | :--- |\n"
            f"| 💵 **Giá sàn TMĐT** | **~ {a_price} đ** | **~ {b_price} đ** |\n"
            f"| 🔥 **Lượt bán & Đánh giá** | {a_sold} đã bán (⭐ {a_rating}) | {b_sold} đã bán (⭐ {b_rating}) |\n"
            f"| 🎯 **Phân khúc / Nhu cầu** | Chơi game / Đa dụng | Tối ưu trọng lượng / Di động |\n"
            f"| 🔋 **Kết nối & Pin** | Không dây 2.4G ổn định | Dual Mode (Bluetooth + 2.4G) |\n"
            f"| 🌟 **Ưu điểm vượt trội** | Độ bền cao, form cầm đầm tay | Trọng lượng nhẹ, switch êm ái |\n\n"
            f"#### 💡 Lời khuyên lựa chọn (Verdict):\n"
            f"- 👉 **Nên chọn `{prod_a_name}` nếu:** Bạn thích cảm giác cầm đầm tay, độ ổn định kết nối cao và thương hiệu phổ biến dễ thay linh kiện.\n"
            f"- 👉 **Nên chọn `{prod_b_name}` nếu:** Bạn ưu tiên chuột siêu nhẹ, thường xuyên mang đi học/đi làm và thích kết nối Bluetooth đa thiết bị."
        )
        return text, comparison_data

    @staticmethod
    def _sanitize_markdown_links(text: str, products: List[Any]) -> str:
        """
        Bảo vệ toàn diện chống hallucination link từ LLM:
        - Quét mọi Markdown link dạng [Label](url) trong câu trả lời.
        - Nếu URL trùng khớp với link thật đã cào -> Giữ nguyên.
        - Nếu LLM tự chế/rút gọn link -> Tự động ánh xạ về link thật của sản phẩm tương ứng trong danh sách cào được.
        - Nếu không tìm thấy sản phẩm cụ thể -> Thay bằng link tìm kiếm chuẩn trên Lazada (đảm bảo không 404).
        """
        if not text or not products:
            return text

        valid_urls = set()
        for p in products:
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

            for p in products:
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

    @staticmethod
    def _extract_core_product_keywords(query: str) -> List[str]:
        """
        Tách và trích xuất danh từ chỉ sản phẩm/thiết bị cốt lõi.
        Loại bỏ stop words và TẤT CẢ các tính từ chỉ chất lượng/mô tả chung (cao cấp, giá rẻ, chính hãng...).
        """
        stopwords = {
            "tôi", "toi", "muốn", "muon", "cần", "can", "hãy", "hay", "tư", "tu", "vấn", "van",
            "cho", "đời", "doi", "mới", "moi", "loại", "loai", "các", "cac", "những", "nhung",
            "cái", "cai", "cục", "cuc", "con", "chiếc", "chiec", "mua", "tìm", "tim", "giúp",
            "giup", "nào", "nao", "gì", "gi", "ở", "o", "tại", "tai", "nhà", "nha", "để", "de",
            "dùng", "dung", "sử", "su", "với", "voi", "tầm", "tam", "khoảng", "khoang"
        }

        modifiers = {
            "cao", "cấp", "chính", "hãng", "giá", "rẻ", "tốt", "nhất", "mini", "nhỏ", "gọn",
            "bền", "đẹp", "xịn", "pro", "max", "plus", "vip", "đa", "năng", "thông", "minh",
            "tiện", "lợi", "nhập", "khẩu", "hot", "sale", "sỉ", "combo", "freeship", "chất",
            "lượng", "full", "box", "chuẩn", "đắt", "tiền", "bản", "hàng", "chính", "hiệu"
        }

        words = [w.lower() for w in query.split() if len(w) >= 2]
        non_stop = [w for w in words if w not in stopwords]
        core_nouns = [w for w in non_stop if w not in modifiers]
        return core_nouns if core_nouns else non_stop

    @classmethod
    def _rank_products_by_relevance(
        cls,
        candidates: List[Product], 
        raw_query: str, 
        search_kw: str, 
        budget_max: Optional[float] = None
    ) -> List[Product]:
        """Thuật toán xếp hạng và lọc sản phẩm chính xác theo từ khóa danh từ cốt lõi, thương hiệu và ngữ nghĩa"""
        if not candidates:
            return []

        core_nouns = cls._extract_core_product_keywords(f"{search_kw} {raw_query}")
        scored = []
        for p in candidates:
            name_lower = (p.name or "").lower()
            score = 0.0

            # 1. BẮT BUỘC: Phải chứa ít nhất 1 DANH TỪ CỐT LÕI (Core Noun) của sản phẩm
            matched_nouns = [w for w in core_nouns if w in name_lower]
            if not matched_nouns:
                # Nếu chỉ khớp từ phụ (như 'cao cấp', 'giá rẻ') mà không có danh từ cốt lõi -> Loại bỏ 100%
                continue

            match_ratio = len(matched_nouns) / len(core_nouns) if core_nouns else 0
            score += len(matched_nouns) * 25.0 + match_ratio * 30.0

            # 2. Khớp cụm từ nguyên văn
            if search_kw.lower() in name_lower:
                score += 40.0

            # 3. Phạt nặng nếu đề xuất sản phẩm thuộc danh mục lệch hoàn toàn
            neg_keywords = ["kẹo", "bánh", "dù câu", "câu cá", "quần", "áo", "váy", "giày", "dép", "nước giặt", "dầu gội", "sữa tắm", "tất", "vớ"]
            if not any(neg in f"{search_kw} {raw_query}".lower() for neg in neg_keywords):
                if any(neg in name_lower for neg in neg_keywords):
                    score -= 200.0

            # Phạt phụ kiện nếu người dùng tìm thiết bị chính
            main_device_terms = ["router", "wifi", "điện thoại", "iphone", "samsung", "laptop", "chuột", "bàn phím", "tai nghe"]
            if any(term in core_nouns for term in main_device_terms):
                if any(neg in name_lower for neg in ["dây điện", "cáp sạc", "củ sạc", "ốp lưng", "kính cường lực", "bao da", "miếng dán"]):
                    if not any(acc in f"{search_kw} {raw_query}".lower() for acc in ["cáp", "sạc", "ốp", "kính", "bao da"]):
                        score -= 50.0

            # 4. Giá cả phù hợp ngân sách
            if budget_max and budget_max > 0:
                if p.current_price and p.current_price <= budget_max:
                    score += 5.0
                elif p.current_price and p.current_price > budget_max * 1.2:
                    score -= 15.0

            # 5. Điểm phụ: Lượt bán & Đánh giá
            score += min((p.historical_sold or 0) / 1000.0, 3.0)
            score += (p.rating_star or 0.0) * 0.5

            if score > 0:
                scored.append((score, p))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [p for _, p in scored[:6]]

    async def _handle_recommendation(
        self, 
        session: AsyncSession, 
        raw_msg: str, 
        classification: IntentClassificationResult,
        model: str = "meta/llama-3.1-8b-instruct"
    ) -> Tuple[str, List[Product]]:
        """Xử lý gợi ý mua sắm: Tra cứu Qdrant Vector Store trước, cào dữ liệu live nếu cần, và tổng hợp bài tư vấn"""
        search_kw = classification.search_keyword or raw_msg
        budget_max = classification.entities.budget_max
        core_nouns = self._extract_core_product_keywords(search_kw)

        logger.info(f"🔍 [RECOMMENDATION] Đối soát sản phẩm cho từ khóa: '{search_kw}' (Core Nouns: {core_nouns}, Ngân sách: {budget_max or 'Không giới hạn'})")
        
        # 1. Qdrant Semantic Search: Tìm kiếm qua Vector DB với ngưỡng tương đồng tin cậy
        qdrant_product_ids = []
        if qdrant_store.is_available:
            try:
                query_vec = await embedding_service.get_embedding(search_kw)
                qdrant_hits = qdrant_store.search_similar(
                    query_vector=query_vec,
                    limit=20,
                    score_threshold=0.40,
                    price_max=budget_max,
                )
                qdrant_product_ids = [hit["id"] for hit in qdrant_hits]
                logger.info(f"🧠 [QDRANT] Tìm thấy {len(qdrant_product_ids)} sản phẩm tương đồng cao cho '{search_kw}'")
            except Exception as e:
                logger.warning(f"Qdrant search lỗi, fallback sang DB: {e}")

        # 2. Lấy Product entities từ PostgreSQL (hoặc tìm kiếm ILIKE theo DANH TỪ CỐT LÕI nếu Qdrant trống)
        db_candidates: List[Product] = []
        if qdrant_product_ids:
            res_db = await session.execute(select(Product).where(Product.id.in_(qdrant_product_ids)))
            db_map = {p.id: p for p in res_db.scalars().all()}
            db_candidates = [db_map[pid] for pid in qdrant_product_ids if pid in db_map]
        else:
            # Fallback thông minh: CHỈ tìm kiếm theo core_nouns (như 'router', 'wifi'), TUYỆT ĐỐI không query theo 'cao cấp'
            if core_nouns:
                conditions = [Product.name.ilike(f"%{w}%") for w in core_nouns]
                res_db = await session.execute(select(Product).where(or_(*conditions)).limit(30))
                db_candidates = list(res_db.scalars().all())

        # 3. Đếm số sản phẩm thực sự chứa Core Nouns trong kho
        valid_cached_prods = [p for p in db_candidates if any(w in (p.name or "").lower() for w in core_nouns)]
        
        # 4. Nếu kho dữ liệu chưa có đủ sản phẩm thực sự khớp (< 2 sản phẩm), kích hoạt Live Crawler từ Lazada
        fresh_products: List[Product] = []
        if len(valid_cached_prods) < 2:
            try:
                logger.info(f"🕷️ [LIVE CRAWL] Kho chưa có đủ sản phẩm cho '{search_kw}'. Kích hoạt cào trực tiếp từ Lazada...")
                crawled_items = await crawler_service.scrape_products(keyword_or_url=search_kw, platform="lazada", limit=10)
                if crawled_items:
                    pipeline_res = await pipeline_service.process_scraped_products(session, crawled_items)
                    fresh_products = pipeline_res.products
            except Exception as e:
                logger.warning(f"Live crawler gặp sự cố: {e}")

        # Gộp sản phẩm vừa cào (ưu tiên hàng đầu) và sản phẩm từ DB
        seen_ids = set()
        all_candidates = []
        for p in fresh_products + valid_cached_prods:
            if p.id not in seen_ids:
                seen_ids.add(p.id)
                all_candidates.append(p)

        # 5. Lọc và xếp hạng sản phẩm nghiêm ngặt theo từ khóa & danh mục
        products = self._rank_products_by_relevance(all_candidates, raw_msg, search_kw, budget_max)
        budget_range = f"Dưới {budget_max:,.0f} đ" if budget_max else "Phù hợp thị trường"

        # 6. Xử lý trường hợp không tìm thấy sản phẩm nào khớp
        if not products:
            logger.info(f"ℹ️ [RECOMMENDATION] Không có sản phẩm nào trong kho khớp với '{search_kw}'. Tạo bài tư vấn chọn mua tổng quan.")
            advice_prompt = (
                f"{SYSTEM_ROLE_PROMPT}\n\n"
                f"Yêu cầu của người dùng: \"{raw_msg}\"\n"
                f"Sản phẩm đang tìm kiếm: \"{search_kw}\"\n"
                f"Ngân sách dự kiến: {budget_range}\n\n"
                f"LƯU Ý QUAN TRỌNG: Hiện tại hệ thống chưa có sẵn danh sách sản phẩm cào trực tiếp từ sàn cho từ khóa này.\n"
                f"Hãy đóng vai chuyên gia mua sắm và viết bài tư vấn chọn mua chuyên nghiệp:\n"
                f"1. Xác nhận đúng nhu cầu của người dùng (ví dụ: tư vấn chọn mua {search_kw}).\n"
                f"2. Nêu các tiêu chí kỹ thuật cốt lõi cần lưu ý khi chọn mua loại sản phẩm này (thương hiệu uy tín, thông số chuẩn, tính năng cần có...).\n"
                f"3. Gợi ý các phân khúc giá và model tiêu biểu trên thị trường.\n"
                f"4. TUYỆT ĐỐI KHÔNG tự bịa đặt link sản phẩm giả mạo.\n"
                f"5. Hướng dẫn người dùng có thể gửi link sản phẩm cụ thể trên Lazada vào khung chat để AI bóc tách giá và phân tích sâu.\n"
            )
            ai_res = await self._generate_text(advice_prompt, model=model)
            if ai_res:
                guarded_text = product_guardrail.guard_recommendation_output(ai_res, [], raw_msg, search_kw)
                return guarded_text, []

            guarded_text = product_guardrail.guard_recommendation_output("", [], raw_msg, search_kw)
            return guarded_text, []

        # 6. Chuẩn bị context sản phẩm thật đã cào
        prod_context = ""
        for idx, p in enumerate(products, 1):
            prod_context += (
                f"{idx}. {p.name}\n"
                f"   - Giá hiện tại: {p.current_price:,.0f}đ (Giảm {p.discount_percentage or 0}%)\n"
                f"   - Đã bán: {p.historical_sold:,} | Đánh giá: {p.rating_star}*\n"
                f"   - Shop: {p.shop_name or 'Gian hàng TMĐT'} | Link: {p.url}\n\n"
            )

        prompt = (
            f"{SYSTEM_ROLE_PROMPT}\n\n"
            f"{RECOMMENDATION_SYNTHESIS_PROMPT.format(user_query=raw_msg, budget_range=budget_range, crawled_products_context=prod_context)}"
        )
        ai_res = await self._generate_text(prompt, model=model)
        if ai_res:
            guarded_text = product_guardrail.guard_recommendation_output(ai_res, list(products), raw_msg, search_kw)
            return guarded_text, list(products)

        # Fallback Synthesis
        text = f"### 🛒 TOP SẢN PHẨM ĐÁNG MUA NHẤT THEO YÊU CẦU CỦA BẠN:\n\n"
        for idx, p in enumerate(products[:4], 1):
            text += (
                f"**{idx}. [{p.name}]({p.url})**\n"
                f"- 💵 **Giá:** `{p.current_price:,.0f} đ` | 🔥 **Đã bán:** `{p.historical_sold:,}` (⭐ `{p.rating_star}`)\n"
                f"- 🏪 **Gian hàng:** {p.shop_name or 'Lazada Mall/Verified'}\n"
                f"- 💡 **Đánh giá nhanh:** Lựa chọn bán chạy, được cộng đồng đánh giá cao trong phân khúc `{budget_range}`.\n\n"
            )
        text += "👉 *Bạn có thể bấm vào thẻ sản phẩm bên dưới để xem hình ảnh chi tiết hoặc mở trực tiếp trên sàn TMĐT!*"
        return text, list(products)

    # =========================================================================
    # SESSION & MESSAGE HELPERS
    # =========================================================================

    async def _get_or_create_session(self, session: AsyncSession, session_id: str, user_id: Optional[str]) -> ChatSession:
        stmt = select(ChatSession).where(ChatSession.id == session_id)
        res = await session.execute(stmt)
        sess = res.scalar_one_or_none()
        if not sess:
            sess = ChatSession(id=session_id, user_id=user_id, context_data={})
            session.add(sess)
            await session.commit()
            await session.refresh(sess)
        return sess

    async def _get_session_history(self, session: AsyncSession, session_id: str, limit: int = 6) -> List[Dict[str, str]]:
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(desc(ChatMessage.created_at))
            .limit(limit)
        )
        res = await session.execute(stmt)
        msgs = res.scalars().all()
        history = []
        for m in reversed(msgs):
            history.append({
                "role": "user" if m.role == "user" else "model",
                "content": m.content
            })
        return history

    async def _save_message(
        self,
        session: AsyncSession,
        session_id: str,
        sender: str,
        message: str,
        intent: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ChatMessage:
        msg = ChatMessage(
            session_id=session_id,
            role=sender,
            content=message,
            intent=intent,
            metadata_json=metadata or {}
        )
        session.add(msg)
        await session.commit()
        return msg


shopping_assistant = ShoppingAssistant()
