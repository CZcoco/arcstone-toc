"""百炼知识库检索工具 - 通过服务端代理访问"""
import os
import httpx
from langchain_core.tools import tool


@tool
def bailian_rag(query: str) -> str:
    """从知识库中检索相关摘要和文献信息。

    参数：
        query: 检索问题

    返回：
        检索到的相关内容
    """
    rag_url = os.environ.get("RAG_PROXY_URL", "http://43.128.44.82:3000/rag/retrieve")

    try:
        resp = httpx.post(
            rag_url,
            json={"query": query},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [])
        if not results:
            return "未检索到相关内容"
        texts = [r.get("text", "") for r in results if r.get("text")]
        return "\n\n---\n\n".join(texts) if texts else "未检索到相关内容"
    except Exception as e:
        return f"知识库检索失败: {e}"
