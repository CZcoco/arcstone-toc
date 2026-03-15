"""
记忆语义搜索工具

让 Agent 通过自然语言搜索自己的记忆文件。
混合检索：向量余弦相似度 (70%) + BM25 关键词匹配 (30%)。
"""

from langchain_core.tools import tool

from src.memory_search import get_global_search_engine


@tool
def memory_search(query: str, top_k: int = 5) -> str:
    """搜索记忆文件，找到与查询最相关的内容。

    使用语义理解 + 关键词匹配的混合检索，比逐个读取文件高效得多。

    使用场景：
        - 需要从记忆中查找相关项目信息，但不确定存在哪个文件
        - 用户提到某个话题，需要快速定位相关记忆
        - 对话开始时，根据用户消息快速检索相关背景

    参数：
        query: 搜索问题，如 "铜矿项目的品位数据" 或 "用户的投资偏好"
        top_k: 返回结果数量，默认 5

    返回：
        匹配的记忆文件列表，包含文件路径、相关度评分和内容摘要。
        需要详细内容请用 read_file 读取对应文件。

    注意：
        - 返回的是文件路径和摘要，需要详细内容请用 read_file 读取
        - 不会搜索 index.md（索引文件）
    """
    engine = get_global_search_engine()
    if engine is None:
        return "记忆搜索引擎未初始化。"
    if hasattr(engine, "available") and not engine.available:
        return engine.status_message()

    results = engine.search(query=query, top_k=top_k)

    if not results:
        return "未找到相关记忆文件。"

    lines = []
    for i, r in enumerate(results, 1):
        path = r["key"]
        score = r["score"]
        snippet = r["snippet"] or "(无关键词匹配摘要)"
        lines.append(f"{i}. **{path}** (相关度: {score:.2f})\n   {snippet}")

    return f"找到 {len(results)} 个相关记忆文件：\n" + "\n".join(lines)
