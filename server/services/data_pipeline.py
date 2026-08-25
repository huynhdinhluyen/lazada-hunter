from typing import List, Tuple, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from loguru import logger

from core.models import Product, PriceHistory, ProductVariant
from core.schemas import ProductCreate
from services.embedding_service import embedding_service
from services.qdrant_store import qdrant_store
from config.settings import settings


class PipelineResult(tuple):
    """Kết quả xử lý pipeline tương thích ngược với tuple (new_count, updated_count, price_alerts)"""
    def __new__(cls, new_count: int, updated_count: int, price_alerts: List[Dict[str, Any]], products: Optional[List[Product]] = None):
        return super().__new__(cls, (new_count, updated_count, price_alerts))

    def __init__(self, new_count: int, updated_count: int, price_alerts: List[Dict[str, Any]], products: Optional[List[Product]] = None):
        self.new_count = new_count
        self.updated_count = updated_count
        self.price_alerts = price_alerts
        self.products = products or []


class DataPipelineService:
    """
    Dịch vụ xử lý dữ liệu cào:
    - Làm sạch & Validate dữ liệu
    - Chống trùng lặp (Deduplication)
    - Upsert vào PostgreSQL
    - Tự động ghi vết biến động giá vào bảng PriceHistory (Time-series)
    - Bắt các sự kiện biến động giá (Price Drops) để chuẩn bị bắn cảnh báo
    """
    
    @staticmethod
    async def process_scraped_products(
        session: AsyncSession, 
        products: List[ProductCreate]
    ) -> PipelineResult:
        """
        Lưu danh sách sản phẩm vào PostgreSQL.
        Trả về: PipelineResult (hỗ trợ unpack tuple 3 phần tử hoặc truy cập .products)
        """
        new_count = 0
        updated_count = 0
        price_alerts: List[Dict[str, Any]] = []
        saved_products: List[Product] = []

        for p_data in products:
            try:
                # 1. Tìm sản phẩm theo platform + platform_product_id
                query = select(Product).where(
                    and_(
                        Product.platform == p_data.platform,
                        Product.platform_product_id == p_data.platform_product_id
                    )
                )
                result = await session.execute(query)
                existing_product = result.scalar_one_or_none()

                if existing_product:
                    # 2. Sản phẩm đã tồn tại -> Kiểm tra biến động giá
                    old_price = existing_product.current_price
                    new_price = p_data.current_price

                    # Tránh bị đè giá 0đ nếu DOM cào thiếu
                    if new_price <= 0 and old_price > 0:
                        new_price = old_price

                    if old_price != new_price and new_price > 0:
                        # Ghi vết vào PriceHistory
                        history_entry = PriceHistory(
                            product_id=existing_product.id,
                            price=new_price,
                            original_price=p_data.original_price,
                            discount_percentage=p_data.discount_percentage,
                            rating_star=p_data.rating_star,
                            sold_count=p_data.historical_sold
                        )
                        session.add(history_entry)

                        # Tính % giảm giá nếu giá giảm thực tế
                        if old_price > new_price and old_price > 0:
                            drop_percent = round(((old_price - new_price) / old_price) * 100, 1)
                            if drop_percent >= settings.PRICE_DROP_ALERT_THRESHOLD_PERCENT:
                                price_alerts.append({
                                    "product_name": existing_product.name,
                                    "platform": existing_product.platform,
                                    "url": p_data.url or existing_product.url,
                                    "old_price": old_price,
                                    "new_price": new_price,
                                    "drop_percent": drop_percent,
                                    "image_url": p_data.image_url or existing_product.image_url,
                                    "shop_name": existing_product.shop_name
                                })
                                logger.info(
                                    f"🚨 [PRICE DROP] '{existing_product.name[:30]}...' giảm {drop_percent}% "
                                    f"({old_price:,.0f}đ -> {new_price:,.0f}đ)"
                                )

                    # Cập nhật thông tin mới nhất
                    existing_product.name = p_data.name
                    if new_price > 0:
                        existing_product.current_price = new_price
                    if p_data.url and "lazada.vn" in p_data.url:
                        existing_product.url = p_data.url
                    existing_product.original_price = p_data.original_price
                    existing_product.discount_percentage = p_data.discount_percentage
                    existing_product.rating_star = p_data.rating_star
                    existing_product.rating_count = p_data.rating_count
                    existing_product.historical_sold = p_data.historical_sold
                    existing_product.stock = p_data.stock
                    if p_data.image_url:
                        existing_product.image_url = p_data.image_url
                    if p_data.shop_name:
                        existing_product.shop_name = p_data.shop_name
                    if p_data.raw_data:
                        existing_product.raw_data = p_data.raw_data

                    updated_count += 1
                    saved_products.append(existing_product)

                    # Sync Qdrant: Cập nhật payload mới nhất (giá, lượt bán, rating)
                    try:
                        upd_vec = await embedding_service.get_embedding(f"{existing_product.name} {existing_product.brand or ''}")
                        qdrant_store.upsert_product(
                            product_id=existing_product.id,
                            vector=upd_vec,
                            payload={
                                "name": existing_product.name,
                                "platform": existing_product.platform,
                                "current_price": existing_product.current_price or 0,
                                "original_price": existing_product.original_price or 0,
                                "discount_percentage": existing_product.discount_percentage or 0,
                                "rating_star": existing_product.rating_star or 0,
                                "historical_sold": existing_product.historical_sold or 0,
                                "shop_name": existing_product.shop_name or "",
                                "brand": existing_product.brand or "",
                                "category": existing_product.category or "",
                                "url": existing_product.url or "",
                                "image_url": existing_product.image_url or "",
                            }
                        )
                    except Exception as eq:
                        logger.debug(f"Qdrant sync (update) bỏ qua: {eq}")

                else:
                    # 3. Sản phẩm mới -> Tạo Product mới kèm Vector Embedding
                    prod_vec = await embedding_service.get_embedding(f"{p_data.name} {p_data.brand or ''}")
                    new_product = Product(
                        platform=p_data.platform,
                        platform_product_id=p_data.platform_product_id,
                        sku=p_data.sku,
                        name=p_data.name,
                        url=p_data.url,
                        image_url=p_data.image_url,
                        brand=p_data.brand,
                        category=p_data.category,
                        current_price=p_data.current_price,
                        original_price=p_data.original_price,
                        discount_percentage=p_data.discount_percentage,
                        rating_star=p_data.rating_star,
                        rating_count=p_data.rating_count,
                        historical_sold=p_data.historical_sold,
                        stock=p_data.stock,
                        shop_id=p_data.shop_id,
                        shop_name=p_data.shop_name,
                        shop_location=p_data.shop_location,
                        is_official_shop=p_data.is_official_shop,
                        embedding=prod_vec,
                        raw_data=p_data.raw_data
                    )
                    session.add(new_product)
                    await session.flush()  # Để lấy new_product.id

                    # Thêm bản ghi đầu tiên vào lịch sử giá
                    first_history = PriceHistory(
                        product_id=new_product.id,
                        price=p_data.current_price,
                        original_price=p_data.original_price,
                        discount_percentage=p_data.discount_percentage,
                        rating_star=p_data.rating_star,
                        sold_count=p_data.historical_sold
                    )
                    session.add(first_history)

                    # Lưu các biến thể (variants) nếu có
                    if p_data.variants:
                        for v in p_data.variants:
                            variant_obj = ProductVariant(
                                product_id=new_product.id,
                                variant_id=v.variant_id,
                                name=v.name,
                                price=v.price,
                                original_price=v.original_price,
                                stock=v.stock,
                                image_url=v.image_url
                            )
                            session.add(variant_obj)

                    new_count += 1
                    saved_products.append(new_product)

                    # Sync Qdrant: Push vector + payload lên Qdrant Cloud
                    try:
                        qdrant_store.upsert_product(
                            product_id=new_product.id,
                            vector=prod_vec,
                            payload={
                                "name": p_data.name,
                                "platform": p_data.platform,
                                "current_price": p_data.current_price or 0,
                                "original_price": p_data.original_price or 0,
                                "discount_percentage": p_data.discount_percentage or 0,
                                "rating_star": p_data.rating_star or 0,
                                "historical_sold": p_data.historical_sold or 0,
                                "shop_name": p_data.shop_name or "",
                                "brand": p_data.brand or "",
                                "category": p_data.category or "",
                                "url": p_data.url or "",
                                "image_url": p_data.image_url or "",
                            }
                        )
                    except Exception as eq:
                        logger.debug(f"Qdrant sync (new) bỏ qua: {eq}")

            except Exception as e:
                logger.error(f"Lỗi khi xử lý sản phẩm {p_data.name[:30]}: {e}")
                continue

        await session.commit()
        logger.info(f"✅ Pipeline hoàn tất: {new_count} mới, {updated_count} cập nhật, {len(price_alerts)} cảnh báo giá.")
        return PipelineResult(new_count, updated_count, price_alerts, saved_products)


pipeline_service = DataPipelineService()
