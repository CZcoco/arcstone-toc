"""
联网搜索工具 - 使用 Tavily API（key 从服务端池获取）
"""
import threading
from langchain_core.tools import tool

from src.api.key_pool import get_key

_client_lock = threading.Lock()


def _get_client():
    """获取 TavilyClient，使用 key 池轮询的 key"""
    try:
        from tavily import TavilyClient
    except ImportError as e:
        raise RuntimeError("缺少 tavily-python 依赖") from e

    api_key = get_key("tavily")
    if not api_key:
        raise ValueError("缺少 Tavily API Key（服务端 key 池为空，且未设置 TAVILY_API_KEY 环境变量）")
    return TavilyClient(api_key=api_key)


@tool
def internet_search(query: str, search_depth: str = "advanced") -> str:
    """搜索互联网获取最新信息。

    使用场景：
    - 查询大宗商品实时价格（铜价、镍价、锂价等）
    - 搜索最新政策法规变化
    - 获取行业新闻和动态
    - 搜集竞品项目公开资料

    参数：
        query: 搜索关键词，如 "2026年铜价走势"
        search_depth: 搜索深度，"basic"（快速）或 "advanced"（深入）

    返回：
        搜索结果摘要
    """
    try:
        client = _get_client()
        response = client.search(
            query=query,
            search_depth=search_depth,
            include_answer=True,
            max_results=5,
        )

        results = []
        if response.get("answer"):
            results.append(f"**摘要**: {response['answer']}\n")

        for item in response.get("results", []):
            title = item.get("title", "")
            content = item.get("content", "")
            results.append(f"- {title}: {content[:300]}")

        return "\n".join(results) if results else "未找到相关结果"

    except ValueError as e:
        return f"搜索未配置：{e}"
    except RuntimeError as e:
        return f"搜索功能不可用：{e}"
    except Exception as e:
        return f"搜索失败: {str(e)}"


_MAX_EXTRACT = 30_000  # 网页抓取最大输出字符数


@tool
def fetch_website(urls: list[str], extract_depth: str = "basic") -> str:
    """抓取网页内容，提取正文文本。

    使用场景：
    - 用户给了一个网址，需要读取网页内容
    - 从搜索结果中深入阅读某篇文章
    - 抓取政策文件、公告、报告等网页全文

    参数：
        urls: 要抓取的网址列表，最多 20 个
        extract_depth: 抓取深度，"basic"（快速）或 "advanced"（深入，适合 JS 渲染页面）

    返回：
        各网页的正文内容
    """
    try:
        client = _get_client()
        response = client.extract(
            urls=urls,
            extract_depth=extract_depth,
            format="markdown",
        )

        parts = []
        for item in response.get("results", []):
            url = item.get("url", "")
            content = item.get("raw_content", "")
            if content:
                if len(content) > _MAX_EXTRACT:
                    content = content[:_MAX_EXTRACT] + f"\n\n... (内容已截断，共 {len(content)} 字符)"
                parts.append(f"## {url}\n\n{content}")

        for item in response.get("failed_results", []):
            url = item.get("url", "")
            error = item.get("error", "未知错误")
            parts.append(f"## {url}\n\n抓取失败: {error}")

        return "\n\n---\n\n".join(parts) if parts else "未能提取到任何内容"

    except ValueError as e:
        return f"搜索未配置：{e}"
    except RuntimeError as e:
        return f"网页抓取功能不可用：{e}"
    except Exception as e:
        return f"网页抓取失败: {str(e)}"
