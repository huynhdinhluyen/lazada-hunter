import asyncio
import json
import urllib.parse
import re
import time
import random
from typing import List, Optional, Dict, Any
from loguru import logger
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from core.models import Platform
from core.schemas import ProductCreate, parse_price, parse_sold_count
from scrapers.base import BaseScraper
from scrapers.anti_bot import (
    get_browser_headers, STEALTH_JS_PAYLOAD, get_random_viewport
)
from config.settings import settings


class LazadaScraper(BaseScraper):
    """
    Crawler thu thập dữ liệu Lazada Việt Nam:
    - Bóc tách dữ liệu sạch thông qua Network Interceptor (AJAX catalog request)
    - Fallback về DOM parsing với BeautifulSoup (html.parser)
    - Chạy Playwright Sync trong Thread Pool (asyncio.to_thread) hoàn toàn tương thích mọi hệ điều hành
    """
    def __init__(self):
        super().__init__(Platform.LAZADA.value)
        self.base_url = "https://www.lazada.vn"

    async def search(self, keyword: str, page: int = 1, limit: int = 20) -> List[ProductCreate]:
        """Tìm kiếm danh sách sản phẩm trên Lazada"""
        return await self.execute_with_retry(self._search_internal, keyword, page, limit)

    async def get_product_detail(self, product_url: str) -> Optional[ProductCreate]:
        """Lấy chi tiết sản phẩm Lazada theo URL"""
        return await self.execute_with_retry(self._get_product_detail_internal, product_url)

    async def _search_internal(self, keyword: str, page: int = 1, limit: int = 20) -> List[ProductCreate]:
        """Bọc sync scraper trong asyncio.to_thread để không chặn async loop và tránh lỗi event loop trên Windows"""
        return await asyncio.to_thread(self._search_sync, keyword, page, limit)

    async def _get_product_detail_internal(self, product_url: str) -> Optional[ProductCreate]:
        """Bọc sync detail scraper trong asyncio.to_thread"""
        return await asyncio.to_thread(self._get_product_detail_sync, product_url)

    def _search_sync(self, keyword: str, page: int = 1, limit: int = 20) -> List[ProductCreate]:
        logger.info(f"[LAZADA] Đang tìm kiếm từ khóa: '{keyword}' (Trang {page})...")
        products: List[ProductCreate] = []

        with sync_playwright() as p:
            viewport = get_random_viewport()
            browser = p.chromium.launch(
                headless=settings.CRAWLER_HEADLESS,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-infobars"
                ]
            )
            context = browser.new_context(
                viewport=viewport,
                user_agent=get_browser_headers()["User-Agent"],
                locale="vi-VN"
            )
            context.add_init_script(STEALTH_JS_PAYLOAD)
            page_obj = context.new_page()

            # Lắng nghe request AJAX chứa toàn bộ sản phẩm của Lazada
            def on_response(response):
                nonlocal products
                if "catalog/?ajax=true" in response.url and response.status == 200:
                    try:
                        data = response.json()
                        mods = data.get("mods", {})
                        list_items = mods.get("listItems", [])
                        for item in list_items:
                            item_id = str(item.get("itemId") or item.get("nid", ""))
                            name = item.get("name") or item.get("title", "")
                            if not item_id or not name:
                                continue

                            price = parse_price(item.get("price") or item.get("priceShow"))
                            original_price = parse_price(item.get("originalPrice") or item.get("originalPriceShow") or price)
                            discount = None
                            if original_price and original_price > price:
                                discount = round(((original_price - price) / original_price) * 100, 1)

                            raw_url = item.get("itemUrl") or item.get("productUrl", "")
                            product_url = f"https:{raw_url}" if raw_url.startswith("//") else (raw_url if raw_url.startswith("http") else f"https://www.lazada.vn{raw_url}")
                            
                            img = item.get("image")
                            image_url = f"https:{img}" if img and img.startswith("//") else img

                            rating_star = float(item.get("ratingScore") or 0.0)
                            rating_count = int(item.get("review") or 0)
                            historical_sold = parse_sold_count(item.get("itemSoldCntShow") or item.get("sold", 0))

                            prod = ProductCreate(
                                platform=Platform.LAZADA.value,
                                platform_product_id=str(item_id),
                                sku=str(item.get("skuId", "")),
                                name=name,
                                url=product_url,
                                image_url=image_url,
                                brand=item.get("brandName"),
                                current_price=price,
                                original_price=original_price,
                                discount_percentage=discount,
                                rating_star=rating_star,
                                rating_count=rating_count,
                                historical_sold=historical_sold,
                                shop_id=str(item.get("sellerId", "")),
                                shop_name=item.get("sellerName"),
                                shop_location=item.get("location"),
                                is_official_shop=bool(item.get("isOfficial") or item.get("isLazmall")),
                                raw_data=item
                            )
                            if not any(p.platform_product_id == prod.platform_product_id for p in products):
                                products.append(prod)
                    except Exception as err:
                        logger.debug(f"Lỗi parse JSON intercepted Lazada: {err}")

            page_obj.on("response", on_response)

            search_url = f"https://www.lazada.vn/catalog/?q={urllib.parse.quote(keyword)}&page={page}"
            try:
                page_obj.goto(search_url, wait_until="domcontentloaded", timeout=settings.CRAWLER_TIMEOUT_SECONDS * 1000)
                time.sleep(random.uniform(1.5, 2.5))
                
                # Cuộn trang nhẹ nhàng để kích hoạt nạp thêm sản phẩm
                try:
                    for _ in range(3):
                        page_obj.evaluate(f"window.scrollBy(0, {random.randint(400, 700)})")
                        time.sleep(random.uniform(0.3, 0.7))
                except Exception:
                    pass

                time.sleep(random.uniform(1.0, 1.5))

                # 1. Thử trích xuất từ window.pageData trong JavaScript context
                if not products:
                    try:
                        raw_list = page_obj.evaluate("""() => {
                            if (window.pageData && window.pageData.mods && window.pageData.mods.listItems) {
                                return window.pageData.mods.listItems;
                            }
                            return null;
                        }""")
                        if raw_list and isinstance(raw_list, list):
                            for item in raw_list:
                                item_id = str(item.get("itemId") or item.get("nid", ""))
                                name = item.get("name") or item.get("title", "")
                                if not item_id or not name:
                                    continue
                                price = parse_price(item.get("price") or item.get("priceShow"))
                                original_price = parse_price(item.get("originalPrice") or item.get("originalPriceShow") or price)
                                discount = None
                                if original_price and original_price > price:
                                    discount = round(((original_price - price) / original_price) * 100, 1)
                                raw_url = item.get("itemUrl") or item.get("productUrl", "")
                                product_url = f"https:{raw_url}" if raw_url.startswith("//") else (raw_url if raw_url.startswith("http") else f"https://www.lazada.vn{raw_url}")
                                img = item.get("image")
                                image_url = f"https:{img}" if img and img.startswith("//") else img
                                rating_star = float(item.get("ratingScore") or 0.0)
                                rating_count = int(item.get("review") or 0)
                                historical_sold = parse_sold_count(item.get("itemSoldCntShow") or item.get("sold", 0))

                                prod = ProductCreate(
                                    platform=Platform.LAZADA.value,
                                    platform_product_id=str(item_id),
                                    sku=str(item.get("skuId", "")),
                                    name=name,
                                    url=product_url,
                                    image_url=image_url,
                                    brand=item.get("brandName"),
                                    current_price=price,
                                    original_price=original_price,
                                    discount_percentage=discount,
                                    rating_star=rating_star,
                                    rating_count=rating_count,
                                    historical_sold=historical_sold,
                                    shop_id=str(item.get("sellerId", "")),
                                    shop_name=item.get("sellerName"),
                                    shop_location=item.get("location"),
                                    is_official_shop=bool(item.get("isOfficial") or item.get("isLazmall")),
                                    raw_data=item
                                )
                                if not any(p.platform_product_id == prod.platform_product_id for p in products):
                                    products.append(prod)
                    except Exception as e_pdata:
                        logger.debug(f"Lỗi trích xuất window.pageData: {e_pdata}")

                # 2. Nếu vẫn chưa có, fallback parse DOM BeautifulSoup
                if not products:
                    content = page_obj.content()
                    soup = BeautifulSoup(content, "html.parser")
                    cards = soup.select('div[data-qa-locator="product-item"], div._95X4G, div.qmXQo, div[data-item-id]')
                    for card in cards:
                        try:
                            title_elem = card.select_one("a[title], .RfADt a, ._5NxDx a, [class*='title'] a, a")
                            price_elem = card.select_one(".ooOxS, .aBrP0, .price, [class*='price']")
                            if not title_elem or not price_elem:
                                continue
                            
                            name = title_elem.get("title") or title_elem.text.strip()
                            url = title_elem.get("href", "")
                            if url.startswith("//"):
                                url = f"https:{url}"
                            elif url.startswith("/"):
                                url = f"https://www.lazada.vn{url}"

                            # Bóc tách ảnh sản phẩm
                            img_elem = card.select_one("img._95X4G, img.jBKAw, img.picture-wrapper, img[type='product'], img[class*='image'], img")
                            img_url = ""
                            if img_elem:
                                img_url = img_elem.get("src") or img_elem.get("data-src") or img_elem.get("data-image") or ""
                                if img_url.startswith("//"):
                                    img_url = f"https:{img_url}"
                            
                            price = parse_price(price_elem.text)
                            orig_price_elem = card.select_one(".WNoPn, [class*='deleted'], [class*='originalPrice']")
                            orig_price = parse_price(orig_price_elem.text) if orig_price_elem else price
                            if not orig_price or orig_price < price:
                                orig_price = price

                            discount = None
                            if orig_price and orig_price > price:
                                discount = round(((orig_price - price) / orig_price) * 100, 1)

                            prod_id_match = re.search(r"-i(\d+)", url)
                            prod_id = prod_id_match.group(1) if prod_id_match else str(hash(name))

                            rating_elem = card.select_one(".qzqFq, [class*='rating']")
                            rating_star = 0.0
                            if rating_elem:
                                try:
                                    rating_star = float(re.sub(r"[^\d\.]", "", rating_elem.text))
                                except Exception:
                                    pass

                            sold_elem = card.select_one("._1cEkb, [class*='sold']")
                            sold_count = parse_sold_count(sold_elem.text) if sold_elem else 0

                            seller_elem = card.select_one(".seller-name, [class*='seller'], [class*='shop']")
                            shop_name = seller_elem.text.strip() if seller_elem else "Gian hàng Lazada"

                            products.append(ProductCreate(
                                platform=Platform.LAZADA.value,
                                platform_product_id=prod_id,
                                name=name,
                                url=url,
                                image_url=img_url if img_url else None,
                                current_price=price,
                                original_price=orig_price,
                                discount_percentage=discount,
                                rating_star=rating_star,
                                historical_sold=sold_count,
                                shop_name=shop_name
                            ))
                        except Exception:
                            continue

            except Exception as e:
                logger.warning(f"[LAZADA] Lỗi trình duyệt: {e}")
            finally:
                browser.close()

        logger.info(f"[LAZADA] Đã thu thập thành công {len(products)} sản phẩm.")
        return products[:limit]

    async def get_multiple_products_by_urls(self, urls: List[str]) -> List[ProductCreate]:
        """Cào chi tiết danh sách nhiều link sản phẩm Lazada"""
        return await asyncio.to_thread(self._get_multiple_products_sync, urls)

    def _get_multiple_products_sync(self, urls: List[str]) -> List[ProductCreate]:
        """Cào tuần tự danh sách URL với cùng 1 phiên trình duyệt để tối ưu tốc độ & tài nguyên"""
        results: List[ProductCreate] = []
        if not urls:
            return results

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=settings.CRAWLER_HEADLESS,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
            )
            context = browser.new_context(
                viewport=get_random_viewport(),
                user_agent=get_browser_headers()["User-Agent"],
                locale="vi-VN"
            )
            context.add_init_script(STEALTH_JS_PAYLOAD)
            page = context.new_page()

            for idx, url in enumerate(urls):
                clean_url = url.strip()
                if not clean_url:
                    continue
                if not clean_url.startswith("http"):
                    clean_url = f"https://www.lazada.vn/products/{clean_url}" if not clean_url.startswith("www.") else f"https://{clean_url}"

                logger.info(f"🔍 [LAZADA] Đang cào link ({idx+1}/{len(urls)}): {clean_url[:60]}...")
                try:
                    prod = self._extract_product_from_page(page, clean_url)
                    if prod:
                        results.append(prod)
                    time.sleep(random.uniform(1.0, 2.0))
                except Exception as err:
                    logger.warning(f"❌ [LAZADA] Lỗi cào link {clean_url}: {err}")

            browser.close()
        return results

    def _get_product_detail_sync(self, product_url: str) -> Optional[ProductCreate]:
        """Lấy chi tiết 1 sản phẩm Lazada theo URL"""
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=settings.CRAWLER_HEADLESS,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
            )
            context = browser.new_context(
                viewport=get_random_viewport(),
                user_agent=get_browser_headers()["User-Agent"],
                locale="vi-VN"
            )
            context.add_init_script(STEALTH_JS_PAYLOAD)
            page = context.new_page()
            
            try:
                prod = self._extract_product_from_page(page, product_url)
                return prod
            except Exception as e:
                logger.warning(f"[LAZADA] Lỗi lấy chi tiết sản phẩm: {e}")
                return None
            finally:
                browser.close()

    def _extract_product_from_page(self, page, product_url: str) -> Optional[ProductCreate]:
        """Hàm bóc tách chi tiết thông tin từ page Playwright"""
        target_url = str(product_url).strip()
        # Chuẩn hóa domain nếu user gõ nhầm (vd: laazada.vn -> lazada.vn)
        target_url = re.sub(r"https?://(www\.)?la+zada\.[a-z\.]+", "https://www.lazada.vn", target_url)
        if target_url.startswith("//"):
            target_url = "https:" + target_url
        elif not target_url.startswith("http"):
            target_url = f"https://www.lazada.vn/products/{target_url}" if not target_url.startswith("www.") else f"https://{target_url}"

        page.goto(target_url, wait_until="domcontentloaded", timeout=settings.CRAWLER_TIMEOUT_SECONDS * 1000)
        time.sleep(random.uniform(1.5, 2.5))

        # 1. Trích xuất JSON-LD (Schema.org)
        json_ld = page.evaluate("""() => {
            const script = document.querySelector('script[type="application/ld+json"]');
            if (!script) return null;
            try {
                return JSON.parse(script.innerText);
            } catch (e) {
                return null;
            }
        }""")

        # 2. Bóc tách dữ liệu DOM & JavaScript Context (Tên, Giá, Đánh giá, Lượt bán, Specs, Reviews)
        dom_data = page.evaluate("""() => {
            const titleEl = document.querySelector('.pdp-mod-product-badge-title') || document.querySelector('h1');
            const priceEl = document.querySelector('.pdp-mod-product-price-v2') ||
                            document.querySelector('.pdp-v2-product-price-content') ||
                            document.querySelector('.pdp-price_type_normal') || 
                            document.querySelector('.pdp-product-price') || 
                            document.querySelector('.notranslate.pdp-price') ||
                            document.querySelector('.pdp-mod-product-price') ||
                            document.querySelector('.pdp-price') ||
                            document.querySelector('[class*="pdp-price_type_normal"]') ||
                            document.querySelector('[class*="pdp-product-price"]');
            const origPriceEl = document.querySelector('.pdp-price_type_deleted') || document.querySelector('.pdp-price__original') || document.querySelector('[class*="pdp-price_type_deleted"]');
            const discountEl = document.querySelector('.pdp-product-price__discount');
            const ratingScoreEl = document.querySelector('.score-average') || document.querySelector('.pdp-review-summary__stars');
            const ratingCountEl = document.querySelector('.pdp-review-summary__link') || document.querySelector('.count');
            const brandEl = document.querySelector('.pdp-product-brand__brand-link') || document.querySelector('.pdp-link_theme_blue');
            const sellerEl = document.querySelector('.seller-name__detail-name') || document.querySelector('.seller-name');
            const imgEl = document.querySelector('.pdp-mod-common-image.gallery-preview-panel__image') || document.querySelector('.gallery-preview-panel__image');
            const canonicalEl = document.querySelector('link[rel="canonical"]');

            // Bóc tách mô tả và thông số kỹ thuật (highlights)
            const highlightEls = document.querySelectorAll('.pdp-product-highlights li, .pdp-product-desc li');
            const highlights = Array.from(highlightEls).map(el => el.innerText.trim()).filter(Boolean);

            // Bóc tách các đoạn đánh giá / review thực tế
            const reviewItemEls = document.querySelectorAll('.item-content .content, .review-content-sl, .mod-reviews .content');
            const reviews = Array.from(reviewItemEls).map(el => el.innerText.trim()).filter(Boolean);

            // Bóc tách giá từ Telemetry / Tracking Object của Lazada
            let dataLayerPrice = '';
            if (window.dataLayer && Array.isArray(window.dataLayer)) {
                for (let item of window.dataLayer) {
                    if (item && item.pdt_price) {
                        dataLayerPrice = item.pdt_price;
                        break;
                    }
                }
            }

            let pdpTrackingPrice = '';
            if (window.pdpTrackingData) {
                try {
                    let parsed = typeof window.pdpTrackingData === 'string' ? JSON.parse(window.pdpTrackingData) : window.pdpTrackingData;
                    if (parsed && parsed.pdt_price) pdpTrackingPrice = parsed.pdt_price;
                } catch(e){}
            }

            let scriptPrice = '';
            let scriptOrigPrice = '';
            const scripts = Array.from(document.querySelectorAll('script')).map(s => s.innerText);
            for (let txt of scripts) {
                if (!scriptPrice) {
                    let m = txt.match(/"pdt_price"\s*:\s*"([^"]+)"/) ||
                            txt.match(/"salePrice"\s*:\s*\{\s*"text"\s*:\s*"([^"]+)"/) ||
                            txt.match(/"priceShow"\s*:\s*"([^"]+)"/) ||
                            txt.match(/"price"\s*:\s*\{\s*"text"\s*:\s*"([^"]+)"/);
                    if (m) scriptPrice = m[1];
                }
                if (!scriptOrigPrice) {
                    let mOrig = txt.match(/"originalPrice"\s*:\s*\{\s*"text"\s*:\s*"([^"]+)"/) ||
                                txt.match(/"originalPriceShow"\s*:\s*"([^"]+)"/);
                    if (mOrig) scriptOrigPrice = mOrig[1];
                }
            }

            return {
                title: titleEl ? titleEl.innerText.trim() : '',
                priceText: priceEl ? priceEl.innerText.trim() : '',
                origPriceText: origPriceEl ? origPriceEl.innerText.trim() : '',
                discountText: discountEl ? discountEl.innerText.trim() : '',
                ratingScore: ratingScoreEl ? ratingScoreEl.innerText.trim() : '',
                ratingCount: ratingCountEl ? ratingCountEl.innerText.trim() : '',
                brand: brandEl ? brandEl.innerText.trim() : '',
                seller: sellerEl ? sellerEl.innerText.trim() : '',
                image: imgEl ? (imgEl.src || imgEl.getAttribute('src')) : '',
                canonicalUrl: canonicalEl ? canonicalEl.href : '',
                highlights: highlights,
                reviews: reviews,
                dataLayerPrice: dataLayerPrice,
                pdpTrackingPrice: pdpTrackingPrice,
                scriptPrice: scriptPrice,
                scriptOrigPrice: scriptOrigPrice
            };
        }""") or {}

        # Tổng hợp dữ liệu từ JSON-LD và DOM
        name = ""
        price = 0.0
        orig_price = None
        image_url = ""
        brand = dom_data.get("brand") or None
        rating_star = 0.0
        rating_count = 0

        if json_ld and isinstance(json_ld, dict):
            name = json_ld.get("name") or ""
            raw_img = json_ld.get("image")
            if isinstance(raw_img, list) and len(raw_img) > 0:
                image_url = str(raw_img[0])
            elif isinstance(raw_img, dict):
                image_url = str(raw_img.get("url") or raw_img.get("src") or "")
            elif isinstance(raw_img, str):
                image_url = raw_img
            else:
                image_url = ""

            if not brand and isinstance(json_ld.get("brand"), dict):
                brand = json_ld.get("brand", {}).get("name")
            
            offers = json_ld.get("offers", {})
            if isinstance(offers, dict):
                price = parse_price(offers.get("price") or offers.get("lowPrice") or offers.get("highPrice") or 0)
            elif isinstance(offers, list) and len(offers) > 0:
                first_offer = offers[0]
                if isinstance(first_offer, dict):
                    price = parse_price(first_offer.get("price") or first_offer.get("lowPrice") or first_offer.get("highPrice") or 0)

            agg_rating = json_ld.get("aggregateRating", {})
            if isinstance(agg_rating, dict):
                rating_star = float(agg_rating.get("ratingValue") or 0.0)
                rating_count = int(agg_rating.get("reviewCount") or 0)

        # Fallback đa tầng nếu JSON-LD thiếu giá
        if not name:
            name = dom_data.get("title") or "Sản phẩm Lazada"
        if price == 0.0:
            price = (
                parse_price(dom_data.get("dataLayerPrice")) or
                parse_price(dom_data.get("pdpTrackingPrice")) or
                parse_price(dom_data.get("scriptPrice")) or
                parse_price(dom_data.get("priceText"))
            )

        if dom_data.get("origPriceText") or dom_data.get("scriptOrigPrice"):
            orig_price = parse_price(dom_data.get("origPriceText") or dom_data.get("scriptOrigPrice"))
        if not orig_price or orig_price <= 0:
            orig_price = price
        if not image_url:
            image_url = dom_data.get("image") or ""

        if isinstance(image_url, str) and image_url.startswith("//"):
            image_url = "https:" + image_url

        if rating_star == 0.0 and dom_data.get("ratingScore"):
            try:
                rating_star = float(re.sub(r"[^\d\.]", "", dom_data.get("ratingScore")))
            except Exception:
                pass

        if rating_count == 0 and dom_data.get("ratingCount"):
            try:
                rating_count = int(re.sub(r"[^\d]", "", dom_data.get("ratingCount")))
            except Exception:
                pass

        discount = None
        if orig_price and orig_price > price:
            discount = round(((orig_price - price) / orig_price) * 100, 1)

        # Lấy URL chuẩn xác nhất
        canonical = dom_data.get("canonicalUrl")
        final_url = canonical if (canonical and "lazada.vn" in canonical) else (page.url if "lazada.vn" in page.url else target_url)

        prod_id_match = re.search(r"-i(\d+)", final_url)
        prod_id = prod_id_match.group(1) if prod_id_match else str(abs(hash(final_url)))

        raw_payload = {
            "json_ld": json_ld,
            "dom_data": dom_data,
            "highlights": dom_data.get("highlights", []),
            "reviews": dom_data.get("reviews", []),
        }

        return ProductCreate(
            platform=Platform.LAZADA.value,
            platform_product_id=prod_id,
            name=name,
            url=final_url,
            image_url=image_url,
            brand=brand,
            current_price=price,
            original_price=orig_price,
            discount_percentage=discount,
            rating_star=rating_star,
            rating_count=rating_count,
            historical_sold=rating_count * 3 if rating_count > 0 else 10,
            shop_name=dom_data.get("seller") or "Gian hàng Lazada",
            is_official_shop=bool("official" in (dom_data.get("seller") or "").lower() or "lazmall" in (dom_data.get("seller") or "").lower()),
            raw_data=raw_payload
        )

