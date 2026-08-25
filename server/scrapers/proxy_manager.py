import asyncio
import subprocess
import httpx
from typing import Optional, List
from loguru import logger

from config.settings import settings


class ProxyManager:
    """
    Quản lý xoay vòng Proxy:
    - Hỗ trợ đổi IP 4G qua thiết bị Android (ADB bật/tắt Airplane Mode)
    - Hỗ trợ xoay vòng danh sách HTTP/SOCKS5 Proxy
    - Fallback về Direct connection với Adaptive Rate Limiting
    """
    def __init__(self):
        self.use_proxy = settings.USE_PROXY
        self.proxy_url = settings.PROXY_URL
        self.adb_device_id = settings.ADB_DEVICE_ID
        self.proxy_pool: List[str] = [p.strip() for p in (settings.PROXY_URL or "").split(",") if p.strip()]
        self.current_index = 0
        self._lock = asyncio.Lock()

    def get_current_proxy(self) -> Optional[str]:
        """Lấy proxy hiện tại"""
        if not self.use_proxy:
            return None
        if self.proxy_pool:
            return self.proxy_pool[self.current_index % len(self.proxy_pool)]
        return self.proxy_url

    async def get_current_ip(self) -> str:
        """Kiểm tra địa chỉ IP Public hiện tại"""
        proxy = self.get_current_proxy()
        try:
            async with httpx.AsyncClient(proxy=proxy, timeout=8.0) as client:
                res = await client.get("https://api.ipify.org?format=json")
                if res.status_code == 200:
                    return res.json().get("ip", "Unknown")
        except Exception as e:
            logger.debug(f"Không thể kiểm tra IP: {e}")
        return "Unknown"

    async def rotate_ip(self) -> bool:
        """
        Kích hoạt đổi IP mới:
        - Nếu cấu hình ADB: Bật/tắt chế độ máy bay trên điện thoại Android
        - Nếu có Proxy Pool: Chuyển sang proxy kế tiếp
        """
        async with self._lock:
            if self.adb_device_id:
                logger.info(f"🔄 Đang kích hoạt xoay IP 4G qua ADB (Device: {self.adb_device_id})...")
                try:
                    cmd_base = f"adb -s {self.adb_device_id}" if self.adb_device_id != "auto" else "adb"
                    
                    # 1. Bật Airplane mode (ngắt 4G)
                    proc = await asyncio.create_subprocess_shell(
                        f"{cmd_base} shell cmd connectivity airplane-mode enable",
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE
                    )
                    await proc.communicate()
                    await asyncio.sleep(2.0)
                    
                    # 2. Tắt Airplane mode (nhận IP mới)
                    proc = await asyncio.create_subprocess_shell(
                        f"{cmd_base} shell cmd connectivity airplane-mode disable",
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE
                    )
                    await proc.communicate()
                    await asyncio.sleep(3.5)
                    
                    new_ip = await self.get_current_ip()
                    logger.info(f"✅ Đã đổi IP 4G thành công! IP mới: {new_ip}")
                    return True
                except Exception as e:
                    logger.error(f"Lỗi khi xoay IP qua ADB: {e}")
                    return False

            elif len(self.proxy_pool) > 1:
                self.current_index = (self.current_index + 1) % len(self.proxy_pool)
                logger.info(f"🔄 Đã chuyển sang Proxy kế tiếp: {self.get_current_proxy()}")
                return True

            logger.debug("Không có cấu hình ADB hoặc Proxy Pool để xoay IP.")
            return False


proxy_manager = ProxyManager()
