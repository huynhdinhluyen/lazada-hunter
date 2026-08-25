import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from loguru import logger

from config.settings import settings

# Base ORM model class
Base = declarative_base()

# Async Engine for PostgreSQL
engine = create_async_engine(
    settings.async_db_url,
    echo=settings.DEBUG,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True
)

# Async Session Factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


def ensure_database_exists():
    """Tự động kiểm tra và tạo database PostgreSQL nếu chưa tồn tại"""
    try:
        conn = psycopg2.connect(
            host=settings.POSTGRES_HOST,
            port=settings.POSTGRES_PORT,
            user=settings.POSTGRES_USER,
            password=settings.POSTGRES_PASSWORD.get_secret_value() if settings.POSTGRES_PASSWORD else "",
            dbname="postgres",
            connect_timeout=5
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        cur.execute(
            "SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s",
            (settings.POSTGRES_DB,)
        )
        exists = cur.fetchone()
        if not exists:
            cur.execute(f'CREATE DATABASE "{settings.POSTGRES_DB}"')
            logger.info(f"Database '{settings.POSTGRES_DB}' đã được tạo thành công trên PostgreSQL.")
        else:
            logger.debug(f"Database '{settings.POSTGRES_DB}' đã tồn tại.")
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Lỗi khi kiểm tra/tạo database PostgreSQL: {e}")
        raise


async def init_db():
    """Khởi tạo toàn bộ bảng trong PostgreSQL & Qdrant Collection"""
    ensure_database_exists()
    
    # 1. Tạo Schema và các bảng PostgreSQL
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Đảm bảo cột ai_analysis tồn tại trên bảng products cũ
        from sqlalchemy import text
        try:
            await conn.execute(text("ALTER TABLE products ADD COLUMN IF NOT EXISTS ai_analysis JSON;"))
        except Exception:
            pass
    logger.info("✅ Đã đồng bộ toàn bộ Schema & Tables vào PostgreSQL.")

    # 2. Khởi tạo Qdrant Collection (nếu cấu hình sẵn sàng)
    try:
        from services.qdrant_store import qdrant_store
        await qdrant_store.ensure_collection()
    except Exception as e:
        logger.debug(f"ℹ️ Qdrant collection init bỏ qua: {e}")


async def get_db():
    """Async Generator Dependency cho FastAPI / Workers"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
