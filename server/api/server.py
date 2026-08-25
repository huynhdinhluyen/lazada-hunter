import sys
import asyncio
import warnings

if sys.platform == "win32":
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from config.settings import settings
from core.database import init_db
from api.routes.chat import router as chat_router
from api.routes.products import router as products_router
from api.routes.crawler import router as crawler_router
from api.routes.telegram import router as telegram_router
from api.routes.ai import router as ai_router
from api.routes.watchlist import router as watchlist_router


from services.watchlist_scheduler import watchlist_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Quản lý vòng đời khởi động và đóng ứng dụng"""
    logger.info("🚀 Khởi động Lazada Hunter API Server...")
    await init_db()
    logger.info("✅ Database PostgreSQL & Schema đã sẵn sàng phục vụ API.")
    
    # Khởi động Background Cron Job theo dõi giá Watchlist
    watchlist_scheduler.start()
    
    yield
    
    # Dừng Scheduler khi tắt server
    watchlist_scheduler.stop()
    logger.info("🛑 Đang dừng API Server...")


app = FastAPI(
    title="Lazada Hunter - Intelligent E-Commerce Assistant API",
    description="Hệ thống API RESTful cho Lazada Việt Nam: AI Trợ lý Mua sắm, Cào dữ liệu Live, Biểu đồ giá và Thông báo Telegram.",
    version="1.0.0",
    lifespan=lifespan
)

# Cấu hình CORS cho phép Next.js Frontend truy cập
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Đăng ký các router với prefix /api/v1
app.include_router(chat_router, prefix="/api/v1")
app.include_router(products_router, prefix="/api/v1")
app.include_router(crawler_router, prefix="/api/v1")
app.include_router(telegram_router, prefix="/api/v1")
app.include_router(ai_router, prefix="/api/v1")
app.include_router(watchlist_router)


@app.get("/health", tags=["Health"])
@app.get("/api/v1/health", tags=["Health"])
async def health_check():
    """Kiểm tra tình trạng sống của API Server"""
    return {
        "status": "healthy",
        "app": "Lazada Hunter",
        "version": "1.0.0"
    }
