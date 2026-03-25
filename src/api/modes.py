"""
云端模式管理 — 从 VPS 拉取可用模式列表，每个模式对应一套系统提示词。
"""

import logging
import os
import threading
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# ---- 内置默认模式（VPS 不可用时 fallback） ----

_BUILTIN_MODES: list[dict] = [
    {
        "id": "default",
        "name": "通用助手",
        "description": "智能对话，帮你完成各种任务",
        "icon": "bot",
        "templates": [
            {"title": "帮我选题", "description": "根据你的兴趣推荐论文题目", "icon": "lightbulb", "message": "我是经济学本科生，请帮我选一个合适的毕业论文题目。我对宏观经济感兴趣，请给我几个方向建议。"},
            {"title": "文献综述", "description": "搜索真实学术文献，生成综述", "icon": "book-open", "message": "请帮我围绕「数字经济对就业结构的影响」这个主题，搜索相关文献并撰写一段文献综述。"},
            {"title": "数据分析", "description": "获取经济数据，运行回归分析", "icon": "bar-chart-3", "message": "请帮我获取中国近20年的GDP和城镇化率数据，并做一个简单的回归分析，看看两者的关系。"},
            {"title": "论文写作", "description": "按学术规范生成 Word 论文", "icon": "file-edit", "message": "请帮我生成一篇关于「人口老龄化对消费结构影响」的论文开题报告，包含研究背景、意义、文献综述提纲和研究方法。"},
        ],
    },
    {
        "id": "thesis",
        "name": "论文辅导",
        "description": "毕业论文全流程：选题、文献、数据、写作",
        "icon": "graduation-cap",
        "templates": [
            {"title": "帮我选题", "description": "根据兴趣推荐合适的毕业论文题目", "icon": "lightbulb", "message": "我是经济学本科生，请帮我选一个合适的毕业论文题目。我对宏观经济感兴趣，请给我几个方向建议。"},
            {"title": "文献综述", "description": "搜索真实文献并撰写综述", "icon": "book-open", "message": "请帮我围绕「数字经济对就业结构的影响」这个主题，搜索相关文献并撰写一段文献综述。"},
            {"title": "数据分析", "description": "获取数据并运行计量回归", "icon": "bar-chart-3", "message": "请帮我获取中国近20年的GDP和城镇化率数据，并做一个简单的回归分析，看看两者的关系。"},
            {"title": "论文写作", "description": "生成 Word 格式论文章节", "icon": "file-edit", "message": "请帮我生成一篇关于「人口老龄化对消费结构影响」的论文开题报告，包含研究背景、意义、文献综述提纲和研究方法。"},
        ],
    },
    {
        "id": "homework",
        "name": "写作业",
        "description": "解题思路讲解与作业辅导",
        "icon": "pencil-line",
        "templates": [
            {"title": "解题辅导", "description": "一步步讲解经济学习题", "icon": "calculator", "message": "请帮我解答这道微观经济学题目：假设某商品的需求函数为 Qd=100-2P，供给函数为 Qs=20+3P，求均衡价格和均衡数量。"},
            {"title": "概念解释", "description": "用通俗语言解释经济学概念", "icon": "book-open", "message": "请用通俗易懂的语言解释「边际效用递减规律」，并举一个生活中的例子。"},
            {"title": "作业检查", "description": "检查作业答案是否正确", "icon": "check-circle", "message": "请帮我检查这道宏观经济学计算题的答案是否正确，并指出错误。"},
            {"title": "知识总结", "description": "整理章节知识点", "icon": "file-text", "message": "请帮我整理「IS-LM 模型」这一章的核心知识点，用表格形式列出。"},
        ],
    },
    {
        "id": "ppt",
        "name": "做 PPT",
        "description": "生成演示文稿大纲和内容",
        "icon": "presentation",
        "templates": [
            {"title": "论文答辩 PPT", "description": "生成毕业论文答辩演示稿", "icon": "graduation-cap", "message": "请帮我生成一份毕业论文答辩 PPT 的大纲和内容，我的论文题目是「数字经济对就业结构的影响研究」。"},
            {"title": "课堂展示", "description": "制作课堂小组展示 PPT", "icon": "presentation", "message": "请帮我制作一份关于「中国碳达峰碳中和政策」的课堂展示 PPT 大纲，10 分钟演讲。"},
            {"title": "研究汇报", "description": "制作研究进度汇报 PPT", "icon": "bar-chart-3", "message": "请帮我制作一份研究进度汇报 PPT，我目前完成了文献综述和数据收集阶段。"},
        ],
    },
]

# ---- 缓存 ----

_lock = threading.Lock()
_modes: list[dict] = []
_loaded = False
_active_mode_id: str = "default"


def _config_url() -> str:
    base = os.environ.get("NEW_API_URL", "http://43.128.44.82:3000/v1")
    base = base.removesuffix("/v1").removesuffix("/")
    return f"{base}/config/modes.json"


def load_modes() -> list[dict]:
    """从 VPS 拉取模式列表。启动时调用一次。"""
    global _loaded, _modes
    url = _config_url()
    try:
        resp = httpx.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        modes = data.get("modes", [])
        if isinstance(modes, list) and len(modes) > 0:
            with _lock:
                _modes = modes
                _loaded = True
            logger.info("从云端加载了 %d 个模式", len(modes))
            return modes
    except Exception as e:
        logger.warning("从 %s 加载模式失败: %s（将使用内置模式）", url, e)

    # Fallback to built-in
    with _lock:
        _modes = list(_BUILTIN_MODES)
        _loaded = True
    return _modes


def get_modes() -> list[dict]:
    """返回可用模式列表。"""
    if not _loaded:
        load_modes()
    with _lock:
        return list(_modes) if _modes else list(_BUILTIN_MODES)


def get_active_mode_id() -> str:
    """返回当前激活的模式 ID。"""
    with _lock:
        return _active_mode_id


def set_active_mode(mode_id: str) -> Optional[dict]:
    """设置当前模式，返回该模式信息（含 system_prompt）。None 表示未找到。"""
    global _active_mode_id
    modes = get_modes()
    for m in modes:
        if m["id"] == mode_id:
            with _lock:
                _active_mode_id = mode_id
            return m
    return None


def get_active_mode_prompt() -> Optional[str]:
    """返回当前激活模式的 system_prompt，如果没有则返回 None（使用默认）。"""
    modes = get_modes()
    mid = get_active_mode_id()
    for m in modes:
        if m["id"] == mid:
            return m.get("system_prompt")
    return None
