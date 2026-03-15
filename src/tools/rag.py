"""
百炼知识库检索工具 - 支持多知识库检索

知识库配置通过 set_rag_kb_configs() 动态更新，
前端切换知识库时调用 POST /api/kb/rag/config 同步。
"""
import os
import threading
from langchain_core.tools import tool

# 全局知识库配置：[{index_id, name, description}]
# 由 API 层在用户切换知识库时更新
_rag_kb_configs: list[dict] = []
_rag_lock = threading.Lock()


def set_rag_kb_configs(configs: list[dict]):
    """更新 RAG 使用的知识库列表"""
    global _rag_kb_configs
    with _rag_lock:
        _rag_kb_configs = list(configs)


def get_rag_kb_configs() -> list[dict]:
    with _rag_lock:
        return list(_rag_kb_configs)


def _init_default_config():
    """用环境变量初始化默认知识库（如果还没有配置）"""
    if _rag_kb_configs:
        return
    index_id = os.environ.get("BAILIAN_INDEX_ID")
    if index_id:
        set_rag_kb_configs([{
            "index_id": index_id,
            "name": "默认知识库",
            "description": "",
        }])


@tool
def bailian_rag(query: str) -> str:
    """从用户配置的百炼知识库中检索信息。

    知识库内容由用户自行上传和管理，可能包含各类文档资料。
    工具会自动检索所有已配置的知识库并汇总结果。

    参数：
        query: 检索问题

    返回：
        检索到的相关内容（来自所有已配置的知识库）
    """
    workspace_id = os.environ.get("BAILIAN_WORKSPACE_ID")
    if not workspace_id:
        return "知识库未配置：缺少 BAILIAN_WORKSPACE_ID"

    _init_default_config()
    configs = get_rag_kb_configs()
    if not configs:
        return "知识库未配置：没有可用的知识库"

    try:
        mgr = _get_cached_manager()
    except RuntimeError as e:
        return f"知识库功能不可用：{e}"
    except Exception as e:
        return f"知识库连接失败: {e}"

    all_results = []
    for kb in configs:
        index_id = kb["index_id"]
        kb_name = kb.get("name", index_id)
        try:
            text = mgr.retrieve(query, index_id=index_id)
            if text:
                all_results.append(f"--- 来自知识库「{kb_name}」---\n{text}")
        except Exception as e:
            all_results.append(f"--- 知识库「{kb_name}」检索失败: {e} ---")

    if all_results:
        return "\n\n".join(all_results)
    return "未检索到相关内容，可能需要补充相关资料到知识库。"


# 缓存 BailianKBManager 实例
_cached_manager = None
_manager_lock = threading.Lock()


def _get_cached_manager():
    global _cached_manager
    if _cached_manager is None:
        with _manager_lock:
            if _cached_manager is None:
                try:
                    from src.tools.kb_uploader import BailianKBManager
                except ImportError as e:
                    raise RuntimeError("缺少百炼知识库依赖") from e
                _cached_manager = BailianKBManager()
    return _cached_manager
