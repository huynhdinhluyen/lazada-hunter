import enum
from datetime import datetime
from typing import List, Optional
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Text, DateTime, ForeignKey, 
    UniqueConstraint, Index, Enum, JSON
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from core.database import Base


class Platform(str, enum.Enum):
    SHOPEE = "shopee"
    LAZADA = "lazada"
    TIKTOK = "tiktok"
    TAOBAO = "taobao"


class Product(Base):
    """
    Bảng Sản Phẩm Cốt Lõi: Lưu trữ danh mục sản phẩm từ các sàn TMĐT.
    Bổ sung trường embedding phục vụ Semantic Vector Search.
    """
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    platform = Column(String(32), nullable=False, index=True)
    platform_product_id = Column(String(128), nullable=False, index=True)
    sku = Column(String(128), nullable=True, index=True)
    name = Column(String(512), nullable=False, index=True)
    url = Column(Text, nullable=False)
    image_url = Column(Text, nullable=True)
    brand = Column(String(128), nullable=True)
    category = Column(String(256), nullable=True)
    
    current_price = Column(Float, nullable=False, default=0.0)
    original_price = Column(Float, nullable=True)
    discount_percentage = Column(Float, nullable=True)
    
    rating_star = Column(Float, nullable=True, default=0.0)
    rating_count = Column(Integer, nullable=True, default=0)
    historical_sold = Column(Integer, nullable=True, default=0)
    stock = Column(Integer, nullable=True)
    
    shop_id = Column(String(64), nullable=True, index=True)
    shop_name = Column(String(256), nullable=True)
    shop_location = Column(String(256), nullable=True)
    is_official_shop = Column(Boolean, default=False)
    
    # Vector Embedding, AI Analysis & Metadata
    embedding = Column(JSON, nullable=True)
    ai_analysis = Column(JSON, nullable=True)
    raw_data = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Quan hệ với lazy='selectin' hỗ trợ AsyncIO
    variants = relationship("ProductVariant", back_populates="product", cascade="all, delete-orphan", lazy="selectin")
    price_history = relationship("PriceHistory", back_populates="product", cascade="all, delete-orphan", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("platform", "platform_product_id", name="uq_platform_product_id"),
        Index("idx_platform_price", "platform", "current_price"),
    )


class ProductVariant(Base):
    __tablename__ = "product_variants"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    variant_id = Column(String(128), nullable=False)
    name = Column(String(256), nullable=False)
    price = Column(Float, nullable=False)
    original_price = Column(Float, nullable=True)
    stock = Column(Integer, nullable=True)
    image_url = Column(Text, nullable=True)

    product = relationship("Product", back_populates="variants")


class PriceHistory(Base):
    __tablename__ = "price_history"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    variant_id = Column(Integer, ForeignKey("product_variants.id", ondelete="SET NULL"), nullable=True)
    price = Column(Float, nullable=False)
    original_price = Column(Float, nullable=True)
    discount_percentage = Column(Float, nullable=True)
    rating_star = Column(Float, nullable=True)
    sold_count = Column(Integer, nullable=True)
    recorded_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    product = relationship("Product", back_populates="price_history")

    __table_args__ = (
        Index("idx_product_record_time", "product_id", "recorded_at"),
    )


class SystemConfig(Base):
    __tablename__ = "system_configs"

    id = Column(Integer, primary_key=True)
    key = Column(String(128), unique=True, nullable=False, index=True)
    value = Column(Text, nullable=True)
    description = Column(String(256), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(String(64), primary_key=True, index=True)
    user_id = Column(String(64), nullable=True, index=True)
    title = Column(String(256), nullable=True)
    context_data = Column(JSON, nullable=True, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan", order_by="ChatMessage.id")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(64), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(32), nullable=False)  # 'user', 'assistant', 'system'
    content = Column(Text, nullable=False)
    intent = Column(String(64), nullable=True)
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("ChatSession", back_populates="messages")


class UserWatchlist(Base):
    """
    Bảng Danh Sách Sản Phẩm Theo Dõi (Watchlist) của người dùng:
    - Được phân biệt theo user_id (email từ Google OAuth)
    - Lưu toàn bộ thông tin sản phẩm (snapshot) tại thời điểm thêm vào
    - Hỗ trợ theo dõi biến động giá cá nhân
    """
    __tablename__ = "user_watchlist"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(256), nullable=False, index=True)  # Google email/sub
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    note = Column(String(512), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    product = relationship("Product")

    __table_args__ = (
        UniqueConstraint("user_id", "product_id", name="uq_user_product_watchlist"),
        Index("idx_user_watchlist", "user_id", "created_at"),
    )

