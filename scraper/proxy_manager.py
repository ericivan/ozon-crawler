import logging
from typing import Optional
from config import settings

logger = logging.getLogger(__name__)


class ProxyManager:
    """管理代理 IP 池，支持切换与重试逻辑。"""

    def __init__(self):
        self._attempts = 0
        self._max_attempts = 3

    def is_enabled(self) -> bool:
        return settings.PROXY_ENABLED and bool(settings.PROXY_HOST) and bool(settings.PROXY_PORT)

    def get_playwright_proxy(self) -> Optional[dict]:
        """返回 Playwright 格式的代理配置。"""
        if not self.is_enabled():
            if settings.PROXY_ENABLED:
                logger.warning("Proxy enabled but PROXY_HOST or PROXY_PORT is missing.")
            return None
        scheme = settings.PROXY_TYPE.lower()
        proxy: dict = {
            "server": f"{scheme}://{settings.PROXY_HOST}:{settings.PROXY_PORT}",
        }
        if settings.PROXY_USER and settings.PROXY_PASS:
            proxy["username"] = settings.PROXY_USER
            proxy["password"] = settings.PROXY_PASS
        logger.info(f"Using proxy: {proxy['server']}")
        return proxy

    def can_retry(self) -> bool:
        return self._attempts < self._max_attempts

    def record_attempt(self):
        self._attempts += 1

    def reset(self):
        self._attempts = 0

    @property
    def attempts(self) -> int:
        return self._attempts
