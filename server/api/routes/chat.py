from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from loguru import logger

from core.database import get_db
from core.models import ChatSession, ChatMessage
from core.schemas import ChatRequest, ChatResponse
from ai_engine.shopping_assistant import shopping_assistant

router = APIRouter(prefix="/chat", tags=["AI Shopping Assistant"])


@router.post("", response_model=ChatResponse, summary="Gửi tin nhắn trò chuyện với AI Trợ lý Mua sắm")
async def send_chat_message(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Xử lý câu hỏi mua sắm từ người dùng qua Router 3 Tầng:
    1. Fast-Path Guardrails (Chặn vi phạm & Chitchat)
    2. Semantic Cache (Trả về kết quả ngay lập tức nếu trùng ý định)
    3. Gemini Structured Outputs (Cào live và tư vấn chuyên sâu)
    """
    try:
        response = await shopping_assistant.chat(db, request)
        return response
    except Exception as e:
        logger.error(f"Lỗi khi xử lý chat message: {e}")
        raise HTTPException(status_code=500, detail=f"Lỗi hệ thống AI Assistant: {str(e)}")


@router.get("/history/{session_id}", summary="Lấy lịch sử hội thoại của một phiên chat")
async def get_chat_history(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
    )
    result = await db.execute(stmt)
    messages = result.scalars().all()
    
    return [
        {
            "id": m.id,
            "session_id": m.session_id,
            "role": m.role,
            "content": m.content,
            "intent": m.intent,
            "metadata": m.metadata_json,
            "created_at": m.created_at
        }
        for m in messages
    ]
