"""
Arcstone-econ API - SSE 流式输出封装

将 agent.stream() 的事件转换为 SSE 格式的事件生成器。

关键设计：agent.stream() 在独立线程中运行，通过 queue 传递事件。
用户点击停止时，通过 cancel_stream() 设置取消信号，agent 线程在下次 yield 时退出。
客户端断开时，detached flag 停止入队避免内存泄漏。
"""
import json
import os
import queue
import threading
import logging
import time
from typing import Generator

import httpx

from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage

logger = logging.getLogger(__name__)


def _extract_text(content) -> str:
    """从 message.content 提取纯文本。

    OpenAI 兼容模型返回 str，Anthropic 返回 list[{"type":"text","text":"..."}]。
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
        )
    return str(content)

_SENTINEL = object()  # 标记 agent 线程结束
_MAX_CONSECUTIVE_TOOL_FAILURES = 5  # 连续工具调用失败熔断阈值
_active_streams: dict[str, threading.Event] = {}  # thread_id → cancel event

_TOOL_ERROR_MARKERS = (
    "Field required", "validation error", "Error", "执行出错",
    "执行失败", "执行超时", "未找到", "Traceback",
)

MAX_API_RETRIES = 3


def sse_event(event_type: str, data: dict) -> str:
    """格式化单条 SSE 事件"""
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _run_agent(agent, user_input: str, config: dict, q: queue.Queue, detached: threading.Event,
               cancelled: threading.Event,
               images: list[str] | None = None, file_summaries: list[str] | None = None,
               model: str = "deepseek-chat", attachments: list[dict] | None = None,
               workspace_path: str | None = None):
    """在独立线程中执行 agent.stream()，将 SSE 事件推入 queue。

    cancelled 被 set 后立即停止迭代（用户主动停止）。
    detached 被 set 后停止入队，避免内存无限增长。
    """
    # 设置当前模型标识，供 read_image 等工具判断多模态能力
    os.environ["CURRENT_MODEL"] = model

    # 设置当前线程的工作区路径覆盖（并发会话隔离）
    from src.tools.path_resolver import set_thread_workspace
    set_thread_workspace(workspace_path)

    # 构建消息内容
    text_parts = []
    if file_summaries:
        text_parts.extend(file_summaries)
    if user_input:
        text_parts.append(user_input)
    full_text = "\n\n".join(text_parts)

    if images:
        if model.startswith("deepseek"):
            # DeepSeek 不支持图像，降级为纯文本
            content = "【提示：当前模型不支持图像识别，以下回答不包含图片内容分析】\n\n" + full_text
        else:
            # Claude 和 GPT 支持图像识别
            content = []
            if full_text:
                content.append({"type": "text", "text": full_text})
            for data_url in images:
                content.append({"type": "image_url", "image_url": {"url": data_url}})
    else:
        content = full_text

    current_tool_calls = {}
    consecutive_tool_failures = 0

    def emit(event: str):
        if not detached.is_set():
            q.put(event)

    try:
        msg_metadata = {}
        if attachments:
            msg_metadata["attachments"] = attachments
        user_msg = HumanMessage(content=content, metadata=msg_metadata)

        for attempt in range(MAX_API_RETRIES):
            try:
                for stream_mode, data in agent.stream(
                    {"messages": [user_msg]},
                    config=config,
                    stream_mode=["messages", "updates"],
                ):
                    if cancelled.is_set():
                        thread_id = config.get("configurable", {}).get("thread_id", "?")
                        logger.info("Agent cancelled by user (thread_id=%s)", thread_id)
                        emit(sse_event("done", {}))
                        return

                    if stream_mode == "messages":
                        token, metadata = data

                        if isinstance(token, AIMessageChunk):
                            if token.tool_call_chunks:
                                for tc in token.tool_call_chunks:
                                    call_id = tc.get("id") or tc.get("index", "")
                                    if call_id and call_id not in current_tool_calls:
                                        current_tool_calls[call_id] = True
                                        emit(sse_event("thinking", {}))
                            elif hasattr(token, "content") and token.content:
                                text = _extract_text(token.content)
                                if text:
                                    emit(sse_event("text_chunk", {"content": text}))

                    elif stream_mode == "updates":
                        if not isinstance(data, dict):
                            continue
                        for node_name, update in data.items():
                            if not isinstance(update, dict):
                                continue
                            if node_name == "tools":
                                messages = update.get("messages", [])
                                for msg in messages:
                                    if isinstance(msg, ToolMessage):
                                        content = _extract_text(msg.content)
                                        # 连续工具失败熔断
                                        is_error = any(m in content for m in _TOOL_ERROR_MARKERS)
                                        if is_error:
                                            consecutive_tool_failures += 1
                                            logger.warning(
                                                "Tool call failed (%d/%d): %s → %s",
                                                consecutive_tool_failures, _MAX_CONSECUTIVE_TOOL_FAILURES,
                                                msg.name, content[:200],
                                            )
                                            if consecutive_tool_failures >= _MAX_CONSECUTIVE_TOOL_FAILURES:
                                                emit(sse_event("tool_result", {
                                                    "id": msg.tool_call_id,
                                                    "name": msg.name,
                                                    "content": content,
                                                }))
                                                emit(sse_event("error", {
                                                    "message": f"连续 {_MAX_CONSECUTIVE_TOOL_FAILURES} 次工具调用失败，已自动停止。请检查模型或重试。",
                                                }))
                                                emit(sse_event("done", {}))
                                                return
                                        else:
                                            consecutive_tool_failures = 0
                                        emit(sse_event("tool_result", {
                                            "id": msg.tool_call_id,
                                            "name": msg.name,
                                            "content": content,
                                        }))
                            elif node_name in ("agent", "model"):
                                messages = update.get("messages", [])
                                for msg in messages:
                                    if isinstance(msg, AIMessage) and msg.tool_calls:
                                        for tc in msg.tool_calls:
                                            emit(sse_event("tool_call", {
                                                "id": tc.get("id", ""),
                                                "name": tc["name"],
                                                "args": tc["args"],
                                            }))

                break  # 正常结束，跳出重试循环
            except (httpx.TimeoutException, httpx.HTTPStatusError) as e:
                if attempt < MAX_API_RETRIES - 1:
                    wait = 2 ** attempt
                    logger.warning("API error (attempt %d/%d), retrying in %ds: %s",
                                  attempt + 1, MAX_API_RETRIES, wait, e)
                    emit(sse_event("error", {"message": f"API 暂时不可用，{wait}秒后自动重试..."}))
                    time.sleep(wait)
                else:
                    raise

        emit(sse_event("done", {}))
    except Exception as e:
        logger.error("Agent stream error: %s", e, exc_info=True)
        err_msg = str(e)
        if "<!DOCTYPE" in err_msg or "<html" in err_msg:
            err_msg = "API 服务暂时不可用（502），可能是额度耗尽或服务异常，请稍后重试或更换模型。"
        emit(sse_event("error", {"message": err_msg}))
    finally:
        q.put(_SENTINEL)


def cancel_stream(thread_id: str) -> bool:
    """设置取消信号，让 agent 线程在下次 yield 时退出。"""
    ev = _active_streams.get(thread_id)
    if ev:
        ev.set()
        return True
    return False


def stream_to_sse(agent, user_input: str, config: dict,
                  images: list[str] | None = None,
                  file_summaries: list[str] | None = None,
                  model: str = "deepseek-chat",
                  attachments: list[dict] | None = None,
                  workspace_path: str | None = None) -> Generator[str, None, None]:
    """将 agent.stream() 转换为 SSE 事件流。

    用户点击停止时，cancel_stream() 设置取消信号，agent 线程在下次 yield 时退出。
    客户端断开时，detached flag 停止入队避免内存泄漏。
    """
    q: queue.Queue = queue.Queue()
    detached = threading.Event()
    cancelled = threading.Event()
    thread_id = config.get("configurable", {}).get("thread_id", "")
    if thread_id:
        _active_streams[thread_id] = cancelled

    thread = threading.Thread(
        target=_run_agent,
        args=(agent, user_input, config, q, detached, cancelled),
        kwargs={"images": images, "file_summaries": file_summaries, "model": model,
                "attachments": attachments, "workspace_path": workspace_path},
        daemon=True,
    )
    thread.start()

    try:
        while True:
            event = q.get()
            if event is _SENTINEL:
                break
            yield event
    except GeneratorExit:
        # 客户端断开（退出/切换会话），agent 继续跑完保存 checkpoint
        detached.set()
        logger.info("SSE client disconnected (thread_id=%s)", thread_id or "?")
    finally:
        _active_streams.pop(thread_id, None)
