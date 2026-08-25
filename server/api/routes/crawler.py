from typing import List
from fastapi import APIRouter, BackgroundTasks
from loguru import logger

from config.settings import settings
from core.database import AsyncSessionLocal
from core.schemas import ScrapeJobCreate, ScrapeJobResponse
from services.crawler_service import crawler_service
from services.data_pipeline import pipeline_service
from services.job_queue import job_queue_service
from services.telegram_service import telegram_service

router = APIRouter(prefix="/crawl", tags=["Crawler Management"])


async def execute_crawl_task(
    job_id: int, 
    keyword: str, 
    platform: str, 
    limit: int,
    input_mode: str = "keyword",
    urls: Optional[List[str]] = None,
    auto_analyze: bool = False,
    auto_notify_telegram: bool = False
):
    """Hàm background worker thực thi cào dữ liệu và cập nhật tiến trình trên Redis"""
    logger.info(f"🕷️ [REDIS JOB #{job_id}] Bắt đầu cào dữ liệu: '{keyword}' ({platform.upper()}) | Auto-AI: {auto_analyze} | Auto-TG: {auto_notify_telegram}")
    
    # 1. Cập nhật RUNNING trên Redis
    await job_queue_service.update_job(job_id=job_id, status="running")

    try:
        # Cào dữ liệu qua CrawlerService dùng chung (tự động nhận diện keyword / url / batch urls)
        collected_products = await crawler_service.scrape_products(
            keyword_or_url=keyword, 
            platform=platform, 
            limit=limit,
            input_mode=input_mode,
            urls=urls
        )

        # Lưu vào PostgreSQL Core Business Tables
        new_cnt, upd_cnt, alerts = 0, 0, []
        saved_product_ids = []
        if collected_products:
            async with AsyncSessionLocal() as session:
                pipeline_res = await pipeline_service.process_scraped_products(session, collected_products)
                new_cnt = pipeline_res.new_count
                upd_cnt = pipeline_res.updated_count
                alerts = pipeline_res.price_alerts
                saved_product_ids = [p.id for p in pipeline_res.products]

        # 2. Tự động chạy AI phân tích nếu được yêu cầu
        if auto_analyze and saved_product_ids:
            from ai_engine.product_analyzer import product_analyzer
            from core.serializers import serialize_product
            from core.models import Product
            from sqlalchemy import select
            logger.info(f"🧠 [REDIS JOB #{job_id}] Tự động kích hoạt AI phân tích cho {len(saved_product_ids)} sản phẩm...")
            async with AsyncSessionLocal() as session:
                stmt = select(Product).where(Product.id.in_(saved_product_ids[:5]))
                res = await session.execute(stmt)
                prods_to_analyze = res.scalars().all()
                for prod in prods_to_analyze:
                    try:
                        p_dict = serialize_product(prod)
                        ai_res = await product_analyzer.analyze_product(p_dict)
                        prod.ai_analysis = ai_res.model_dump()
                        session.add(prod)
                    except Exception as ai_err:
                        logger.warning(f"Lỗi AI phân tích cho sản phẩm #{prod.id}: {ai_err}")
                await session.commit()

        # 3. Cập nhật COMPLETED trên Redis
        await job_queue_service.update_job(
            job_id=job_id,
            status="completed",
            total_items_found=len(collected_products),
            total_items_saved=new_cnt + upd_cnt
        )
        logger.info(f"✅ [REDIS JOB #{job_id}] Hoàn tất: {len(collected_products)} tìm thấy, {new_cnt} mới, {upd_cnt} cập nhật, {len(alerts)} cảnh báo giá.")

        # 4. Gửi thông báo Telegram
        try:
            # Gửi cảnh báo các món giảm giá sâu
            if alerts and settings.TELEGRAM_NOTIFY_ON_PRICE_DROP:
                for alert in alerts:
                    await telegram_service.send_price_drop_alert(alert)

            # Tự động format bản tin tóm tắt sản phẩm (kèm ảnh/giá/link/AI) gửi ngay vào nhóm chat Telegram
            if saved_product_ids:
                from core.serializers import serialize_product
                from core.models import Product
                from sqlalchemy import select
                async with AsyncSessionLocal() as session:
                    stmt = select(Product).where(Product.id.in_(saved_product_ids[:3]))
                    res = await session.execute(stmt)
                    bulletin_prods = res.scalars().all()
                    for prod in bulletin_prods:
                        await telegram_service.send_product_bulletin(
                            product=serialize_product(prod),
                            ai_data=prod.ai_analysis
                        )

            # Gửi báo cáo hoàn tất cào dữ liệu
            await telegram_service.send_crawl_job_report(
                job_id=job_id,
                keyword=keyword,
                platform=platform,
                total_found=len(collected_products),
                total_saved=new_cnt + upd_cnt,
                price_alerts_count=len(alerts)
            )
        except Exception as tg_err:
            logger.warning(f"Lỗi gửi thông báo Telegram cho Job #{job_id}: {tg_err}")

    except Exception as e:
        logger.error(f"❌ [REDIS JOB #{job_id}] Thất bại: {e}")
        await job_queue_service.update_job(
            job_id=job_id,
            status="failed",
            error_message=str(e)
        )


@router.post("", response_model=ScrapeJobResponse, summary="Kích hoạt tác vụ cào dữ liệu mới")
async def trigger_crawl_job(
    request: ScrapeJobCreate,
    background_tasks: BackgroundTasks
):
    """Tạo mới một Job cào dữ liệu và đưa vào Background Worker trên Redis"""
    job_data = await job_queue_service.create_job(
        keyword_or_url=request.keyword_or_url.strip(),
        platform=request.platform.lower(),
        limit=request.limit_per_platform
    )

    background_tasks.add_task(
        execute_crawl_task,
        job_id=job_data["id"],
        keyword=request.keyword_or_url,
        platform=request.platform,
        limit=request.limit_per_platform,
        input_mode=request.input_mode,
        urls=request.urls,
        auto_analyze=request.auto_analyze,
        auto_notify_telegram=request.auto_notify_telegram
    )

    return job_data


@router.get("/jobs", response_model=List[ScrapeJobResponse], summary="Lấy danh sách các tác vụ cào dữ liệu gần nhất")
async def list_crawl_jobs(limit: int = 20):
    """Đọc danh sách tác vụ cào gần nhất từ Redis Cloud"""
    return await job_queue_service.list_jobs(limit=limit)
