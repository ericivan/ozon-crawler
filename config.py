from typing import Literal, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_NAME: str = "ozon_analyzer"
    DB_USER: str = "root"
    DB_PASS: str = ""

    # Anthropic
    ANTHROPIC_API_KEY: str = ""

    # Proxy
    PROXY_ENABLED: bool = False
    PROXY_TYPE: Literal["http", "https", "socks5"] = "http"
    PROXY_HOST: Optional[str] = None
    PROXY_PORT: Optional[int] = None
    PROXY_USER: Optional[str] = None
    PROXY_PASS: Optional[str] = None

    # Scraper
    SCRAPE_DELAY_MIN: float = 2.0
    SCRAPE_DELAY_MAX: float = 5.0
    SCRAPE_MAX_PAGES: int = 3

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @field_validator("PROXY_TYPE", mode="before")
    @classmethod
    def normalize_proxy_type(cls, value: str) -> str:
        if value is None:
            return "http"
        return str(value).lower().strip()

    @property
    def db_url(self) -> str:
        return (
            f"mysql+aiomysql://{self.DB_USER}:{self.DB_PASS}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"
        )

    @property
    def proxy_url(self) -> Optional[str]:
        if not self.PROXY_ENABLED or not self.PROXY_HOST or not self.PROXY_PORT:
            return None
        scheme = self.PROXY_TYPE.lower()
        if self.PROXY_USER and self.PROXY_PASS:
            return f"{scheme}://{self.PROXY_USER}:{self.PROXY_PASS}@{self.PROXY_HOST}:{self.PROXY_PORT}"
        return f"{scheme}://{self.PROXY_HOST}:{self.PROXY_PORT}"


settings = Settings()
