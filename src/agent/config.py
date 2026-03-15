"""
模型配置
"""
import os
import re
from typing import Any, ClassVar, Literal, NotRequired, Protocol, TypedDict, cast

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import LanguageModelInput
from langchain_openai import ChatOpenAI
from pydantic import SecretStr


class CompatChatOpenAI(ChatOpenAI):
    """为兼容性较弱的 OpenAI 兼容中转做请求层修正。"""

    _INVALID_ID_CHARS_RE: ClassVar[re.Pattern[str]] = re.compile(r"[^A-Za-z0-9_-]+")

    @staticmethod
    def _flatten_system_content(content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        parts.append(str(block.get("text", "")))
                    else:
                        parts.append(str(block.get("text", "") or block))
                else:
                    parts.append(str(block))
            return "".join(parts)
        return "" if content is None else str(content)

    @classmethod
    def _sanitize_compat_id(cls, value: Any, *, fallback: str) -> str:
        text = "" if value is None else str(value)
        sanitized = cls._INVALID_ID_CHARS_RE.sub("-", text.strip()).strip("-")
        return sanitized or fallback

    def _normalize_gpt_messages(
        self,
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        normalized_messages: list[dict[str, Any]] = []
        tool_call_id_map: dict[str, str] = {}
        next_tool_call_index = 1

        def map_tool_call_id(raw_id: Any) -> str:
            nonlocal next_tool_call_index
            raw_key = "" if raw_id is None else str(raw_id)
            if raw_key in tool_call_id_map:
                return tool_call_id_map[raw_key]
            mapped = f"call_{next_tool_call_index}"
            next_tool_call_index += 1
            tool_call_id_map[raw_key] = mapped
            return mapped

        for message in messages:
            if not isinstance(message, dict):
                normalized_messages.append(message)
                continue

            normalized = dict(message)
            normalized.pop("id", None)

            if (
                normalized.get("role") == "system"
                and isinstance(normalized.get("content"), list)
            ):
                normalized["content"] = self._flatten_system_content(normalized["content"])

            if normalized.get("role") == "assistant" and isinstance(
                normalized.get("tool_calls"), list
            ):
                normalized_tool_calls: list[dict[str, Any]] = []
                for tool_call in normalized["tool_calls"]:
                    if not isinstance(tool_call, dict):
                        normalized_tool_calls.append(tool_call)
                        continue
                    normalized_tool_call = dict(tool_call)
                    normalized_tool_call["id"] = map_tool_call_id(
                        normalized_tool_call.get("id")
                    )
                    normalized_tool_calls.append(normalized_tool_call)
                normalized["tool_calls"] = normalized_tool_calls

            if normalized.get("role") == "tool":
                normalized["tool_call_id"] = map_tool_call_id(
                    self._sanitize_compat_id(
                        normalized.get("tool_call_id"),
                        fallback=f"call_{next_tool_call_index}",
                    )
                )

            normalized_messages.append(normalized)

        return normalized_messages

    def _get_request_payload(
        self,
        input_: LanguageModelInput,
        *,
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        payload = super()._get_request_payload(input_, stop=stop, **kwargs)
        messages = payload.get("messages")
        if isinstance(messages, list):
            payload["messages"] = self._normalize_gpt_messages(messages)
        return payload


class ModelConfigEntry(TypedDict):
    model: str
    env_key: str
    base_url: str
    provider: NotRequired[Literal["anthropic"]]
    extra_body: NotRequired[dict[str, object]]
    default_headers: NotRequired[dict[str, str]]
    timeout: NotRequired[int]
    max_retries: NotRequired[int]
    max_input_tokens: NotRequired[int]
    temperature: NotRequired[float]
    frequency_penalty: NotRequired[float]
    betas: NotRequired[list[str]]


class AnthropicFactory(Protocol):
    def __call__(
        self,
        *,
        model: str,
        api_key: SecretStr,
        base_url: str,
        default_headers: dict[str, str],
        betas: list[str] | None = None,
    ) -> ChatAnthropic: ...


class OpenAIFactory(Protocol):
    def __call__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: SecretStr,
        extra_body: dict[str, object] | None,
        default_headers: dict[str, str] | None,
        timeout: int | None,
        max_retries: int | None,
        temperature: float | None,
        frequency_penalty: float | None,
    ) -> ChatOpenAI: ...


MODEL_CONFIG: dict[str, ModelConfigEntry] = {
    "gpt": {
        "base_url": "https://apiport.cc.cd/v1",
        "model": "gpt-5.4",
        "env_key": "OPENAI_API_KEY",
        "extra_body": {"reasoning_effort": "xhigh"},
        "default_headers": {"User-Agent": "curl/8.0"},
        "timeout": 120,
        "max_retries": 3,
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
        # "base_url": "https://cc.honoursoft.cn",
        "base_url": "https://apicn.ai",
        "env_key": "ANTHROPIC_AUTH_TOKEN",
    },
    "claude-sonnet": {
        "provider": "anthropic",
        "model": "claude-sonnet-4-6",
        # "base_url": "https://cc.honoursoft.cn",
        "base_url": "https://apicn.ai",
        "env_key": "ANTHROPIC_AUTH_TOKEN",
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


def get_llm(model_name: str = "claude-sonnet") -> ChatOpenAI | ChatAnthropic:
    """获取 LLM 实例"""
    if model_name not in MODEL_CONFIG:
        raise ValueError(f"未知模型: {model_name}，可用: {list(MODEL_CONFIG.keys())}")

    config = MODEL_CONFIG[model_name]
    api_key = os.getenv(config["env_key"])

    if not api_key:
        raise ValueError(f"缺少 API Key，请设置环境变量: {config['env_key']}")

    secret_api_key = SecretStr(api_key)

    if config.get("provider") == "anthropic":
        # anthropic SDK 会自动读 ANTHROPIC_AUTH_TOKEN 环境变量，加上 Authorization: Bearer header。
        # 当多个 Anthropic 模型用不同 key 时，Bearer token 会串。
        # 用 default_headers 强制覆盖，确保只用当前模型的 key。
        default_headers = {
            "x-api-key": api_key,
            "Authorization": "",  # 清掉 SDK 自动加的错误 Bearer token
            "User-Agent": "curl/8.0",
        }
        anthropic_factory = cast(AnthropicFactory, cast(object, ChatAnthropic))
        if "betas" in config:
            return anthropic_factory(
                model=config["model"],
                api_key=secret_api_key,
                base_url=config["base_url"],
                default_headers=default_headers,
                betas=config["betas"],
            )
        return anthropic_factory(
            model=config["model"],
            api_key=secret_api_key,
            base_url=config["base_url"],
            default_headers=default_headers,
        )

    extra_body = config["extra_body"] if "extra_body" in config else None
    default_headers = config["default_headers"] if "default_headers" in config else None
    timeout = config["timeout"] if "timeout" in config else None
    max_retries = config["max_retries"] if "max_retries" in config else None
    temperature = config["temperature"] if "temperature" in config else None
    frequency_penalty = config["frequency_penalty"] if "frequency_penalty" in config else None

    openai_factory_cls: type[ChatOpenAI] = CompatChatOpenAI if model_name == "gpt" else ChatOpenAI
    openai_factory = cast(OpenAIFactory, cast(object, openai_factory_cls))
    llm = openai_factory(
        base_url=config["base_url"],
        model=config["model"],
        api_key=secret_api_key,
        extra_body=extra_body,
        default_headers=default_headers,
        timeout=timeout,
        max_retries=max_retries,
        temperature=temperature,
        frequency_penalty=frequency_penalty,
    )
    # 注入 profile 让 SummarizationMiddleware 走 fraction 分支（0.85 触发）
    # 否则走硬编码 170k tokens，超过 128K 窗口永远不触发
    if "max_input_tokens" in config:
        llm.profile = {"max_input_tokens": config["max_input_tokens"]}
    return llm
