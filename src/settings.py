"""
Arcstone-econ 设置管理

用户配置存 data/settings.json（flat key-value，和 env var 同名）。
启动时：先 load_dotenv() 加载 .env，再从 settings.json 覆盖到 os.environ。
所有现有代码继续用 os.getenv()，零改动。
"""
import json
import os
import threading
from pathlib import Path

_lock = threading.Lock()

# 备份 .env 原始值，用于"清空设置时恢复"
_env_backup: dict[str, str] = {}

SETTINGS_SCHEMA = [
    {
        "group": "模型 API",
        "keys": [
            {"key": "DEEPSEEK_API_KEY", "label": "DeepSeek", "sensitive": True},
            {"key": "MOONSHOT_API_KEY", "label": "Kimi (Moonshot)", "sensitive": True},
            {"key": "DASHSCOPE_API_KEY", "label": "通义千问 / 百炼", "sensitive": True},
            {"key": "ANTHROPIC_AUTH_TOKEN", "label": "Claude（API额度）", "sensitive": True},
            {"key": "ANTHROPIC_SUB_TOKEN", "label": "Claude（订阅）", "sensitive": True},
            {"key": "OPENAI_API_KEY", "label": "GPT-5.4", "sensitive": True},
            {"key": "TAVILY_API_KEY", "label": "Tavily 搜索", "sensitive": True},
            {"key": "MINERU_API_KEY", "label": "MinerU PDF 解析", "sensitive": True},
        ],
    },
    {
        "group": "百炼知识库",
        "keys": [
            {"key": "ALIBABA_CLOUD_ACCESS_KEY_ID", "label": "阿里云 AccessKey ID", "sensitive": True},
            {"key": "ALIBABA_CLOUD_ACCESS_KEY_SECRET", "label": "阿里云 AccessKey Secret", "sensitive": True},
            {"key": "BAILIAN_WORKSPACE_ID", "label": "业务空间 ID", "sensitive": False},
        ],
    },
]

# 所有可配置 key 的集合
_ALL_KEYS: set[str] = set()
_SENSITIVE_KEYS: set[str] = set()
for _g in SETTINGS_SCHEMA:
    for _k in _g["keys"]:
        _ALL_KEYS.add(_k["key"])
        if _k["sensitive"]:
            _SENSITIVE_KEYS.add(_k["key"])


def _settings_path(data_dir: str) -> Path:
    return Path(data_dir) / "settings.json"


def load_settings(data_dir: str) -> dict[str, str]:
    p = _settings_path(data_dir)
    if not p.exists():
        return {}
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {k: v for k, v in data.items() if isinstance(k, str) and isinstance(v, str)}
    except Exception:
        return {}


def save_settings(data_dir: str, settings: dict[str, str]):
    p = _settings_path(data_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        with open(p, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)


def apply_settings_to_environ(data_dir: str):
    """启动时调用：将 settings.json 中的值覆盖到 os.environ，并备份 .env 原值。"""
    settings = load_settings(data_dir)
    for key in _ALL_KEYS:
        current = os.environ.get(key, "")
        if current:
            _env_backup[key] = current
    for key, value in settings.items():
        if key in _ALL_KEYS and value.strip():
            os.environ[key] = value.strip()


def mask_value(key: str, value: str) -> str:
    if not value:
        return ""
    if key not in _SENSITIVE_KEYS:
        return value
    if len(value) <= 4:
        return "****"
    return "****" + value[-4:]


def get_settings_for_api(data_dir: str) -> dict[str, str]:
    """返回当前生效值（settings.json 覆盖后的 os.environ），敏感值脱敏。"""
    result: dict[str, str] = {}
    for key in _ALL_KEYS:
        val = os.environ.get(key, "")
        if val:
            result[key] = mask_value(key, val)
    return result


def update_settings(data_dir: str, incoming: dict[str, str]) -> dict:
    """
    处理前端提交的设置。返回 {"ok": True, "needs_restart": bool, "changed_keys": [...]}。
    - 跳过 **** 开头的值（用户未修改）
    - 空值 → 从 settings.json 删除 + 恢复 .env 原值
    - 非空值 → 写入 settings.json + patch os.environ
    """
    current = load_settings(data_dir)
    changed_keys: list[str] = []

    for key, value in incoming.items():
        if key not in _ALL_KEYS:
            continue
        value = value.strip()  # 去掉粘贴时带入的前后空格
        # 用户未修改敏感字段
        if value.startswith("****"):
            continue

        if not value:
            # 清空：删除自定义值，恢复 .env 原值
            if key in current:
                del current[key]
                changed_keys.append(key)
            backup = _env_backup.get(key, "")
            if backup:
                os.environ[key] = backup
            elif key in os.environ:
                del os.environ[key]
        else:
            # 设置新值
            old = current.get(key, "")
            if old != value:
                current[key] = value
                changed_keys.append(key)
            os.environ[key] = value

    if changed_keys:
        save_settings(data_dir, current)

    return {"ok": True, "changed_keys": changed_keys}
