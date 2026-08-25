from typing import Dict, Any, List, Optional
from core.models import Product, PriceHistory


def serialize_product(p: Product) -> Dict[str, Any]:
    """
    Hàm chuẩn hóa đối tượng Product ORM sang Dictionary JSON an toàn (DRY):
    - Tái sử dụng đồng nhất ở API Products, AI Assistant và Cache Serialization.
    """
    if not p:
        return {}
    return {
        "id": p.id,
        "platform": p.platform,
        "platform_product_id": p.platform_product_id,
        "sku": p.sku,
        "name": p.name,
        "url": p.url,
        "image_url": p.image_url,
        "brand": p.brand,
        "category": p.category,
        "current_price": p.current_price,
        "original_price": p.original_price,
        "discount_percentage": p.discount_percentage,
        "rating_star": p.rating_star,
        "rating_count": p.rating_count,
        "historical_sold": p.historical_sold,
        "stock": p.stock,
        "shop_id": p.shop_id,
        "shop_name": p.shop_name,
        "shop_location": p.shop_location,
        "is_official_shop": p.is_official_shop,
        "ai_analysis": p.ai_analysis,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


def serialize_price_history(h: PriceHistory) -> Dict[str, Any]:
    """Chuẩn hóa đối tượng PriceHistory sang Dictionary"""
    if not h:
        return {}
    return {
        "id": h.id,
        "product_id": h.product_id,
        "price": h.price,
        "original_price": h.original_price,
        "discount_percentage": h.discount_percentage,
        "rating_star": h.rating_star,
        "sold_count": h.sold_count,
        "recorded_at": h.recorded_at.isoformat() if h.recorded_at else None,
    }
