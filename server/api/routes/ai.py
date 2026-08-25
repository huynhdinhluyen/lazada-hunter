from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from loguru import logger

from core.database import get_db, AsyncSessionLocal
from core.models import Product
from core.schemas import ProductAIAnalysisResult
from core.serializers import serialize_product
from ai_engine.product_analyzer import product_analyzer
from services.telegram_service import telegram_service

router = APIRouter(prefix="/ai", tags=["AI Product Intelligence"])


class BatchAnalyzeRequest(BaseModel):
    product_ids: List[int]
    auto_notify_telegram: bool = False


@router.post("/analyze-product/{product_id}", response_model=ProductAIAnalysisResult, summary="Phân tích AI thông minh cho một sản phẩm")
async def analyze_single_product(
    product_id: int,
    auto_notify_telegram: bool = Query(False, description="Tự động bắn bản tin lên Telegram sau khi phân tích"),
    db: AsyncSession = Depends(get_db)
):
    """
    Kích hoạt LLM (NVIDIA NIM / Gemini) phân tích chuyên sâu cho sản phẩm:
    - Dịch thuật/chuẩn hóa nội dung
    - Phân tích ưu/nhược điểm từ đánh giá của khách hàng (Reviews)
    - Tóm tắt chất lượng sản phẩm
    - Gợi ý định giá cạnh tranh chuẩn JSON
    - Lưu kết quả vào PostgreSQL
    """
    stmt = select(Product).where(Product.id == product_id)
    result = await db.execute(stmt)
    product = result.scalar_one_or_none()

    if not product:
        raise HTTPException(status_code=404, detail="Không tìm thấy sản phẩm")

    prod_dict = serialize_product(product)
    
    # Thực hiện phân tích qua AI Engine
    ai_result = await product_analyzer.analyze_product(prod_dict)
    
    # Lưu kết quả phân tích có cấu trúc vào Database
    product.ai_analysis = ai_result.model_dump()
    await db.commit()
    await db.refresh(product)

    # Tự động gửi Telegram nếu được yêu cầu
    if auto_notify_telegram:
        try:
            await telegram_service.send_product_bulletin(
                product=prod_dict,
                ai_data=product.ai_analysis
            )
        except Exception as tg_err:
            logger.warning(f"Lỗi gửi Telegram sau khi phân tích AI: {tg_err}")

    return ai_result


@router.post("/batch-analyze", summary="Phân tích AI hàng loạt cho danh sách sản phẩm")
async def batch_analyze_products(
    request: BatchAnalyzeRequest,
    db: AsyncSession = Depends(get_db)
):
    """Kích hoạt phân tích AI cho nhiều sản phẩm cùng lúc"""
    if not request.product_ids:
        raise HTTPException(status_code=400, detail="Danh sách product_ids không được rỗng")

    analyzed_count = 0
    errors = []

    for pid in request.product_ids:
        try:
            stmt = select(Product).where(Product.id == pid)
            product = (await db.execute(stmt)).scalar_one_or_none()
            if not product:
                continue

            prod_dict = serialize_product(product)
            ai_res = await product_analyzer.analyze_product(prod_dict)
            product.ai_analysis = ai_res.model_dump()
            await db.commit()
            analyzed_count += 1

            if request.auto_notify_telegram:
                await telegram_service.send_product_bulletin(
                    product=prod_dict,
                    ai_data=product.ai_analysis
                )
        except Exception as e:
            logger.error(f"Lỗi phân tích AI cho sản phẩm #{pid}: {e}")
            errors.append({"product_id": pid, "error": str(e)})

    return {
        "status": "success",
        "total_requested": len(request.product_ids),
        "total_analyzed": analyzed_count,
        "errors": errors
    }
