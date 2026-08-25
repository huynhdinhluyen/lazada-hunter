from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, SecretStr


class Settings(BaseSettings):
    """
    Cấu hình toàn hệ thống E-Commerce Crawler & AI Engine
    - Sử dụng SecretStr để bảo mật tuyệt đối các thông tin nhạy cảm (API Keys, Passwords).
    - Tự động nạp từ file .env hoặc biến môi trường hệ thống.
    """
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8", 
        extra="ignore"
    )

    # App
    APP_NAME: str = "E-Commerce Intelligent Crawler"
    DEBUG: bool = False

    # Database Credentials
    POSTGRES_USER: str = Field(default="postgres", description="PostgreSQL Username")
    POSTGRES_PASSWORD: Optional[SecretStr] = Field(default=None, description="PostgreSQL Password")
    POSTGRES_HOST: str = Field(default="localhost", description="PostgreSQL Host")
    POSTGRES_PORT: int = Field(default=5432, description="PostgreSQL Port")
    POSTGRES_DB: str = Field(default="ecommerce_crawler", description="PostgreSQL Database Name")
    
    DATABASE_URL: Optional[SecretStr] = Field(default=None, description="Custom Async Connection URL")
    SYNC_DATABASE_URL: Optional[SecretStr] = Field(default=None, description="Custom Sync Connection URL")

    @property
    def async_db_url(self) -> str:
        """Tạo chuỗi kết nối Async PostgreSQL (asyncpg) an toàn"""
        if self.DATABASE_URL:
            return self.DATABASE_URL.get_secret_value()
        pwd = self.POSTGRES_PASSWORD.get_secret_value() if self.POSTGRES_PASSWORD else ""
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{pwd}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    @property
    def sync_db_url(self) -> str:
        """Tạo chuỗi kết nối Sync PostgreSQL (psycopg2) an toàn"""
        if self.SYNC_DATABASE_URL:
            return self.SYNC_DATABASE_URL.get_secret_value()
        pwd = self.POSTGRES_PASSWORD.get_secret_value() if self.POSTGRES_PASSWORD else ""
        return f"postgresql://{self.POSTGRES_USER}:{pwd}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # Crawler Settings
    CRAWLER_HEADLESS: bool = True
    CRAWLER_MIN_DELAY: float = 2.0
    CRAWLER_MAX_DELAY: float = 5.0
    CRAWLER_MAX_RETRIES: int = 3
    CRAWLER_TIMEOUT_SECONDS: int = 30
    CRAWLER_ROTATE_USER_AGENT: bool = True
    
    # Proxy Settings
    USE_PROXY: bool = False
    PROXY_URL: Optional[SecretStr] = None
    ADB_DEVICE_ID: Optional[str] = None

    # Telegram Bot
    TELEGRAM_BOT_TOKEN: Optional[SecretStr] = None
    TELEGRAM_CHAT_ID: Optional[str] = None
    TELEGRAM_NOTIFY_ON_PRICE_DROP: bool = True
    PRICE_DROP_ALERT_THRESHOLD_PERCENT: float = 5.0
    WATCHLIST_CRON_INTERVAL_MINUTES: int = 30  # Chu kỳ chạy Cron Job quét giá Watchlist (mặc định 30 phút)

    # Redis Cloud Configuration
    REDIS_HOST: str = Field(default="localhost", description="Redis Host")
    REDIS_PORT: int = Field(default=6379, description="Redis Port")
    REDIS_PASSWORD: Optional[SecretStr] = Field(default=None, description="Redis Password")
    REDIS_USERNAME: Optional[str] = Field(default=None, description="Redis Username")
    REDIS_DB: int = Field(default=0, description="Redis Database Number")
    REDIS_DECODE_RESPONSE: bool = True
    
    # Tiered TTL Settings (Tần suất biến động giá sàn TMĐT)
    CACHE_HOT_TTL_SECONDS: int = 7200          # 2 giờ cho giá deal Flash Sale / Gợi ý sản phẩm
    CACHE_CHITCHAT_TTL_SECONDS: int = 86400    # 24 giờ cho câu chào hỏi
    JOB_TTL_SECONDS: int = 86400               # 24 giờ cho lịch sử Job cào dữ liệu trên Redis

    # AI Engine API Keys
    GEMINI_API_KEY: Optional[SecretStr] = None
    OPENAI_API_KEY: Optional[SecretStr] = None
    NVIDIA_API_KEY: Optional[SecretStr] = None
    NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.com/v1"

    # Qdrant Cloud Vector Database
    QDRANT_API_KEY: Optional[SecretStr] = None
    QDRANT_CLUSTER_ENDPOINT: Optional[str] = None
    QDRANT_COLLECTION_NAME: str = "products"
    DEFAULT_AI_MODEL: str = "meta/llama-3.1-8b-instruct"

    def get_redis_password(self) -> Optional[str]:
        """Lấy raw Redis Password an toàn"""
        return self.REDIS_PASSWORD.get_secret_value() if self.REDIS_PASSWORD else None

    def get_gemini_api_key(self) -> Optional[str]:
        """Lấy raw Gemini API Key an toàn"""
        return self.GEMINI_API_KEY.get_secret_value() if self.GEMINI_API_KEY else None

    def get_nvidia_api_key(self) -> Optional[str]:
        """Lấy raw NVIDIA API Key an toàn"""
        return self.NVIDIA_API_KEY.get_secret_value() if self.NVIDIA_API_KEY else None

    def get_telegram_token(self) -> Optional[str]:
        """Lấy raw Telegram Bot Token an toàn"""
        return self.TELEGRAM_BOT_TOKEN.get_secret_value() if self.TELEGRAM_BOT_TOKEN else None

    def get_qdrant_api_key(self) -> Optional[str]:
        """Lấy raw Qdrant API Key an toàn"""
        return self.QDRANT_API_KEY.get_secret_value() if self.QDRANT_API_KEY else None


settings = Settings()

