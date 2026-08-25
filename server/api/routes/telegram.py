from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from loguru import logger

from services.telegram_service import telegram_service

router = APIRouter(prefix="/telegram", tags=["Telegram Notifications"])


class TelegramChatIdUpdate(BaseModel):
    chat_id: str


class TelegramSendMessageRequest(BaseModel):
    text: str
    chat_id: Optional[str] = None


@router.get("/status", summary="Lấy trạng thái kết nối Telegram Bot")
async def get_telegram_status():
    """Kiểm tra tính hợp lệ của Telegram Bot và thông tin cấu hình"""
    return await telegram_service.get_bot_info()


@router.post("/test", summary="Gửi tin nhắn thông báo mẫu qua Telegram")
async def send_test_telegram(request: Optional[TelegramSendMessageRequest] = None):
    """Gửi một thông báo test để kiểm tra bot có gửi được tin nhắn tới user không"""
    target_chat_id = request.chat_id if request else None
    result = await telegram_service.send_test_notification(chat_id=target_chat_id)
    if not result.get("success"):
        raise HTTPException(
            status_code=400,
            detail=result.get("error", "Không thể gửi tin nhắn Telegram")
        )
    return {
        "status": "success",
        "message": "Đã gửi thông báo kiểm tra tới Telegram thành công!",
        "details": result
    }


@router.post("/chat-id", summary="Cập nhật hoặc tự động nhận diện Chat ID")
async def update_chat_id(request: Optional[TelegramChatIdUpdate] = None):
    """Cập nhật Chat ID thủ công hoặc tự động tìm từ lệnh /start gần nhất"""
    if request and request.chat_id.strip():
        telegram_service.set_chat_id(request.chat_id.strip())
        return {
            "status": "success",
            "message": f"Đã cập nhật Chat ID: {request.chat_id.strip()}",
            "chat_id": request.chat_id.strip()
        }
    
    # Auto discover
    discovered = await telegram_service.auto_discover_chat_id()
    if not discovered:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy Chat ID mới. Vui lòng mở Bot @lazamerce_alert_bot trên Telegram và bấm /start trước."
        )
    return {
        "status": "success",
        "message": f"Đã tự động nhận diện Chat ID: {discovered}",
        "chat_id": discovered
    }


@router.post("/broadcast-product/{product_id}", summary="Bắn bản tin tóm tắt sản phẩm (kèm ảnh/giá/link/AI) vào Telegram")
async def broadcast_product_to_telegram(
    product_id: int,
    chat_id: Optional[str] = None
):
    """Bắn bản tin sản phẩm hoàn chỉnh cùng hình ảnh và phân tích AI vào Telegram"""
    from core.database import AsyncSessionLocal
    from core.models import Product
    from sqlalchemy import select
    from core.serializers import serialize_product

    async with AsyncSessionLocal() as session:
        stmt = select(Product).where(Product.id == product_id)
        product = (await session.execute(stmt)).scalar_one_or_none()
        if not product:
            raise HTTPException(status_code=404, detail="Không tìm thấy sản phẩm")

        prod_dict = serialize_product(product)
        ai_data = product.ai_analysis

        success = await telegram_service.send_product_bulletin(
            product=prod_dict,
            ai_data=ai_data,
            chat_id=chat_id
        )

        if not success:
            raise HTTPException(status_code=400, detail="Không thể gửi bản tin sản phẩm tới Telegram. Vui lòng kiểm tra lại Bot Token hoặc Chat ID.")

        return {
            "status": "success",
            "message": f"Đã gửi bản tin sản phẩm '{product.name[:35]}...' vào nhóm Telegram thành công!",
            "product_id": product_id
        }

