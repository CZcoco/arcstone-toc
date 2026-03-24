"""
模型配置 - ToC 版（所有调用走 New API）
"""
import os
import logging

from langchain_openai import ChatOpenAI
from pydantic import SecretStr

logger = logging.getLogger(__name__)

# New API 服务器地址
NEW_API_BASE_URL = os.environ.get("NEW_API_URL", "http://43.128.44.82:3000/v1")


def get_llm(model_name: str = "deepseek-chat") -> ChatOpenAI:
    """获取 LLM 实例 - 所有模型统一走 New API（OpenAI 兼容格式）

    model_name: New API 中配置的模型 ID（如 "deepseek-chat", "claude-sonnet-4-6"）
    认证：使用 ECON_USER_TOKEN 环境变量（用户登录后自动设置的 New API token）
    """
    api_key = os.environ.get("ECON_USER_TOKEN", "")
    if not api_key:
        raise ValueError("未登录：缺少用户 token（ECON_USER_TOKEN）")

    return ChatOpenAI(
        base_url=NEW_API_BASE_URL,
        model=model_name,
        api_key=SecretStr(api_key),
        timeout=120,
        max_retries=3,
    )
