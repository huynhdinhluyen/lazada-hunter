import random
import asyncio
import math
from typing import Dict, List, Tuple
from loguru import logger
from fake_useragent import UserAgent

try:
    ua_generator = UserAgent(platforms='desktop')
except Exception:
    ua_generator = None

# Danh sách User-Agents máy tính hiện đại chuẩn 2025/2026
FALLBACK_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 Edg/128.0.0.0",
]

VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1536, "height": 864},
    {"width": 1440, "height": 900},
    {"width": 1366, "height": 768},
    {"width": 1600, "height": 900},
]


def get_random_user_agent() -> str:
    """Lấy ngẫu nhiên một User-Agent máy tính thật"""
    if ua_generator:
        try:
            return ua_generator.random
        except Exception:
            pass
    return random.choice(FALLBACK_USER_AGENTS)


def get_random_viewport() -> Dict[str, int]:
    """Lấy ngẫu nhiên kích thước màn hình phổ biến"""
    return random.choice(VIEWPORTS)


def get_browser_headers(referer: str = None) -> Dict[str, str]:
    """Tạo Headers giả lập trình duyệt Chrome thật 100% bao gồm Client Hints (Sec-CH-UA)"""
    ua = get_random_user_agent()
    headers = {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Sec-Ch-Ua": '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin" if referer else "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "max-age=0",
        "Priority": "u=0, i",
    }
    if referer:
        headers["Referer"] = referer
    return headers


async def human_delay(min_sec: float = 1.5, max_sec: float = 4.0, gaussian: bool = True):
    """
    Tạo khoảng trễ ngẫu nhiên mô phỏng thời gian đọc/thao tác của con người.
    Sử dụng phân phối chuẩn (Gaussian distribution) để tạo độ trễ tự nhiên nhất.
    """
    if gaussian:
        mean = (min_sec + max_sec) / 2
        sigma = (max_sec - min_sec) / 4
        delay = random.gauss(mean, sigma)
        delay = max(min_sec, min(max_sec, delay))
    else:
        delay = random.uniform(min_sec, max_sec)
    
    logger.debug(f"Human delay: {delay:.2f}s")
    await asyncio.sleep(delay)


# JS Snippet để ẩn hoàn toàn dấu vết Headless / Automation trong Playwright
STEALTH_JS_PAYLOAD = """
(() => {
    // 1. Ghi đè navigator.webdriver
    Object.defineProperty(navigator, 'webdriver', {
        get: () => undefined,
    });

    // 2. Giả lập chrome runtime
    window.chrome = {
        app: {
            isInstalled: false,
            InstallState: { DISABLED: 'disabled', INSTALLED: 'installed', NOT_INSTALLED: 'not_installed' },
            RunningState: { CANNOT_RUN: 'cannot_run', READY_TO_RUN: 'ready_to_run', RUNNING: 'running' }
        },
        runtime: {
            OnInstalledReason: { CHROME_UPDATE: 'chrome_update', INSTALL: 'install', SHARED_MODULE_UPDATE: 'shared_module_update', UPDATE: 'update' },
            OnRestartRequiredReason: { APP_UPDATE: 'app_update', OS_UPDATE: 'os_update', PERIODIC: 'periodic' },
            PlatformArch: { ARM: 'arm', ARM64: 'arm64', MIPS: 'mips', MIPS64: 'mips64', X86_32: 'x86-32', X86_64: 'x86-64' },
            PlatformNaclArch: { ARM: 'arm', MIPS: 'mips', MIPS64: 'mips64', X86_32: 'x86-32', X86_64: 'x86-64' },
            PlatformOs: { ANDROID: 'android', CROS: 'cros', LINUX: 'linux', MAC: 'mac', OPENBSD: 'openbsd', WIN: 'win' }
        }
    };

    // 3. Giả lập plugins và languages
    Object.defineProperty(navigator, 'plugins', {
        get: () => [1, 2, 3, 4, 5],
    });
    Object.defineProperty(navigator, 'languages', {
        get: () => ['vi-VN', 'vi', 'en-US', 'en'],
    });

    // 4. Che giấu WebGL Vendor/Renderer
    const getParameter = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function(parameter) {
        if (parameter === 37445) {
            return 'Google Inc. (NVIDIA)';
        }
        if (parameter === 37446) {
            return 'ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)';
        }
        return getParameter.apply(this, [parameter]);
    };
})();
"""


def generate_bezier_curve(start_point: Tuple[float, float], end_point: Tuple[float, float], num_points: int = 25) -> List[Tuple[float, float]]:
    """
    Sinh quỹ đạo chuyển động chuột theo đường cong Bézier bậc 3
    Mô phỏng tay người di chuyển (có độ cong, gia tốc và độ rung nhẹ).
    """
    x0, y0 = start_point
    x3, y3 = end_point

    # Điểm điều khiển ngẫu nhiên tạo độ cong
    ctrl_deviation = max(abs(x3 - x0), abs(y3 - y0)) * 0.3
    x1 = x0 + (x3 - x0) * 0.25 + random.uniform(-ctrl_deviation, ctrl_deviation)
    y1 = y0 + (y3 - y0) * 0.25 + random.uniform(-ctrl_deviation, ctrl_deviation)
    x2 = x0 + (x3 - x0) * 0.75 + random.uniform(-ctrl_deviation, ctrl_deviation)
    y2 = y0 + (y3 - y0) * 0.75 + random.uniform(-ctrl_deviation, ctrl_deviation)

    points = []
    for i in range(num_points):
        t = i / (num_points - 1)
        # Công thức Bézier bậc 3: B(t) = (1-t)^3*P0 + 3*(1-t)^2*t*P1 + 3*(1-t)*t^2*P2 + t^3*P3
        x = (1 - t)**3 * x0 + 3 * (1 - t)**2 * t * x1 + 3 * (1 - t) * t**2 * x2 + t**3 * x3
        y = (1 - t)**3 * y0 + 3 * (1 - t)**2 * t * y1 + 3 * (1 - t) * t**2 * y2 + t**3 * y3
        # Thêm rung nhẹ tự nhiên (micro-jitter)
        jitter_x = random.uniform(-1.0, 1.0)
        jitter_y = random.uniform(-1.0, 1.0)
        points.append((x + jitter_x, y + jitter_y))

    return points


async def simulate_human_mouse_move(page, target_x: float, target_y: float):
    """Mô phỏng di chuột mượt mà đến tọa độ đích"""
    try:
        # Lấy tọa độ chuột hiện tại hoặc ngẫu nhiên
        start_x = random.uniform(100, 500)
        start_y = random.uniform(100, 400)
        points = generate_bezier_curve((start_x, start_y), (target_x, target_y), num_points=random.randint(15, 30))
        for px, py in points:
            await page.mouse.move(px, py)
            await asyncio.sleep(random.uniform(0.005, 0.02))
    except Exception as e:
        logger.debug(f"Mouse move simulation note: {e}")


async def simulate_human_scroll(page, min_scrolls: int = 2, max_scrolls: int = 5):
    """
    Mô phỏng hành vi cuộn trang đọc nội dung của người dùng thật:
    - Cuộn từng đoạn với gia tốc mượt
    - Dừng ngẫu nhiên vài giây để 'đọc'
    - Thỉnh thoảng cuộn nhẹ lên trên rồi cuộn tiếp xuống
    """
    scrolls = random.randint(min_scrolls, max_scrolls)
    for i in range(scrolls):
        scroll_distance = random.randint(300, 700)
        
        # Thỉnh thoảng lướt ngược lên trên như người đang xem lại
        if random.random() < 0.25 and i > 0:
            up_dist = -random.randint(100, 300)
            await page.evaluate(f"window.scrollBy({{top: {up_dist}, behavior: 'smooth'}})")
            await asyncio.sleep(random.uniform(0.4, 0.8))
        
        # Cuộn xuống mượt mà
        await page.evaluate(f"window.scrollBy({{top: {scroll_distance}, behavior: 'smooth'}})")
        # Tạm dừng đọc
        await asyncio.sleep(random.uniform(0.8, 2.2))
