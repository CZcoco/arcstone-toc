"""
服务端 Key 池管理

启动时从 VPS 拉取 /config/keys.json，缓存到内存，轮询分配。
VPS 端只需 Caddy 托管一个静态 JSON 文件：

    {
      "tavily": ["tvly-xxx", "tvly-yyy"],
      "mineru": ["mineru-xxx", "mineru-yyy"]
    }

更新 key 只需修改 VPS 上的 JSON 文件，客户端重启后自动生效。
"""
import os
import threading
import itertools
import logging

import httpx

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_pools: dict[str, list[str]] = {}  # {"tavily": [...], "mineru": [...]}
_cycles: dict[str, itertools.cycle] = {}
_loaded = False


def _config_url() -> str:
    """Key 配置 JSON 的 URL，从 NEW_API_URL 推导"""
    base = os.environ.get("NEW_API_URL", "http://43.128.44.82:3000/v1")
    base = base.removesuffix("/v1").removesuffix("/")
    return f"{base}/config/keys.json"


def load_keys():
    """从 VPS 拉取 key 配置。启动时调用一次。"""
    global _loaded
    url = _config_url()
    try:
        resp = httpx.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        with _lock:
            for name in ("tavily", "mineru"):
                keys = data.get(name, [])
                if isinstance(keys, list):
                    _pools[name] = [k for k in keys if isinstance(k, str) and k.strip()]
                    logger.info("Key 池 [%s]: 从服务器加载 %d 个 key", name, len(_pools[name]))
            _cycles.clear()  # 重置 cycle
            _loaded = True
    except Exception as e:
        logger.warning("从 %s 加载 key 池失败: %s（将使用本地环境变量）", url, e)
        _loaded = True  # 标记已尝试，避免重复请求


def get_key(service: str) -> str:
    """获取指定服务的下一个 key（轮询）。

    优先级：服务器池 > 环境变量（逗号分隔） > 单个环境变量
    返回空字符串表示无可用 key。
    """
    if not _loaded:
        load_keys()

    with _lock:
        # 如果池里有 key，从 cycle 里取
        pool = _pools.get(service, [])
        if pool:
            if service not in _cycles:
                _cycles[service] = itertools.cycle(pool)
            return next(_cycles[service])

    # Fallback: 环境变量
    env_name = service.upper()
    multi = os.environ.get(f"{env_name}_API_KEYS", "")
    if multi:
        keys = [k.strip() for k in multi.split(",") if k.strip()]
        if keys:
            with _lock:
                _pools[service] = keys
                _cycles[service] = itertools.cycle(keys)
            return keys[0]

    return os.environ.get(f"{env_name}_API_KEY", "")
