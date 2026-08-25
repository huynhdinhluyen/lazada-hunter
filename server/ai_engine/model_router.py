import json
import re
import enum
import asyncio
from typing import Dict, Any, Optional, Tuple, Type, List, Union
from pydantic import BaseModel
from loguru import logger

from config.settings import settings

try:
    from openai import AsyncOpenAI, APIStatusError, APIConnectionError, RateLimitError
except ImportError:
    AsyncOpenAI = None
    APIStatusError = Exception
    APIConnectionError = Exception
    RateLimitError = Exception

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None


class TaskComplexity(str, enum.Enum):
    LOW = "low"          # Tác vụ nhẹ: phân loại intent, trích xuất thực thể, chuẩn hóa ngắn -> Dùng Llama 3.1 8B (tiết kiệm token)
    MEDIUM = "medium"    # Tác vụ vừa: tóm tắt, trích xuất thông số kỹ thuật -> Dùng Llama 3.1 8B
    HIGH = "high"        # Tác vụ phức tạp: phân tích sâu reviews, đối chiếu ưu/nhược điểm, định giá cạnh tranh -> Dùng Llama 3.1 8B / Llama 3.3 70B


class DynamicModelRouter:
    """
    Bộ Điều Phối & Tự Động Xoay Model AI Thông Minh (Dynamic Model Router):
    1. Ưu tiên mặc định: NVIDIA NIM.
    2. Tự động chọn model theo độ phức tạp tác vụ để tối ưu chi phí & token:
       - Tác vụ nhẹ (LOW / MEDIUM): `meta/llama-3.1-8b-instruct` (nhẹ, cực nhanh ~1s, siêu tiết kiệm).
       - Tác vụ phân tích (HIGH): `meta/llama-3.1-8b-instruct` hoặc `meta/llama-3.3-70b-instruct`.
    3. Cơ chế Failover tự động (Tự phục hồi):
       - Nếu NVIDIA NIM gặp sự cố (hết credit 402, rate limit 429, lỗi 503/timeout), tự động xoay sang Google Gemini (Gemini 2.0 Flash / 1.5 Flash).
    4. Trích xuất JSON sạch chuẩn xác ngay cả khi LLM trả về Markdown / Python / Text bọc ngoài.
    """

    def __init__(self):
        self._nvidia_client: Optional[AsyncOpenAI] = None
        self._gemini_client = None
        self._init_clients()

    def _init_clients(self):
        nvidia_key = settings.get_nvidia_api_key()
        if nvidia_key and AsyncOpenAI:
            try:
                self._nvidia_client = AsyncOpenAI(
                    base_url=settings.NVIDIA_BASE_URL,
                    api_key=nvidia_key,
                    timeout=25.0
                )
            except Exception as e:
                logger.warning(f"Lỗi khởi tạo NVIDIA NIM Client: {e}")

        gemini_key = settings.get_gemini_api_key()
        if gemini_key and genai:
            try:
                self._gemini_client = genai.Client(api_key=gemini_key)
            except Exception as e:
                logger.warning(f"Lỗi khởi tạo Google Gemini Client: {e}")

    def _select_nvidia_model(self, complexity: Union[TaskComplexity, str]) -> str:
        """Chọn model NVIDIA NIM tối ưu nhất theo chi phí & hiệu năng"""
        comp_val = complexity.value if isinstance(complexity, TaskComplexity) else str(complexity).lower()
        if comp_val == "high":
            # Ưu tiên Llama 3.1 8B vì tốc độ phản hồi cực nhanh, chuẩn xác và không bị nghẽn quota
            return "meta/llama-3.1-8b-instruct"
        return "meta/llama-3.1-8b-instruct"

    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        complexity: Union[TaskComplexity, str] = TaskComplexity.LOW,
        temperature: float = 0.2,
        max_tokens: int = 1500,
    ) -> Tuple[str, str]:
        """
        Sinh văn bản với cơ chế xoay model và fallback tự động.
        Trả về: (nội dung_kết_quả, tên_model_đã_dùng)
        """
        comp_val = complexity.value if isinstance(complexity, TaskComplexity) else str(complexity).lower()

        # 1. Thử gọi qua NVIDIA NIM (ưu tiên hàng đầu)
        if self._nvidia_client:
            model_name = self._select_nvidia_model(complexity)
            try:
                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": prompt})

                logger.debug(f"🤖 [AI ROUTER] Gọi NVIDIA NIM: {model_name} (Complexity: {comp_val})")
                
                response = await self._nvidia_client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                content = response.choices[0].message.content or ""
                return content.strip(), f"NVIDIA NIM ({model_name})"

            except Exception as err:
                logger.warning(
                    f"⚠️ [AI ROUTER] NVIDIA NIM ({model_name}) gặp sự cố: {err}. "
                    f"Kích hoạt cơ chế Failover chuyển sang Google Gemini..."
                )

        # 2. Failover: Chuyển sang Google Gemini
        if self._gemini_client:
            for gemini_model in ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-2.5-flash"]:
                try:
                    logger.info(f"⚡ [AI ROUTER] Chuyển hướng sang Google Gemini ({gemini_model})")
                    full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
                    
                    res = await asyncio.to_thread(
                        self._gemini_client.models.generate_content,
                        model=gemini_model,
                        contents=full_prompt,
                    )
                    text = res.text or ""
                    if text.strip():
                        return text.strip(), f"Google Gemini ({gemini_model})"
                except Exception as gemini_err:
                    logger.warning(f"⚠️ [AI ROUTER] Google Gemini ({gemini_model}) lỗi: {gemini_err}")

        # 3. Nếu không có API nào hoạt động
        logger.error("❌ [AI ROUTER] Tất cả các LLM Provider đều không khả dụng!")
        raise RuntimeError("Tất cả dịch vụ AI (NVIDIA NIM & Google Gemini) đều không khả dụng hoặc chưa có API Key hợp lệ.")

    async def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        complexity: Union[TaskComplexity, str] = TaskComplexity.HIGH,
        temperature: float = 0.1,
    ) -> Tuple[Dict[str, Any], str]:
        """
        Sinh JSON có cấu trúc an toàn với cơ chế Clean Markdown & Fix JSON.
        Trả về: (dict_dữ_liệu_json, tên_model_đã_dùng)
        """
        enforced_sys_prompt = (
            (system_prompt + "\n\n") if system_prompt else ""
        ) + "CRITICAL INSTRUCTION: You MUST return ONLY a valid, raw JSON object. Do not include markdown formatting, backticks, comments, or python code."

        raw_text, model_used = await self.generate_text(
            prompt=prompt,
            system_prompt=enforced_sys_prompt,
            complexity=complexity,
            temperature=temperature,
            max_tokens=2048,
        )

        parsed_json = self.extract_json_from_text(raw_text)
        return parsed_json, model_used

    @staticmethod
    def extract_json_from_text(text: str) -> Dict[str, Any]:
        """Hàm bóc tách JSON an toàn từ text trả về của LLM (loại bỏ markdown block, backticks, python wrapper)"""
        text = text.strip()
        
        # 1. Thử parse trực tiếp nếu trả về JSON thuần
        try:
            return json.loads(text)
        except Exception:
            pass

        # 2. Bóc tách bằng Regular Expression khối ```json ... ``` hoặc ``` ... ```
        code_blocks = re.findall(r"```(?:json|python)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
        for block in code_blocks:
            block = block.strip()
            try:
                return json.loads(block)
            except Exception:
                pass
            # Tìm JSON bên trong block
            f_brace = block.find("{")
            l_brace = block.rfind("}")
            if f_brace != -1 and l_brace != -1 and l_brace > f_brace:
                try:
                    return json.loads(block[f_brace:l_brace + 1])
                except Exception:
                    pass

        # 3. Tìm cặp ngoặc { ... } lớn nhất trong toàn bộ text
        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            json_str = text[first_brace:last_brace + 1].strip()
            try:
                return json.loads(json_str)
            except Exception:
                # Thử fix các lỗi phổ biến (dấu phẩy thừa cuối mảng/object)
                try:
                    fixed = re.sub(r",\s*([\]}])", r"\1", json_str)
                    return json.loads(fixed)
                except Exception:
                    pass

        logger.warning(f"Không thể parse JSON từ phản hồi LLM: {text[:200]}...")
        raise ValueError(f"Dữ liệu trả về từ AI không đúng định dạng JSON hợp lệ.")


# Singleton Instance
model_router = DynamicModelRouter()
