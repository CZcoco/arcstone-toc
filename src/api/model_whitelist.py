"""
模型白名单 — 从 VPS 拉取允许的模型列表，过滤 New API 返回的全量模型。
"""
import logging
import os
import threading

import httpx

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_whitelist: list[str] | None = None
_loaded = False


def _config_url() -> str:
    base = os.environ.get("NEW_API_URL", "http://43.128.44.82:3000/v1")
    base = base.removesuffix("/v1").removesuffix("/")
    return f"{base}/config/models.json"


def load_whitelist():
    """从 VPS 拉取模型白名单。启动时调用一次。"""
    global _loaded, _whitelist
    url = _config_url()
    try:
        resp = httpx.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        wl = data.get("whitelist", [])
        if isinstance(wl, list) and len(wl) > 0:
            with _lock:
                _whitelist = [m for m in wl if isinstance(m, str) and m.strip()]
            logger.info("模型白名单: %s", _whitelist)
        else:
            logger.info("模型白名单为空，不过滤")
        _loaded = True
    except Exception as e:
        logger.warning("从 %s 加载模型白名单失败: %s（不过滤）", url, e)
        _loaded = True


def get_whitelist() -> list[str] | None:
    """返回白名单列表。None 或空列表表示不过滤。"""
    if not _loaded:
        load_whitelist()
    with _lock:
        return list(_whitelist) if _whitelist else None
