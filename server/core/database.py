import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from loguru import logger

from config.settings import settings

# Base ORM model class
Base = declarative_base()

import ssl
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse


def _build_async_engine():
    """Tạo async engine với xử lý SSL đúng cho asyncpg (Neon/Supabase/Cloud).
    
    asyncpg không hỗ trợ các query params của libpq (như `?sslmode=require`, `channel_binding=...`).
    Hàm này tự động tách và chuyển hóa chúng thành `connect_args={'ssl': ssl_context}` chuẩn.
    """
    url = settings.async_db_url
    connect_args = {
        "timeout": 30,
        "command_timeout": 30,
    }
    
    # Xử lý SSL và query params cho cloud providers (Neon, Supabase, Render...)
    if settings.is_production:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        
        # Bóc tách các tham số của libpq/psycopg2 mà asyncpg không hỗ trợ
        sslmode = params.pop("sslmode", ["require"])[0]
        params.pop("channel_binding", None)
        params.pop("target_session_attrs", None)
        
        # Xây lại clean URL
        new_query = urlencode({k: v[0] for k, v in params.items()})
        clean_url = urlunparse(parsed._replace(query=new_query))
        
        # Thiết lập SSLContext cho asyncpg
        if sslmode in ("require", "verify-ca", "verify-full", "prefer"):
            ssl_ctx = ssl.create_default_context()
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE
            connect_args["ssl"] = ssl_ctx
        
        url = clean_url
    
    return create_async_engine(
        url,
        echo=settings.DEBUG,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        connect_args=connect_args,
    )


# Async Engine for PostgreSQL
engine = _build_async_engine()

# Async Session Factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


def ensure_database_exists():
    """Tự động kiểm tra và tạo database PostgreSQL nếu chưa tồn tại.
    
    - Khi DATABASE_URL được cấu hình (Neon, Supabase, Render, Railway...): 
      Database đã tồn tại trên cloud, bỏ qua hoàn toàn.
    - Khi chạy local với POSTGRES_HOST/PORT: 
      Kết nối và tạo database nếu chưa có.
    """
    # PRODUCTION: Cloud managed database đã tồn tại sẵn, không cần tạo
    if settings.is_production:
        logger.info(f"☁️ [{settings.APP_ENV}] Sử dụng Cloud Database — bỏ qua bước tạo database tự động.")
        return
    
    logger.info(f"🖥️ [{settings.APP_ENV}] Kết nối PostgreSQL local: {settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}")

    # Local PostgreSQL: tự động tạo database nếu chưa có
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
            logger.info(f"✅ Database '{settings.POSTGRES_DB}' đã được tạo thành công trên PostgreSQL.")
        else:
            logger.debug(f"Database '{settings.POSTGRES_DB}' đã tồn tại.")
        cur.close()
        conn.close()
    except Exception as e:
        logger.warning(f"⚠️ Không thể tạo database tự động (bỏ qua): {e}")


async def init_db():
    """Khởi tạo toàn bộ bảng trong PostgreSQL & Qdrant Collection"""
    ensure_database_exists()
    
    try:
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
    except Exception as e:
        logger.exception(f"❌ Khởi tạo database thất bại ({type(e).__name__}): {e}")
        raise

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
