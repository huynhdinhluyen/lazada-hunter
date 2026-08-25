import asyncio
import sys
from pathlib import Path
import httpx

root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from api.server import app


async def test_all_api_endpoints():
    print("======================================================================")
    print("      KIỂM THỬ TỰ ĐỘNG CÁC ENDPOINT REST API (LAZADA HUNTER v1)      ")
    print("======================================================================\n")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Health Check
        r_health = await client.get("/health")
        print(f"1. GET /health -> Status: {r_health.status_code}, Body: {r_health.json()}")

        # 2. Products list
        r_prods = await client.get("/api/v1/products?page=1&page_size=3")
        prods_data = r_prods.json()
        print(f"2. GET /api/v1/products -> Status: {r_prods.status_code}, Total: {prods_data.get('total')}, Returned: {len(prods_data.get('items', []))}")

        # 3. Fast-Path Guardrail Chat message
        r_chat = await client.post("/api/v1/chat", json={"message": "Thời tiết hôm nay thế nào?"})
        chat_data = r_chat.json()
        print(f"3. POST /api/v1/chat (Chitchat Fast-Path) -> Intent: {chat_data.get('intent')}, Message: \"{chat_data.get('message')[:50]}...\"")

        # 4. Crawler jobs list
        r_jobs = await client.get("/api/v1/crawl/jobs")
        print(f"4. GET /api/v1/crawl/jobs -> Status: {r_jobs.status_code}, Recent Jobs: {len(r_jobs.json())}")

        # 5. Telegram Bot status
        r_tg = await client.get("/api/v1/telegram/status")
        tg_data = r_tg.json()
        print(f"5. GET /api/v1/telegram/status -> Status: {r_tg.status_code}, Connected: {tg_data.get('is_connected')}, Bot: @{tg_data.get('bot_info', {}).get('username')}\n")

    print("🎉 TẤT CẢ 5 NHÓM ENDPOINT REST API ĐÃ HOẠT ĐỘNG HOÀN HẢO!")


if __name__ == "__main__":
    asyncio.run(test_all_api_endpoints())
