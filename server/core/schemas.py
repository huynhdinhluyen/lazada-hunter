import re
import enum
from datetime import datetime
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field, field_validator, ConfigDict


def parse_price(value: Any) -> float:
    """Chuẩn hóa giá tiền Việt Nam từ nhiều định dạng khác nhau về float (VNĐ)"""
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        val = float(value)
        if val > 10_000_000_000:  # Shopee micro-price 100_000 scale
            return val / 100_000
        return val
    
    text = str(value).strip().lower()
    if not text or text == "n/a":
        return 0.0
    
    text = re.sub(r"[₫đvnđvndrmb\$\s]", "", text)
    
    if "k" in text:
        num_part = re.sub(r"[^\d\.]", "", text.replace("k", ""))
        try:
            return float(num_part) * 1000
        except ValueError:
            return 0.0
    if "tr" in text or "m" in text:
        num_part = re.sub(r"[^\d\.]", "", text.replace("tr", "").replace("m", ""))
        try:
            return float(num_part) * 1_000_000
        except ValueError:
            return 0.0
            
    if "." in text and "," in text:
        if text.rfind(".") > text.rfind(","):
            text = text.replace(",", "")
        else:
            text = text.replace(".", "").replace(",", ".")
    elif "." in text:
        parts = text.split(".")
        if len(parts) > 1 and len(parts[-1]) == 3:
            text = "".join(parts)
    elif "," in text:
        parts = text.split(",")
        if len(parts) > 1 and len(parts[-1]) == 3:
            text = "".join(parts)
        else:
            text = text.replace(",", ".")
            
    clean_num = re.sub(r"[^\d\.]", "", text)
    try:
        return float(clean_num) if clean_num else 0.0
    except ValueError:
        return 0.0


def parse_sold_count(value: Any) -> int:
    """Chuẩn hóa số lượng đã bán từ chuỗi (VD: '1,2k đã bán', '15k+ đã bán', 1234)"""
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    
    text = str(value).strip().lower()
    text = re.sub(r"[đãbánsolds\+]", "", text).strip()
    
    if "k" in text:
        text = text.replace("k", "").replace(",", ".")
        try:
            return int(float(re.sub(r"[^\d\.]", "", text)) * 1000)
        except ValueError:
            return 0
    if "tr" in text or "m" in text:
        text = text.replace("tr", "").replace("m", "").replace(",", ".")
        try:
            return int(float(re.sub(r"[^\d\.]", "", text)) * 1_000_000)
        except ValueError:
            return 0
            
    clean_num = re.sub(r"[^\d]", "", text)
    return int(clean_num) if clean_num else 0


# ==========================================
# PRODUCT & AI ANALYSIS SCHEMAS
# ==========================================

class ProductAIAnalysisResult(BaseModel):
    """
    Schema JSON Chuẩn hóa Đầu ra của AI Phân Tích & Định Giá Sản Phẩm (LLM Engine):
    - Dịch thuật/chuẩn hóa nội dung
    - Phân tích ưu/nhược điểm từ đánh giá của khách hàng (Reviews)
    - Tóm tắt chất lượng sản phẩm
    - Gợi ý mức giá cạnh tranh
    """
    normalized_name: str = Field(description="Tên sản phẩm chuẩn hóa, dịch thuật gọn gàng, loại bỏ từ khóa spam")
    category_standardized: str = Field(description="Ngành hàng chuẩn hóa (vd: Chuột máy tính, Tai nghe không dây...)")
    specs_summary: List[str] = Field(default_factory=list, description="Tóm tắt thông số kỹ thuật cốt lõi (tối đa 4-6 gạch đầu dòng)")
    quality_summary: str = Field(description="Tóm tắt tổng quan về chất lượng sản phẩm và mức độ tin cậy")
    pros: List[str] = Field(default_factory=list, description="Danh sách ưu điểm nổi bật bóc tách từ đánh giá của khách hàng và thông số")
    cons: List[str] = Field(default_factory=list, description="Danh sách nhược điểm hoặc điểm cần lưu ý từ phản hồi của người mua")
    sentiment_score: float = Field(default=8.0, description="Điểm đánh giá cảm xúc / mức độ hài lòng khách hàng trên thang điểm 10 (vd: 8.5)")
    competitive_price_analysis: str = Field(description="Phân tích định giá thị trường và mức độ cạnh tranh")
    recommended_price_min: float = Field(default=0.0, description="Mức giá cạnh tranh tối thiểu khuyến nghị (VNĐ)")
    recommended_price_max: float = Field(default=0.0, description="Mức giá cạnh tranh tối đa khuyến nghị (VNĐ)")
    recommended_price_optimal: float = Field(default=0.0, description="Mức giá tối ưu mang lại thanh khoản tốt nhất (VNĐ)")
    target_audience: str = Field(description="Đối tượng khách hàng hoặc phân khúc sử dụng phù hợp nhất")
    buying_verdict: str = Field(description="Kết luận & lời khuyên quyết định mua hàng (Nên mua / Cân nhắc / Đáng tiền)")
    model_used: Optional[str] = Field(default="NVIDIA NIM (Llama 3.1)", description="Model AI đã thực hiện phân tích")
    analyzed_at: Optional[str] = Field(default_factory=lambda: datetime.utcnow().isoformat(), description="Thời điểm phân tích ISO format")


class ProductVariantBase(BaseModel):
    variant_id: str
    name: str
    price: float
    original_price: Optional[float] = None
    stock: Optional[int] = None
    image_url: Optional[str] = None


class ProductVariantCreate(ProductVariantBase):
    pass


class ProductVariantResponse(ProductVariantBase):
    id: int
    product_id: int

    model_config = ConfigDict(from_attributes=True)


class ProductBase(BaseModel):
    platform: str
    platform_product_id: str
    sku: Optional[str] = None
    name: str
    url: str
    image_url: Optional[str] = None
    brand: Optional[str] = None
    category: Optional[str] = None
    
    current_price: float
    original_price: Optional[float] = None
    discount_percentage: Optional[float] = None
    
    rating_star: Optional[float] = 0.0
    rating_count: Optional[int] = 0
    historical_sold: Optional[int] = 0
    stock: Optional[int] = None
    
    shop_id: Optional[str] = None
    shop_name: Optional[str] = None
    shop_location: Optional[str] = None
    is_official_shop: bool = False
    ai_analysis: Optional[ProductAIAnalysisResult] = None
    raw_data: Optional[Dict[str, Any]] = None

    @field_validator("url", mode="before")
    @classmethod
    def validate_product_url(cls, v):
        if not v:
            return "https://www.lazada.vn"
        v = str(v).strip()
        # Correct misspelled domain typos like laazada.vn -> lazada.vn
        v = re.sub(r"https?://(www\.)?la+zada\.[a-z\.]+", "https://www.lazada.vn", v)
        if v.startswith("//"):
            v = "https:" + v
        elif v.startswith("/"):
            v = f"https://www.lazada.vn{v}"
        elif not v.startswith("http"):
            v = f"https://www.lazada.vn/products/{v}"
        return v

    @field_validator("image_url", mode="before")
    @classmethod
    def validate_image_url(cls, v):
        if isinstance(v, list) and len(v) > 0:
            v = v[0]
        if isinstance(v, dict):
            v = v.get("url") or v.get("src") or ""
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("//"):
                v = "https:" + v
            return v if v else None
        return None


class ProductCreate(ProductBase):
    variants: Optional[List[ProductVariantCreate]] = []

    @field_validator("current_price", mode="before")
    @classmethod
    def validate_current_price(cls, v):
        return parse_price(v)

    @field_validator("original_price", mode="before")
    @classmethod
    def validate_original_price(cls, v):
        return parse_price(v) if v is not None else None

    @field_validator("historical_sold", mode="before")
    @classmethod
    def validate_sold(cls, v):
        return parse_sold_count(v) if v is not None else 0


class PriceHistoryResponse(BaseModel):
    id: int
    product_id: int
    variant_id: Optional[int] = None
    price: float
    original_price: Optional[float] = None
    discount_percentage: Optional[float] = None
    rating_star: Optional[float] = None
    sold_count: Optional[int] = None
    recorded_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProductResponse(ProductBase):
    id: int
    created_at: datetime
    updated_at: datetime
    variants: List[ProductVariantResponse] = []

    model_config = ConfigDict(from_attributes=True)


class ProductDetailResponse(ProductResponse):
    price_history: List[PriceHistoryResponse] = []

    model_config = ConfigDict(from_attributes=True)


class ScrapeJobCreate(BaseModel):
    keyword_or_url: str
    platform: str = "lazada"
    input_mode: str = "keyword"  # "keyword", "single_url", "batch_urls"
    urls: Optional[List[str]] = []
    max_pages: int = 1
    limit_per_platform: int = 20
    auto_analyze: bool = False
    auto_notify_telegram: bool = False


class ScrapeJobResponse(BaseModel):
    id: int
    keyword_or_url: str
    platform: str
    status: str
    total_items_found: int
    total_items_saved: int
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# AI CHAT & ASSISTANT SCHEMAS
# ==========================================

class ChatIntentEnum(str, enum.Enum):
    RECOMMENDATION = "recommendation"
    COMPARISON = "comparison"
    CLARIFICATION_NEEDED = "clarification_needed"
    UNREALISTIC_CONSTRAINTS = "unrealistic_constraints"
    CHITCHAT_OUT_OF_SCOPE = "chitchat_out_of_scope"
    SAFETY_GUARD = "safety_guard"


class ExtractedEntities(BaseModel):
    product_type: Optional[str] = None
    brand: Optional[str] = None
    budget_max: Optional[float] = None
    budget_min: Optional[float] = None
    features: List[str] = []
    products_to_compare: List[str] = []
    is_realistic: bool = True
    unrealistic_reason: Optional[str] = None
    missing_criteria: List[str] = []


class IntentClassificationResult(BaseModel):
    intent: ChatIntentEnum
    confidence: float = 1.0
    search_keyword: Optional[str] = None
    entities: ExtractedEntities = Field(default_factory=ExtractedEntities)
    reasoning: Optional[str] = None


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    force_refresh: bool = False
    model: Optional[str] = "meta/llama-3.1-8b-instruct"


class ChatResponse(BaseModel):
    session_id: str
    intent: str
    message: str
    cached: bool = False
    recommended_products: List[ProductResponse] = []
    comparison_data: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
