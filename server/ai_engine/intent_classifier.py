import re
import json
from typing import List, Dict, Optional, Any
from loguru import logger

from config.settings import settings
from core.schemas import ChatIntentEnum, ExtractedEntities, IntentClassificationResult
from ai_engine.prompts import SYSTEM_ROLE_PROMPT, INTENT_CLASSIFIER_PROMPT

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None

import warnings
warnings.filterwarnings("ignore", message=".*automatic function calling.*")
warnings.filterwarnings("ignore", category=UserWarning, module="google.genai")


# =============================================================================
# 1. FAST-PATH GUARDRAILS (STAGE 1: PURE REGEX / ZERO TOKEN COST)
# =============================================================================

class FastPathGuardrails:
    """
    Tầng Guardrails Fast-Path (Sub-millisecond, 0 token LLM):
    - Chặn đứng ngay lập tức các hành vi Prompt Injection / Jailbreak / Vi phạm an toàn.
    - Lọc nhanh các câu chào hỏi, hỏi thời tiết, ngoài lề thuần túy trước khi gọi LLM.
    """

    INJECTION_PATTERNS = [
        r"\b(system\s*prompt|bỏ\s*qua\s*các\s*lệnh|ignore\s*previous\s*instructions|jailbreak)\b",
        r"\b(đm|đkm|vcl|vl|địt|lừa\s*đảo\s*bot)\b"
    ]

    CHITCHAT_PATTERNS = [
        r"^(thời\s*tiết|dự\s*báo\s*thời\s*tiết|mấy\s*giờ|bây\s*giờ\s*mấy\s*giờ|hôm\s*nay\s*thứ\s*mấy)\b",
        r"^(viết\s*code|làm\s*thơ|kể\s*chuyện\s*cười|hát\s*đi|bạn\s*là\s*ai|ai\s*tạo\s*ra\s*bạn)\b",
        r"^(chào\s*bạn|hello|hi\s*bot|chào\s*em|hi\s*shop)\s*[\?\!\.]*$"
    ]

    SHOPPING_KEYWORDS = {"mua", "giá", "sản phẩm", "deal", "shop", "tìm", "tư vấn", "tiền", "đồ", "hàng"}

    def evaluate(self, message: str) -> Optional[IntentClassificationResult]:
        """Kiểm tra nhanh tin nhắn. Trả về IntentClassificationResult nếu khớp, ngược lại trả về None."""
        msg_lower = message.lower().strip()

        # 1.1 Kiểm tra Safety Guard
        for pattern in self.INJECTION_PATTERNS:
            if re.search(pattern, msg_lower, re.IGNORECASE):
                return IntentClassificationResult(
                    intent=ChatIntentEnum.SAFETY_GUARD,
                    confidence=1.0,
                    reasoning="Fast-Path: Phát hiện tín hiệu vi phạm tiêu chuẩn an toàn hoặc can thiệp hệ thống"
                )

        # 1.2 Kiểm tra Out-of-Scope Chitchat
        is_chitchat = any(re.search(pat, msg_lower, re.IGNORECASE) for pat in self.CHITCHAT_PATTERNS)
        words = set(re.split(r"\s+", msg_lower))
        has_shopping_intent = bool(words & self.SHOPPING_KEYWORDS)

        if is_chitchat and not has_shopping_intent:
            return IntentClassificationResult(
                intent=ChatIntentEnum.CHITCHAT_OUT_OF_SCOPE,
                confidence=1.0,
                reasoning="Fast-Path: Câu hỏi chào hỏi hoặc ngoài phạm vi tư vấn mua sắm TMĐT"
            )

        return None


# =============================================================================
# 2. LLM STRUCTURED PARSER (STAGE 2: NATIVE PYDANTIC SCHEMA ENGINE)
# =============================================================================

class LLMStructuredParser:
    """
    Tầng Primary Engine: Sử dụng NVIDIA NIM (Llama 3.1/3.3, Mistral) hoặc Gemini Native Pydantic
    - Tự động serialize/deserialize 100% Type-Safety vào IntentClassificationResult.
    - Zero-Shot Entity Resolution: Xử lý mọi nhãn hàng, model, phiên bản trên thế giới mà không cần hardcode.
    - Tiết kiệm chi phí tối đa khi dùng NVIDIA NIM (Llama 3.1 8B).
    """

    def __init__(self, model_name: str = "meta/llama-3.1-8b-instruct"):
        self.model_name = model_name
        self.gemini_client = None
        self.nvidia_client = None

        # Khởi tạo Gemini Client
        gemini_key = settings.get_gemini_api_key()
        if gemini_key and genai:
            try:
                self.gemini_client = genai.Client(api_key=gemini_key)
            except Exception as e:
                logger.warning(f"Không thể khởi tạo Gemini Client: {e}")

        # Khởi tạo NVIDIA Client (OpenAI-compatible)
        nvidia_key = settings.get_nvidia_api_key()
        if nvidia_key:
            try:
                from openai import AsyncOpenAI
                self.nvidia_client = AsyncOpenAI(
                    base_url=settings.NVIDIA_BASE_URL,
                    api_key=nvidia_key
                )
            except Exception as e:
                logger.warning(f"Không thể khởi tạo NVIDIA Client: {e}")

    async def parse(
        self, 
        message: str, 
        history: Optional[List[Dict[str, str]]] = None,
        model_name: Optional[str] = None
    ) -> Optional[IntentClassificationResult]:
        """Gửi prompt tới NVIDIA NIM hoặc Gemini với JSON Structured Output"""
        target_model = model_name or self.model_name
        if target_model.startswith("fallback") or "heuristic" in target_model:
            return None

        history_context = ""
        if history:
            history_context = "Lịch sử hội thoại gần nhất:\n"
            for h in history[-4:]:
                history_context += f"- {h['role'].upper()}: {h['content']}\n"

        prompt = (
            f"{SYSTEM_ROLE_PROMPT}\n\n"
            f"{INTENT_CLASSIFIER_PROMPT}\n\n"
            f"{history_context}\n"
            f"Tin nhắn mới của người dùng: \"{message}\"\n\n"
            f"Hãy phân loại và CHỈ TRẢ VỀ DUY NHẤT 1 ĐOẠN JSON HỢP LỆ THEO SCHEMA:\n"
            f'{{"intent": "recommendation"|"comparison"|"clarification_needed"|"unrealistic_constraints"|"chitchat_out_of_scope"|"safety_guard", "confidence": 0.95, "search_keyword": "từ khóa tìm kiếm tối ưu trên Shopee/Lazada", "entities": {{"product_type": "...", "brand": "...", "budget_max": null, "budget_min": null, "features": [], "products_to_compare": [], "is_realistic": true, "unrealistic_reason": null, "missing_criteria": []}}, "reasoning": "giải thích ngắn gọn"}}'
        )

        # 1. Nếu là NVIDIA Model (meta/llama, mistralai/...)
        is_nvidia_model = "/" in target_model or "llama" in target_model or "mistral" in target_model or "deepseek" in target_model
        if is_nvidia_model:
            if not self.nvidia_client:
                logger.warning("NVIDIA Client chưa được khởi tạo. Chuyển sang Graceful Fallback.")
                return None
            try:
                res = await self.nvidia_client.chat.completions.create(
                    model=target_model,
                    messages=[
                        {"role": "system", "content": "You are a professional JSON classification engine. Output strictly valid JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.1,
                    max_tokens=600
                )
                if res and res.choices:
                    raw_content = res.choices[0].message.content or ""
                    # Trích xuất JSON bằng regex nếu có bọc code block
                    json_match = re.search(r"\{.*\}", raw_content, re.DOTALL)
                    if json_match:
                        json_str = json_match.group(0)
                        data = json.loads(json_str)
                        parsed = IntentClassificationResult.model_validate(data)
                        if not parsed.search_keyword:
                            parsed.search_keyword = message
                        return parsed
            except Exception as e:
                logger.warning(f"Lỗi khi gọi NVIDIA Structured Parser ({target_model}): {e}")
            return None

        # 2. Nếu là Gemini Model
        if "gemini" in target_model and self.gemini_client:
            # Map model name sang model mới nhất nếu là chuỗi chung hoặc model cũ
            gemini_model = "gemini-3.6-flash" if ("2.0" in target_model or target_model == "gemini") else target_model
            try:
                response = self.gemini_client.models.generate_content(
                    model=gemini_model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.1,
                        response_mime_type="application/json",
                        response_schema=IntentClassificationResult
                    )
                )
                if response and response.parsed:
                    parsed_result: IntentClassificationResult = response.parsed
                    if not parsed_result.search_keyword:
                        parsed_result.search_keyword = message
                    return parsed_result
            except Exception as e:
                logger.warning(f"Lỗi khi gọi Gemini Structured Parser ({gemini_model}): {e}")
            return None

        return None


# =============================================================================
# 3. GRACEFUL FALLBACK HANDLER (STAGE 3: GENERIC LINGUISTIC HEURISTIC)
# =============================================================================

class GracefulFallbackHandler:
    """
    Tầng Fallback an toàn (Generic Heuristic):
    - Hoạt động độc lập không cần mạng khi LLM mất kết nối hoặc hết quota.
    - Hoàn toàn Generic: Phân tích cú pháp câu và độ đặc hiệu token, KHÔNG hardcode danh sách thương hiệu/giá.
    """

    CONVERSATIONAL_PREFIXES = [
        "tư vấn", "gợi ý", "cho mình", "cho em", "cho tôi", "tìm mua", 
        "muốn mua", "cần mua", "hỏi về", "xem giúp", "bạn ơi", "shop ơi", "giúp mình"
    ]

    FILLER_TOKENS = {
        "giờ", "tôi", "mình", "em", "anh", "chị", "bạn", "muốn", "cần", "tìm", "mua", 
        "với", "ạ", "nhé", "nào", "ơi", "ad", "shop", "giúp", "ổn", "ngon", "tốt", 
        "được", "không", "giá", "tầm", "khoảng", "dưới"
    }

    SPECIFIC_MODIFIERS = {
        "mới nhất", "pro", "max", "ultra", "plus", "mini", "lite", 
        "gb", "tb", "gaming", "không dây", "bluetooth", "chống ồn", "ergonomic", "rgb"
    }

    def evaluate(
        self, 
        message: str, 
        history: Optional[List[Dict[str, str]]] = None
    ) -> IntentClassificationResult:
        """Phân tích cấu trúc câu dự phòng"""
        msg_lower = message.lower().strip()

        # 3.1 Cú pháp So sánh (Comparison) qua liên từ kết nối
        explicit_compare = any(sig in msg_lower for sig in ["so sánh", "con nào ngon hơn", "con nào tốt hơn", "nên chọn", "vs", "hay là con nào"])
        if explicit_compare or (" với " in msg_lower and any(w in msg_lower for w in ["hơn", "tốt hơn", "ngon hơn", "khác gì"])):
            prods = self._extract_comparison_products(msg_lower)
            if len(prods) >= 2:
                return IntentClassificationResult(
                    intent=ChatIntentEnum.COMPARISON,
                    confidence=0.90,
                    search_keyword=f"{prods[0]} {prods[1]}",
                    entities=ExtractedEntities(products_to_compare=prods),
                    reasoning="Fallback Engine: Phát hiện cấu trúc cú pháp so sánh đối chiếu"
                )

        # 3.2 Trích xuất Ngân sách tổng quát qua Regex
        extracted_budget = self._extract_generic_budget(msg_lower)

        # 3.3 Làm sạch chuỗi từ khóa
        clean_text = msg_lower
        for prefix in self.CONVERSATIONAL_PREFIXES:
            clean_text = clean_text.replace(prefix, " ")

        clean_tokens = [w for w in clean_text.split() if w and w not in self.FILLER_TOKENS]
        clean_keyword = " ".join(clean_tokens).strip()

        # 3.4 Phân định Clarification vs Recommendation theo độ đặc hiệu (Token Specificity)
        has_modifier = any(w in msg_lower for w in self.SPECIFIC_MODIFIERS)
        has_numbers = bool(re.search(r"\d+", msg_lower))

        # Nếu chỉ có 1 danh mục chung chung (không kèm số, không kèm modifier cụ thể)
        if not has_modifier and not has_numbers and not extracted_budget and len(clean_tokens) <= 3:
            prod_type = clean_keyword.title() if clean_keyword else "Sản phẩm công nghệ"
            return IntentClassificationResult(
                intent=ChatIntentEnum.CLARIFICATION_NEEDED,
                confidence=0.85,
                search_keyword=clean_keyword,
                entities=ExtractedEntities(
                    product_type=prod_type,
                    missing_criteria=["Ngân sách dự kiến", "Nhu cầu sử dụng chính", "Tính năng ưu tiên"]
                ),
                reasoning="Fallback Engine: Câu hỏi danh mục chung, cần hỏi thêm tiêu chí"
            )

        # 3.5 Mặc định: Đủ thông tin để tìm kiếm (Recommendation)
        return IntentClassificationResult(
            intent=ChatIntentEnum.RECOMMENDATION,
            confidence=0.80,
            search_keyword=clean_keyword if clean_keyword else message,
            entities=ExtractedEntities(
                budget_max=extracted_budget,
                product_type=clean_keyword,
                features=["mới nhất"] if "mới nhất" in msg_lower else []
            ),
            reasoning="Fallback Engine: Yêu cầu có đủ thông tin hoặc thực thể cụ thể để truy vấn"
        )

    def _extract_comparison_products(self, text: str) -> List[str]:
        """Tách 2 sản phẩm so sánh theo liên từ"""
        for d in [" vs ", " với ", " hay là ", " hay "]:
            if d in text:
                parts = text.split(d, 1)
                p1 = re.sub(r"^(so sánh|tư vấn|chọn|mua|giữa)\s*", "", parts[0]).strip()
                p2 = re.sub(r"\s*(con nào|nên chọn|tốt hơn|ngon hơn|hơn|\?).*$", "", parts[1]).strip()
                p2 = re.sub(r"\b(ạ|nhé|ơi|với)\b", "", p2).strip()
                if p1 and p2:
                    return [p1.title(), p2.title()]
        return []

    def _extract_generic_budget(self, text: str) -> Optional[float]:
        """Trích xuất ngân sách bằng Regex tổng quát hỗ trợ mọi đơn vị"""
        match = re.search(r"(\d+[\.,]?\d*)\s*(triệu|tr|k|nghìn|đ|vnd|m)", text)
        if not match:
            return None
        num = float(match.group(1).replace(",", "."))
        unit = match.group(2)
        if unit in ["triệu", "tr", "m"]:
            return num * 1_000_000
        elif unit in ["k", "nghìn"]:
            return num * 1_000
        return num


# =============================================================================
# 4. INTENT CLASSIFIER FACADE / PIPELINE COORDINATOR
# =============================================================================

class IntentClassifier:
    """
    Orchestrator điều phối Pipeline phân loại Ý định (Chain of Responsibility):
    1. Fast-Path Guardrails (Sub-millisecond, Regex pure, 0 token)
    2. LLM Structured Parser (Primary Engine với Native Pydantic schema)
    3. Graceful Fallback (Generic Linguistic Heuristic)
    """

    def __init__(self):
        self.guardrails = FastPathGuardrails()
        self.llm_parser = LLMStructuredParser()
        self.fallback = GracefulFallbackHandler()

    async def classify(
        self, 
        message: str, 
        history: Optional[List[Dict[str, str]]] = None,
        model: Optional[str] = None
    ) -> IntentClassificationResult:
        cleaned_msg = message.strip()

        # Bước 1: Fast-Path Guardrails (Tiết kiệm 100% chi phí và thời gian cho Safety/Chitchat)
        fast_result = self.guardrails.evaluate(cleaned_msg)
        if fast_result:
            logger.debug(f"⚡ [FAST-PATH GUARDRAIL] Intent: {fast_result.intent.value.upper()}")
            return fast_result

        # Bước 2: Primary LLM Parser (Native Pydantic Type-Safe Engine)
        llm_result = await self.llm_parser.parse(cleaned_msg, history, model_name=model)
        if llm_result:
            return llm_result

        # Bước 3: Graceful Fallback (Khi mất mạng hoặc hết Quota)
        logger.info("ℹ️ Chuyển tiếp sang Graceful Fallback Engine.")
        return self.fallback.evaluate(cleaned_msg, history)


intent_classifier = IntentClassifier()
