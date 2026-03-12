"""
模型配置
"""
import os
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic

MODEL_CONFIG = {
    "gpt": {
        "base_url": "https://chat.apiport.cc.cd/v1",
        "model": "gpt-5.4",
        "env_key": "OPENAI_API_KEY",
        "extra_body": {"reasoning_effort": "xhigh"},
    },
    "claude-opus-plan": {
        "provider": "anthropic",
        "model": "claude-opus-4-6",
        "base_url": "https://apiport.cc.cd",
        "env_key": "ANTHROPIC_SUB_TOKEN",
    },
    "claude-sonnet-plan": {
        "provider": "anthropic",
        "model": "claude-sonnet-4-6",
        "base_url": "https://apiport.cc.cd",
        "env_key": "ANTHROPIC_SUB_TOKEN",
    },
    "claude-opus": {
        "provider": "anthropic",
        "model": "claude-opus-4-6",
        "base_url": "https://cc.honoursoft.cn",
        "env_key": "ANTHROPIC_AUTH_TOKEN",
    },
    "claude-sonnet": {
        "provider": "anthropic",
        "model": "claude-sonnet-4-6",
        "base_url": "https://cc.honoursoft.cn",
        "env_key": "ANTHROPIC_AUTH_TOKEN",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",  # 已对应 DeepSeek V3.2
        "env_key": "DEEPSEEK_API_KEY",
        "max_input_tokens": 131072,  # 128K，注入 profile 让摘要在 85% (~111K) 触发
        "extra_kwargs": {"frequency_penalty": 0.3},
    },
    "kimi": {
        "base_url": "https://api.moonshot.cn/v1",
        "model": "kimi-k2.5",
        "env_key": "MOONSHOT_API_KEY",
        # 关闭 thinking 模式：ChatOpenAI 会丢弃 reasoning_content，导致多轮工具调用报错
        # 官方 API 用 {"thinking": {"type": "disabled"}}，vLLM 用 chat_template_kwargs
        "extra_body": {"thinking": {"type": "disabled"}},
        "extra_kwargs": {"temperature": 0.6},
    },
    #"qwen": {
    #    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    #    "model": "qwen3.5-plus",
    #    "env_key": "DASHSCOPE_API_KEY",
    #    "extra_body": {"enable_thinking": False},
    #},


    #"claude-sonnet-1m": {
    #    "provider": "anthropic",
    #    "model": "claude-sonnet-4-6",
    #    "base_url": "https://cc.honoursoft.cn",
    #    "env_key": "ANTHROPIC_AUTH_TOKEN",
    #    "betas": ["context-1m-2025-08-07"],
    #},
}


def get_llm(model_name: str = "claude-sonnet"):
    """获取 LLM 实例"""
    if model_name not in MODEL_CONFIG:
        raise ValueError(f"未知模型: {model_name}，可用: {list(MODEL_CONFIG.keys())}")

    config = MODEL_CONFIG[model_name]
    api_key = os.getenv(config["env_key"])

    if not api_key:
        raise ValueError(f"缺少 API Key，请设置环境变量: {config['env_key']}")

    if config.get("provider") == "anthropic":
        # anthropic SDK 会自动读 ANTHROPIC_AUTH_TOKEN 环境变量，加上 Authorization: Bearer header。
        # 当多个 Anthropic 模型用不同 key 时，Bearer token 会串。
        # 用 default_headers 强制覆盖，确保只用当前模型的 key。
        kwargs = {
            "model": config["model"],
            "api_key": api_key,
            "default_headers": {
                "x-api-key": api_key,
                "Authorization": "",  # 清掉 SDK 自动加的错误 Bearer token
            },
        }
        if config.get("base_url"):
            kwargs["base_url"] = config["base_url"]
        if config.get("betas"):
            kwargs["betas"] = config["betas"]
        return ChatAnthropic(**kwargs)

    llm = ChatOpenAI(
        base_url=config["base_url"],
        model=config["model"],
        api_key=api_key,
        extra_body=config.get("extra_body"),
        **config.get("extra_kwargs", {}),
    )
    # 注入 profile 让 SummarizationMiddleware 走 fraction 分支（0.85 触发）
    # 否则走硬编码 170k tokens，超过 128K 窗口永远不触发
    if config.get("max_input_tokens"):
        llm.profile = {"max_input_tokens": config["max_input_tokens"]}
    return llm
