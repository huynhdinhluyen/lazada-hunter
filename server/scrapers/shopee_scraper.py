import json
import os
import urllib.parse
import re
from typing import List, Optional, Dict, Any
from loguru import logger
from curl_cffi import requests as cffi_requests
from playwright.async_api import async_playwright

from core.models import Platform
from core.schemas import ProductCreate, ProductVariantCreate, parse_price, parse_sold_count
from scrapers.base import BaseScraper
from scrapers.anti_bot import (
    get_browser_headers, human_delay, simulate_human_scroll, 
    simulate_human_mouse_move, STEALTH_JS_PAYLOAD, get_random_viewport
)
from scrapers.proxy_manager import proxy_manager
from config.settings import settings


COOKIE_FILE_PATH = os.path.join(os.getcwd(), "shopee_cookies.json")


class ShopeeScraper(BaseScraper):
    """
    Crawler thu thập dữ liệu Shopee Việt Nam:
    - Hỗ trợ Cookie / Session Warm-up (từ shopee_cookies.json hoặc .env)
    - Fast API Direct Requests (curl_cffi TLS impersonation)
    - Playwright Browser với Persistent Profile và Human Interaction Simulation
    """
    def __init__(self):
        super().__init__(Platform.SHOPEE.value)
        self.base_url = "https://shopee.vn"

    def _load_stored_cookies(self) -> Dict[str, str]:
        """Đọc cookies Shopee từ file nếu có"""
        if os.path.exists(COOKIE_FILE_PATH):
            try:
                with open(COOKIE_FILE_PATH, "r", encoding="utf-8") as f:
                    cookies_data = json.load(f)
                    if isinstance(cookies_data, list):
                        return {c["name"]: c["value"] for c in cookies_data if "name" in c and "value" in c}
                    elif isinstance(cookies_data, dict):
                        return cookies_data
            except Exception as e:
                logger.debug(f"Không thể đọc shopee_cookies.json: {e}")
        return {}

    async def search(self, keyword: str, page: int = 1, limit: int = 20) -> List[ProductCreate]:
        """Tìm kiếm danh sách sản phẩm theo từ khóa trên Shopee"""
        return await self.execute_with_retry(self._search_internal, keyword, page, limit)

    async def get_product_detail(self, product_url: str) -> Optional[ProductCreate]:
        """Lấy chi tiết sản phẩm Shopee theo URL hoặc ID"""
        return await self.execute_with_retry(self._get_product_detail_internal, product_url)

    async def _search_internal(self, keyword: str, page: int = 1, limit: int = 20) -> List[ProductCreate]:
        offset = (page - 1) * limit
        
        # 1. Thử Fast API với curl_cffi kèm Stored Cookies nếu có
        cookies = self._load_stored_cookies()
        if cookies:
            try:
                products = await self._search_via_fast_api(keyword, offset, limit, cookies=cookies)
                if products:
                    logger.info(f"[SHOPEE-API] Thu thập thành công {len(products)} sản phẩm cho từ khóa '{keyword}'")
                    return products
            except Exception as e:
                logger.debug(f"[SHOPEE-API] Fast API với cookie không thành công: {e}")

        # 2. Chuyển sang Playwright Browser
        return await self._search_via_playwright(keyword, page, limit)

    async def _search_via_fast_api(
        self, 
        keyword: str, 
        offset: int, 
        limit: int, 
        cookies: Optional[Dict[str, str]] = None
    ) -> List[ProductCreate]:
        """Gọi API nội bộ của Shopee với giả lập TLS JA3/JA4 của Chrome"""
        api_url = (
            f"https://shopee.vn/api/v4/search/search_items?"
            f"by=relevancy&keyword={urllib.parse.quote(keyword)}&limit={limit}&newest={offset}"
            f"&order=desc&page_type=search&scenario=PAGE_GLOBAL_SEARCH&version=2"
        )
        headers = get_browser_headers(referer=f"https://shopee.vn/search?keyword={urllib.parse.quote(keyword)}")
        headers.update({
            "x-api-source": "pc",
            "x-shopee-language": "vi",
            "x-requested-with": "XMLHttpRequest",
            "Accept": "application/json",
        })
        
        proxy = proxy_manager.get_current_proxy()
        proxies = {"http": proxy, "https": proxy} if proxy else None

        response = cffi_requests.get(
            api_url,
            headers=headers,
            cookies=cookies,
            impersonate="chrome124",
            proxies=proxies,
            timeout=15
        )

        if response.status_code != 200:
            raise Exception(f"Shopee API trả về status code {response.status_code}")

        data = response.json()
        items = data.get("items") or []
        products: List[ProductCreate] = []

        for item_wrapper in items:
            item_data = item_wrapper.get("item_basic") or item_wrapper
            if not item_data or not item_data.get("itemid"):
                continue

            item_id = str(item_data.get("itemid"))
            shop_id = str(item_data.get("shopid"))
            name = item_data.get("name", "").strip()
            if not name:
                continue

            raw_price = item_data.get("price") or item_data.get("price_min") or 0
            price = parse_price(raw_price)
            
            raw_original = item_data.get("price_before_discount") or item_data.get("price_max_before_discount")
            original_price = parse_price(raw_original) if raw_original and raw_original > 0 else price
            
            discount = None
            if original_price and original_price > price:
                discount = round(((original_price - price) / original_price) * 100, 1)

            rating_info = item_data.get("item_rating") or {}
            rating_star = round(float(rating_info.get("rating_star", 0.0)), 1)
            rating_count = sum(rating_info.get("rating_count", [0]))
            historical_sold = parse_sold_count(item_data.get("historical_sold") or item_data.get("sold", 0))

            img_hash = item_data.get("image")
            image_url = f"https://down-vn.img.susercontent.com/file/{img_hash}" if img_hash else None
            product_url = f"https://shopee.vn/product/{shop_id}/{item_id}"

            product = ProductCreate(
                platform=Platform.SHOPEE.value,
                platform_product_id=f"{shop_id}_{item_id}",
                name=name,
                url=product_url,
                image_url=image_url,
                brand=item_data.get("brand"),
                current_price=price,
                original_price=original_price,
                discount_percentage=discount,
                rating_star=rating_star,
                rating_count=rating_count,
                historical_sold=historical_sold,
                stock=item_data.get("stock"),
                shop_id=shop_id,
                shop_location=item_data.get("shop_location"),
                is_official_shop=bool(item_data.get("show_official_shop_label")),
                raw_data={"itemid": item_id, "shopid": shop_id}
            )
            products.append(product)

        return products

    async def _search_via_playwright(self, keyword: str, page: int = 1, limit: int = 20) -> List[ProductCreate]:
        """Cào Shopee bằng Playwright với Network Interception & Human Emulation"""
        logger.info(f"[SHOPEE] Khởi động trình duyệt Playwright tìm kiếm: '{keyword}' (Trang {page})")
        captured_products: List[ProductCreate] = []
        user_data_dir = os.path.join(os.getcwd(), ".browser_profile")
        
        async with async_playwright() as p:
            viewport = get_random_viewport()
            context = await p.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                headless=settings.CRAWLER_HEADLESS,
                viewport=viewport,
                user_agent=get_browser_headers()["User-Agent"],
                locale="vi-VN",
                timezone_id="Asia/Ho_Chi_Minh",
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-infobars"
                ]
            )
            
            await context.add_init_script(STEALTH_JS_PAYLOAD)
            page_obj = context.pages[0] if context.pages else await context.new_page()

            async def handle_response(response):
                nonlocal captured_products
                if "search_items" in response.url and response.status == 200:
                    try:
                        res_json = await response.json()
                        items = res_json.get("items") or []
                        for item_wrapper in items:
                            item_data = item_wrapper.get("item_basic") or item_wrapper
                            if not item_data or not item_data.get("itemid"):
                                continue
                            
                            item_id = str(item_data.get("itemid"))
                            shop_id = str(item_data.get("shopid"))
                            name = item_data.get("name", "").strip()
                            if not name:
                                continue

                            price = parse_price(item_data.get("price") or item_data.get("price_min") or 0)
                            raw_original = item_data.get("price_before_discount") or item_data.get("price_max_before_discount")
                            original_price = parse_price(raw_original) if raw_original and raw_original > 0 else price
                            
                            discount = None
                            if original_price and original_price > price:
                                discount = round(((original_price - price) / original_price) * 100, 1)

                            rating_info = item_data.get("item_rating") or {}
                            rating_star = round(float(rating_info.get("rating_star", 0.0)), 1)
                            historical_sold = parse_sold_count(item_data.get("historical_sold") or item_data.get("sold", 0))
                            img_hash = item_data.get("image")
                            image_url = f"https://down-vn.img.susercontent.com/file/{img_hash}" if img_hash else None

                            prod = ProductCreate(
                                platform=Platform.SHOPEE.value,
                                platform_product_id=f"{shop_id}_{item_id}",
                                name=name,
                                url=f"https://shopee.vn/product/{shop_id}/{item_id}",
                                image_url=image_url,
                                current_price=price,
                                original_price=original_price,
                                discount_percentage=discount,
                                rating_star=rating_star,
                                historical_sold=historical_sold,
                                shop_id=shop_id,
                                shop_location=item_data.get("shop_location"),
                                is_official_shop=bool(item_data.get("show_official_shop_label"))
                            )
                            if not any(p.platform_product_id == prod.platform_product_id for p in captured_products):
                                captured_products.append(prod)
                    except Exception as err:
                        logger.debug(f"Lỗi parse intercepted response Shopee: {err}")

            page_obj.on("response", handle_response)

            search_url = f"https://shopee.vn/search?keyword={urllib.parse.quote(keyword)}&page={page - 1}"
            try:
                await page_obj.goto(search_url, wait_until="domcontentloaded", timeout=settings.CRAWLER_TIMEOUT_SECONDS * 1000)
                await human_delay(1.5, 2.5)
                await simulate_human_mouse_move(page_obj, 500, 400)
                await simulate_human_scroll(page_obj, min_scrolls=2, max_scrolls=4)
                await human_delay(1.0, 2.0)

            except Exception as e:
                logger.warning(f"[SHOPEE] Lỗi khi tải trang Playwright: {e}")
            finally:
                await context.close()

        logger.info(f"[SHOPEE] Thu thập được {len(captured_products)} sản phẩm.")
        return captured_products[:limit]

    async def _get_product_detail_internal(self, product_url: str) -> Optional[ProductCreate]:
        """Trích xuất chi tiết sản phẩm Shopee"""
        match = re.search(r"(\d+)/(\d+)", product_url) or re.search(r"i\.(\d+)\.(\d+)", product_url)
        if not match:
            logger.warning(f"URL Shopee không hợp lệ: {product_url}")
            return None
        
        shop_id, item_id = match.groups()
        api_url = f"https://shopee.vn/api/v4/item/get?itemid={item_id}&shopid={shop_id}"
        
        headers = get_browser_headers(referer=product_url)
        headers.update({
            "x-api-source": "pc",
            "x-shopee-language": "vi",
            "Accept": "application/json"
        })
        
        cookies = self._load_stored_cookies()
        proxy = proxy_manager.get_current_proxy()
        proxies = {"http": proxy, "https": proxy} if proxy else None

        response = cffi_requests.get(
            api_url,
            headers=headers,
            cookies=cookies,
            impersonate="chrome124",
            proxies=proxies,
            timeout=15
        )
        
        if response.status_code != 200:
            raise Exception(f"Không thể lấy chi tiết Shopee API (Status: {response.status_code})")
            
        data = response.json().get("data")
        if not data:
            return None

        name = data.get("name", "")
        price = parse_price(data.get("price"))
        original_price = parse_price(data.get("price_before_discount") or price)
        discount = round(((original_price - price) / original_price) * 100, 1) if original_price > price else None

        return ProductCreate(
            platform=Platform.SHOPEE.value,
            platform_product_id=f"{shop_id}_{item_id}",
            name=name,
            url=product_url,
            image_url=f"https://down-vn.img.susercontent.com/file/{data.get('image')}" if data.get("image") else None,
            brand=data.get("brand"),
            current_price=price,
            original_price=original_price,
            discount_percentage=discount,
            rating_star=round(float(data.get("item_rating", {}).get("rating_star", 0.0)), 1),
            rating_count=sum(data.get("item_rating", {}).get("rating_count", [0])),
            historical_sold=parse_sold_count(data.get("historical_sold", 0)),
            stock=data.get("stock"),
            shop_id=str(shop_id),
            raw_data=data
        )
