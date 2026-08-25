from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, delete
from pydantic import BaseModel
from loguru import logger

import asyncio
from core.database import get_db
from core.models import UserWatchlist, Product
from services.telegram_service import telegram_service

router = APIRouter(prefix="/api/v1/watchlist", tags=["Watchlist"])


class WatchlistAddRequest(BaseModel):
    user_id: str  # Google email or sub ID
    product_id: int
    note: Optional[str] = None


class WatchlistItemResponse(BaseModel):
    id: int
    user_id: str
    product_id: int
    note: Optional[str] = None
    created_at: str
    product: Optional[dict] = None

    class Config:
        from_attributes = True


@router.get("")
async def get_watchlist(
    user_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Lấy danh sách sản phẩm theo dõi của người dùng"""
    try:
        result = await db.execute(
            select(UserWatchlist)
            .where(UserWatchlist.user_id == user_id)
            .order_by(UserWatchlist.created_at.desc())
        )
        items = result.scalars().all()

        product_ids = [item.product_id for item in items]
        products_result = await db.execute(
            select(Product).where(Product.id.in_(product_ids))
        )
        products_map = {p.id: p for p in products_result.scalars().all()}

        response = []
        for item in items:
            prod = products_map.get(item.product_id)
            prod_dict = None
            if prod:
                prod_dict = {
                    "id": prod.id,
                    "name": prod.name,
                    "url": prod.url,
                    "image_url": prod.image_url,
                    "current_price": prod.current_price,
                    "original_price": prod.original_price,
                    "discount_percentage": prod.discount_percentage,
                    "rating_star": prod.rating_star,
                    "rating_count": prod.rating_count,
                    "historical_sold": prod.historical_sold,
                    "shop_name": prod.shop_name,
                    "brand": prod.brand,
                    "platform": prod.platform,
                    "platform_product_id": prod.platform_product_id,
                }
            response.append({
                "id": item.id,
                "user_id": item.user_id,
                "product_id": item.product_id,
                "note": item.note,
                "created_at": item.created_at.isoformat() if item.created_at else None,
                "product": prod_dict,
            })

        return {"items": response, "total": len(response)}

    except Exception as e:
        logger.error(f"Lỗi khi lấy watchlist: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", status_code=201)
async def add_to_watchlist(
    request: WatchlistAddRequest,
    db: AsyncSession = Depends(get_db)
):
    """Thêm sản phẩm vào danh sách theo dõi"""
    try:
        # Kiểm tra sản phẩm tồn tại
        prod_result = await db.execute(select(Product).where(Product.id == request.product_id))
        product = prod_result.scalar_one_or_none()
        if not product:
            raise HTTPException(status_code=404, detail="Sản phẩm không tồn tại")

        # Kiểm tra đã thêm chưa
        existing = await db.execute(
            select(UserWatchlist).where(
                and_(
                    UserWatchlist.user_id == request.user_id,
                    UserWatchlist.product_id == request.product_id
                )
            )
        )
        if existing.scalar_one_or_none():
            return {"status": "already_exists", "message": "Sản phẩm đã có trong danh sách theo dõi"}

        watchlist_item = UserWatchlist(
            user_id=request.user_id,
            product_id=request.product_id,
            note=request.note
        )
        db.add(watchlist_item)
        await db.commit()
        await db.refresh(watchlist_item)

        logger.info(f"✅ [WATCHLIST] User '{request.user_id}' đã thêm sản phẩm #{request.product_id}")

        # Tự động gửi thông báo đến Telegram Bot
        try:
            prod_dict = {
                "id": product.id,
                "name": product.name,
                "url": product.url,
                "image_url": product.image_url,
                "current_price": product.current_price,
                "original_price": product.original_price,
                "discount_percentage": product.discount_percentage,
                "rating_star": product.rating_star,
                "rating_count": product.rating_count,
                "historical_sold": product.historical_sold,
                "shop_name": product.shop_name,
                "ai_analysis": product.ai_analysis,
            }
            asyncio.create_task(telegram_service.send_watchlist_saved_alert(prod_dict, request.user_id))
        except Exception as tg_err:
            logger.warning(f"⚠️ [TELEGRAM] Không thể bắn thông báo watchlist: {tg_err}")

        return {
            "status": "added",
            "message": "Đã thêm vào danh sách theo dõi và thông báo qua Telegram",
            "item_id": watchlist_item.id,
            "product_id": request.product_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Lỗi khi thêm vào watchlist: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{product_id}")
async def remove_from_watchlist(
    product_id: int,
    user_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Xóa sản phẩm khỏi danh sách theo dõi"""
    try:
        result = await db.execute(
            delete(UserWatchlist).where(
                and_(
                    UserWatchlist.user_id == user_id,
                    UserWatchlist.product_id == product_id
                )
            )
        )
        await db.commit()

        if result.rowcount == 0:
            return {"status": "not_found", "message": "Sản phẩm không có trong danh sách theo dõi"}

        logger.info(f"🗑️ [WATCHLIST] User '{user_id}' đã xóa sản phẩm #{product_id}")
        return {"status": "removed", "message": "Đã xóa khỏi danh sách theo dõi"}

    except Exception as e:
        logger.error(f"Lỗi khi xóa khỏi watchlist: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/check/{product_id}")
async def check_in_watchlist(
    product_id: int,
    user_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Kiểm tra sản phẩm có trong watchlist không"""
    result = await db.execute(
        select(UserWatchlist).where(
            and_(
                UserWatchlist.user_id == user_id,
                UserWatchlist.product_id == product_id
            )
        )
    )
    item = result.scalar_one_or_none()
    return {"is_saved": item is not None}


@router.get("/tracker/status")
async def get_watchlist_tracker_status():
    """Lấy thông tin trạng thái hoạt động của Cron Job theo dõi giá Watchlist"""
    from services.watchlist_scheduler import watchlist_scheduler
    return watchlist_scheduler.get_status()


@router.post("/tracker/trigger")
async def trigger_watchlist_price_check():
    """Kích hoạt quét cập nhật giá Watchlist thủ công ngay lập tức"""
    from services.watchlist_scheduler import watchlist_scheduler
    import asyncio
    asyncio.create_task(watchlist_scheduler.check_watchlist_prices())
    return {
        "status": "triggered",
        "message": "Đã kích hoạt quét cập nhật giá Watchlist và gửi cảnh báo Telegram ngầm."
    }
