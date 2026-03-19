"""
虚拟路径 → 真实磁盘路径 转换

Agent 内部使用虚拟路径（/workspace/xxx, /memories/xxx），
但 subprocess 工具（run_python, read_pdf）运行在操作系统上，需要真实路径。
本模块提供统一转换。

并发隔离：通过 threading.local() 支持 per-thread 的 /workspace/ 路径覆盖，
不同会话的工具线程各自解析到自己的工作区目录。
"""
import os
import threading

# 虚拟前缀 → 真实根目录的映射，由 app 启动时设置（全局默认值）
_VIRTUAL_ROOTS: dict[str, str] = {}

# per-thread 的 /workspace/ 路径覆盖
_thread_local = threading.local()


def set_virtual_root(prefix: str, real_dir: str) -> None:
    """注册一个虚拟前缀到真实目录的映射。

    Args:
        prefix: 虚拟路径前缀，如 "/workspace/"
        real_dir: 对应的真实磁盘目录
    """
    if not prefix.endswith("/"):
        prefix += "/"
    _VIRTUAL_ROOTS[prefix] = os.path.normpath(real_dir)


def set_thread_workspace(path: str | None) -> None:
    """设置当前线程的 /workspace/ 覆盖路径。None 表示清除。"""
    _thread_local.workspace = path


def _get_effective_roots() -> dict[str, str]:
    """返回当前线程生效的虚拟路径映射。

    如果线程本地有 workspace 覆盖，用它替代全局的 /workspace/ 映射。
    其他前缀（/memories/, /skills/）不受影响。
    """
    ws = getattr(_thread_local, "workspace", None)
    if ws:
        return {**_VIRTUAL_ROOTS, "/workspace/": os.path.normpath(ws)}
    return _VIRTUAL_ROOTS


def resolve_virtual_path(path: str) -> str:
    """将虚拟路径转为真实磁盘路径。非虚拟路径原样返回。

    Args:
        path: 可能是虚拟路径（/workspace/report.pdf）或真实路径

    Returns:
        真实磁盘路径
    """
    normalized = path.replace("\\", "/")
    for prefix, real_dir in _get_effective_roots().items():
        if normalized.startswith(prefix):
            relative = normalized[len(prefix):].lstrip("/")
            return os.path.normpath(os.path.join(real_dir, relative))
    return path


def resolve_virtual_paths_in_code(code: str) -> str:
    """替换代码字符串中所有虚拟路径引用为真实磁盘路径。

    Args:
        code: Python 代码字符串

    Returns:
        替换后的代码
    """
    result = code
    for prefix, real_dir in _get_effective_roots().items():
        # 替换正斜杠版本
        real_forward = real_dir.replace("\\", "/")
        result = result.replace(prefix, real_forward + "/")
    return result
