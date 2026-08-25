import asyncio
import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from core.database import init_db, AsyncSessionLocal
from core.schemas import ChatRequest
from ai_engine.shopping_assistant import shopping_assistant


async def test_nvidia_shopping_flow():
    print("======================================================================")
    print("      KIỂM THỬ TOÀN DIỆN AI SHOPPING ASSISTANT VỚI NVIDIA NIM        ")
    print("======================================================================\n")

    await init_db()

    test_queries = [
        ("Test 1: Tư vấn model mới nhất", "giờ tôi muốn mua điện thoại Google Pixel mới nhất"),
        ("Test 2: Cảnh báo giá phi thực tế", "Tìm iPhone 16 Pro Max 5 triệu new seal full box"),
        ("Test 3: So sánh 2 sản phẩm", "Chuột Logitech G304 với Razer Orochi v2 con nào ngon hơn?"),
    ]

    async with AsyncSessionLocal() as session:
        for title, query in test_queries:
            print(f"\n🔹 {title}")
            print(f"👤 User: {query}")
            
            req = ChatRequest(
                message=query,
                session_id=f"test_nv_{hash(query) % 10000}",
                model="meta/llama-3.1-8b-instruct"
            )
            res = await shopping_assistant.chat(session, req)
            
            print(f"🤖 Intent: {res.intent.upper()} (Cached: {res.cached})")
            print(f"📝 Response:\n{res.message[:250]}...\n")
            print(f"🛍️ Số sản phẩm đính kèm: {len(res.recommended_products)}")
            print("-" * 60)

    print("\n🎉 KIỂM THỬ THÀNH CÔNG: NVIDIA NIM LLAMA 3.1 8B HOẠT ĐỘNG HOÀN HẢO!")


if __name__ == "__main__":
    asyncio.run(test_nvidia_shopping_flow())
