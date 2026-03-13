"""
Arcstone-econ API - 路由

所有涉及阻塞 IO（agent.stream / SQLite）的端点用 def（非 async def），
FastAPI 会自动在线程池中执行，不阻塞事件循环。
"""
import uuid
import sqlite3
import base64
import threading
import logging
import os
import re
import shutil
from typing import Optional
from datetime import datetime, timezone

import subprocess

from fastapi import APIRouter, Request, UploadFile, File, Form, Query
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
from pydantic import BaseModel

from src.api.stream import stream_to_sse, _extract_text
from src.tools.pdf_parser import parse_pdf, parse_pdfs_batch
from src.agent.prompts import ECON_SYSTEM_PROMPT
from src.settings import SETTINGS_SCHEMA, get_settings_for_api, update_settings

_kb_logger = logging.getLogger(__name__ + ".kb")

_INDEX_KEY = "/index.md"
_INDEX_TEMPLATE = """\
# 记忆索引

## 用户画像
| 文件 | 摘要 | 更新时间 |
|------|------|---------|

## 项目
| 文件 | 摘要 | 更新时间 |
|------|------|---------|

## 决策
| 文件 | 摘要 | 更新时间 |
|------|------|---------|

## 文档
| 文件 | 摘要 | 更新时间 |
|------|------|---------|
"""


def _update_memory_index(store, file_path: str, summary: str, date: str):
    """更新 /memories/index.md 中某条记录。

    file_path: 相对路径如 "/documents/报告.md"
    summary:   该文件的摘要
    date:      更新日期如 "2026-02-18"
    """
    if file_path.startswith("/projects/"):
        section = "## 项目"
    elif file_path.startswith("/decisions/"):
        section = "## 决策"
    elif file_path.startswith("/documents/"):
        section = "## 文档"
    else:
        section = "## 用户画像"

    new_row = f"| {file_path} | {summary} | {date} |"

    # 读取现有 index.md
    item = store.get(("filesystem",), _INDEX_KEY)
    if item and isinstance(item.value, dict) and isinstance(item.value.get("content"), list):
        lines = list(item.value["content"])
    elif item and isinstance(item.value, dict):
        raw = item.value.get("data", "") or item.value.get("content", "")
        if isinstance(raw, list):
            raw = "\n".join(raw)
        lines = raw.split("\n")
    else:
        lines = _INDEX_TEMPLATE.split("\n")

    # 查找已有行并替换
    updated = False
    for i, line in enumerate(lines):
        if line.startswith(f"| {file_path} "):
            lines[i] = new_row
            updated = True
            break

    if not updated:
        # 找到目标 section，在其表格末尾插入
        section_idx = None
        for i, line in enumerate(lines):
            if line.strip() == section:
                section_idx = i
                break

        if section_idx is not None:
            # 跳过 section header + table header + separator = 3 lines
            insert_at = section_idx + 3
            while insert_at < len(lines) and lines[insert_at].startswith("| "):
                insert_at += 1
            lines.insert(insert_at, new_row)
        else:
            lines.append(new_row)

    now_iso = datetime.now(timezone.utc).isoformat()
    store.put(("filesystem",), _INDEX_KEY, {
        "content": lines,
        "created_at": now_iso,
        "modified_at": now_iso,
    })


router = APIRouter()
_MAX_BATCH_UPLOAD_FILES = 100

# 图片临时存储：image_id -> base64 data URL（进程内存，用完即弃）
_image_store: dict[str, str] = {}

ARCHIVE_PROMPT = (
    "请回顾我们这次的完整对话，将有价值的信息归档到 /memories/。具体要求：\n"
    "1. 如果讨论了具体项目，将项目的关键数据、分析结论、待办事项完整写入 /memories/projects/{项目名}.md\n"
    "2. 如果有投资决策，写入 /memories/decisions/{日期}_{项目}_{决策}.md\n"
    "3. 如果发现了新的用户偏好或我纠正了你的错误，更新 /memories/user_profile.md 或 /memories/instructions.md\n"
    "4. 归档内容要详细、有结构，包含具体数据和数字，不要只写结论\n"
    "请直接执行归档，完成后简要告诉我归档了哪些内容。"
)

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def _get_agent(request: Request, model: str = "deepseek"):
    """从 AgentManager 获取指定模型的 agent"""
    return request.app.state.agent_manager.get(model)


def _get_shared(request: Request):
    """获取共享的 store 和 checkpointer"""
    return request.app.state.store, request.app.state.checkpointer


# --- Models ---

class AttachmentMeta(BaseModel):
    name: str
    type: str  # "pdf" | "excel" | "doc" | "md" | "image"
    path: str | None = None


class ChatRequest(BaseModel):
    message: str
    thread_id: str
    model: Optional[str] = "deepseek"
    image_ids: list[str] = []
    file_summaries: list[str] = []
    attachments: list[AttachmentMeta] = []


class ResendRequest(BaseModel):
    message: str
    thread_id: str
    message_index: int
    model: Optional[str] = "deepseek"


class CancelRequest(BaseModel):
    thread_id: str


class SessionNewResponse(BaseModel):
    thread_id: str


class ArchiveRequest(BaseModel):
    thread_id: str
    model: Optional[str] = "deepseek"


class RenameRequest(BaseModel):
    thread_id: str
    title: str


# --- Health ---

@router.get("/health")
async def health():
    return {"status": "ok"}


# --- Models ---

@router.get("/models")
def list_models(request: Request):
    manager = request.app.state.agent_manager
    return {"models": manager.available_models()}


# --- Chat ---

@router.post("/chat/stream")
def chat_stream(req: ChatRequest, request: Request):
    agent = _get_agent(request, req.model)
    store = request.app.state.store
    config = {"configurable": {"thread_id": req.thread_id}}
    images = [_image_store.pop(iid, None) for iid in req.image_ids]
    images = [img for img in images if img]

    # 首次发消息时存 preview（轻量，不反序列化 checkpoint）
    _set_session_preview(store, req.thread_id, _extract_text(req.message))

    return StreamingResponse(
        stream_to_sse(agent, req.message, config,
                      images=images,
                      file_summaries=req.file_summaries,
                      model=req.model or "deepseek",
                      attachments=[a.model_dump() for a in req.attachments]),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


@router.post("/chat/resend")
def chat_resend(req: ResendRequest, request: Request):
    """编辑并重发：回退到第 message_index 条用户消息之前的状态，重新发送。"""
    agent = _get_agent(request, req.model)
    config = {"configurable": {"thread_id": req.thread_id}}

    target_config = None
    for i, snapshot in enumerate(agent.get_state_history(config)):
        if i >= 500:
            break
        msgs = snapshot.values.get("messages", [])
        human_count = sum(1 for m in msgs if getattr(m, "type", "") == "human")
        if human_count <= req.message_index:
            target_config = snapshot.config
            break

    if target_config is None:
        target_config = config

    return StreamingResponse(
        stream_to_sse(agent, req.message, target_config),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


@router.post("/chat/cancel")
def cancel_chat(req: CancelRequest):
    """取消正在运行的 agent stream。"""
    from src.api.stream import cancel_stream
    return {"cancelled": cancel_stream(req.thread_id)}


# --- Archive ---

@router.post("/archive")
def archive(req: ArchiveRequest, request: Request):
    agent = _get_agent(request, req.model)
    config = {"configurable": {"thread_id": req.thread_id}}

    return StreamingResponse(
        stream_to_sse(agent, ARCHIVE_PROMPT, config),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


# --- Session ---

def _get_session_meta(store, thread_id: str) -> dict:
    item = store.get(("session_meta",), thread_id)
    if item and isinstance(item.value, dict):
        return item.value
    return {}


def _get_session_title(store, thread_id: str) -> str:
    return _get_session_meta(store, thread_id).get("title", "")


def _set_session_title(store, thread_id: str, title: str):
    meta = _get_session_meta(store, thread_id)
    meta["title"] = title
    store.put(("session_meta",), thread_id, meta)


def _set_session_preview(store, thread_id: str, preview: str):
    """首次发消息时存 preview，后续不覆盖。"""
    meta = _get_session_meta(store, thread_id)
    if not meta.get("preview"):
        meta["preview"] = preview[:100]
        store.put(("session_meta",), thread_id, meta)


@router.post("/session/new")
def session_new():
    return SessionNewResponse(thread_id=str(uuid.uuid4()))


@router.get("/session/list")
def session_list(request: Request):
    store, checkpointer = _get_shared(request)
    conn: sqlite3.Connection = checkpointer.conn

    try:
        rows = conn.execute(
            "SELECT thread_id, MAX(checkpoint_id) AS last_cp "
            "FROM checkpoints GROUP BY thread_id ORDER BY last_cp DESC"
        ).fetchall()
    except sqlite3.OperationalError:
        return {"sessions": []}

    sessions = []
    for tid, _last_cp in rows:
        meta = _get_session_meta(store, tid)
        sessions.append({
            "thread_id": tid,
            "title": meta.get("title", ""),
            "preview": meta.get("preview", ""),
        })

    return {"sessions": sessions}


@router.post("/session/rename")
def session_rename(req: RenameRequest, request: Request):
    store, _ = _get_shared(request)
    _set_session_title(store, req.thread_id, req.title.strip())
    return {"ok": True}


@router.delete("/session/{thread_id}")
def session_delete(thread_id: str, request: Request):
    store, checkpointer = _get_shared(request)
    conn: sqlite3.Connection = checkpointer.conn

    try:
        conn.execute("DELETE FROM checkpoints WHERE thread_id = ?", (thread_id,))
        conn.execute("DELETE FROM writes WHERE thread_id = ?", (thread_id,))
        conn.commit()
    except sqlite3.OperationalError:
        pass

    store.delete(("session_meta",), thread_id)
    return {"ok": True}


@router.get("/session/{thread_id}")
def session_history(thread_id: str, request: Request):
    _, checkpointer = _get_shared(request)
    config = {"configurable": {"thread_id": thread_id}}
    checkpoint = checkpointer.get(config)

    if not checkpoint or "channel_values" not in checkpoint:
        return {"messages": []}

    raw_messages = checkpoint["channel_values"].get("messages", [])
    messages = []
    for msg in raw_messages:
        role = getattr(msg, "type", "unknown")
        if role == "human":
            role = "user"
        elif role == "ai":
            role = "assistant"
        elif role == "tool":
            messages.append({
                "role": "tool",
                "name": getattr(msg, "name", ""),
                "tool_call_id": getattr(msg, "tool_call_id", ""),
                "content": _extract_text(msg.content),
            })
            continue
        else:
            continue

        entry = {
            "role": role,
            "content": _extract_text(msg.content),
        }

        # user 消息：从 metadata 提取附件信息
        if role == "user":
            meta = getattr(msg, "metadata", None) or {}
            if meta.get("attachments"):
                entry["attachments"] = meta["attachments"]

        if role == "assistant" and hasattr(msg, "tool_calls") and msg.tool_calls:
            entry["tool_calls"] = [
                {"id": tc.get("id", ""), "name": tc["name"], "args": tc["args"]}
                for tc in msg.tool_calls
            ]

        messages.append(entry)

    return {"messages": messages}


# --- Memory ---

@router.get("/memory/list")
def memory_list(request: Request):
    store, _ = _get_shared(request)
    items = store.search(("filesystem",), limit=100)
    return {
        "items": [
            {
                "key": item.key,
                "updated_at": item.updated_at.isoformat() if item.updated_at else "",
            }
            for item in items
        ]
    }


@router.get("/memory/{key:path}")
def memory_detail(key: str, request: Request):
    store, _ = _get_shared(request)
    if not key.startswith("/"):
        key = "/" + key
    item = store.get(("filesystem",), key)
    if item is None:
        return {"key": key, "content": ""}
    value = item.value
    if isinstance(value, dict):
        # StoreBackend 格式：{"content": [lines], ...}
        if isinstance(value.get("content"), list):
            content = "\n".join(value["content"])
        else:
            content = value.get("data", "") or value.get("content", "")
    else:
        content = str(value)
    return {"key": key, "content": content}


class MemoryUpdateRequest(BaseModel):
    content: str


class MemoryRenameRequest(BaseModel):
    old_key: str
    new_name: str


class SystemPromptRequest(BaseModel):
    content: str


class PromptVersionCreateRequest(BaseModel):
    name: str
    content: str = ""


class PromptVersionUpdateRequest(BaseModel):
    name: str | None = None
    content: str | None = None


@router.put("/memory/{key:path}")
def memory_update(key: str, req: MemoryUpdateRequest, request: Request):
    """更新记忆文件内容。"""
    store, _ = _get_shared(request)
    if not key.startswith("/"):
        key = "/" + key
    now = datetime.now(timezone.utc).isoformat()
    store.put(("filesystem",), key, {
        "content": req.content.split("\n"),
        "created_at": now,
        "modified_at": now,
    })
    return {"ok": True}


@router.delete("/memory/{key:path}")
def memory_delete(key: str, request: Request):
    """删除记忆文件。"""
    store, _ = _get_shared(request)
    if not key.startswith("/"):
        key = "/" + key
    store.delete(("filesystem",), key)
    return {"ok": True}


@router.post("/memory/rename")
def memory_rename(req: MemoryRenameRequest, request: Request):
    """重命名记忆文件。保留原目录，只改文件名。"""
    store, _ = _get_shared(request)
    old_key = req.old_key
    if not old_key.startswith("/"):
        old_key = "/" + old_key

    # 提取目录部分，拼新 key
    parts = old_key.rsplit("/", 1)
    directory = parts[0] if len(parts) > 1 else ""
    new_name = req.new_name.strip()
    if not new_name:
        return {"ok": False, "error": "文件名不能为空"}
    if not new_name.endswith(".md"):
        new_name += ".md"
    new_key = f"{directory}/{new_name}"

    if new_key == old_key:
        return {"ok": True, "new_key": new_key}

    # 检查新 key 是否已存在
    existing = store.get(("filesystem",), new_key)
    if existing and existing.value:
        return {"ok": False, "error": "该文件名已存在"}

    # 读取旧内容 → 写入新 key → 删除旧 key
    old_item = store.get(("filesystem",), old_key)
    if old_item is None:
        return {"ok": False, "error": "原文件不存在"}

    now = datetime.now(timezone.utc).isoformat()
    value = old_item.value
    if isinstance(value, dict):
        value["modified_at"] = now
    store.put(("filesystem",), new_key, value)
    store.delete(("filesystem",), old_key)

    # 更新记忆索引：删除旧行，添加新行
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    _update_memory_index(store, new_key, new_name.replace(".md", ""), today)

    return {"ok": True, "new_key": new_key}


# --- System Prompt (多版本) ---

def _get_prompt_versions(store) -> list[dict]:
    """获取所有提示词版本列表"""
    saved = store.get(("settings",), "prompt_versions")
    if saved and isinstance(saved.value, dict):
        return saved.value.get("versions", [])
    return []


def _save_prompt_versions(store, versions: list[dict]):
    store.put(("settings",), "prompt_versions", {"versions": versions})


def _get_active_prompt_id(store) -> str | None:
    saved = store.get(("settings",), "active_prompt_id")
    if saved and isinstance(saved.value, dict):
        return saved.value.get("id")
    return None


def _set_active_prompt_id(store, vid: str | None):
    if vid:
        store.put(("settings",), "active_prompt_id", {"id": vid})
    else:
        store.delete(("settings",), "active_prompt_id")


def _migrate_old_prompt(store) -> list[dict]:
    """如果存在旧的单一 system_prompt 但没有 versions，自动迁移"""
    versions = _get_prompt_versions(store)
    if versions:
        return versions
    # 检查旧格式
    old = store.get(("settings",), "system_prompt")
    if old and isinstance(old.value, dict) and old.value.get("content"):
        vid = uuid.uuid4().hex[:8]
        now = datetime.now(timezone.utc).isoformat()
        versions = [{
            "id": vid,
            "name": "自定义提示词",
            "content": old.value["content"],
            "created_at": now,
            "updated_at": now,
        }]
        _save_prompt_versions(store, versions)
        _set_active_prompt_id(store, vid)
        store.delete(("settings",), "system_prompt")
    return versions


@router.get("/system-prompt/versions")
def list_prompt_versions(request: Request):
    """列出所有提示词版本"""
    store, _ = _get_shared(request)
    versions = _migrate_old_prompt(store)
    active_id = _get_active_prompt_id(store)
    return {"versions": versions, "active_id": active_id}


@router.post("/system-prompt/versions")
def create_prompt_version(req: PromptVersionCreateRequest, request: Request):
    """新建提示词版本"""
    store, _ = _get_shared(request)
    versions = _migrate_old_prompt(store)
    vid = uuid.uuid4().hex[:8]
    now = datetime.now(timezone.utc).isoformat()
    v = {
        "id": vid,
        "name": req.name.strip() or "未命名",
        "content": req.content,
        "created_at": now,
        "updated_at": now,
    }
    versions.append(v)
    _save_prompt_versions(store, versions)
    return {"ok": True, "version": v}


@router.put("/system-prompt/versions/{vid}")
def update_prompt_version(vid: str, req: PromptVersionUpdateRequest, request: Request):
    """更新提示词版本（名称和/或内容）"""
    store, _ = _get_shared(request)
    versions = _migrate_old_prompt(store)
    for v in versions:
        if v["id"] == vid:
            if req.name is not None:
                v["name"] = req.name.strip() or v["name"]
            if req.content is not None:
                v["content"] = req.content
            v["updated_at"] = datetime.now(timezone.utc).isoformat()
            _save_prompt_versions(store, versions)
            # 如果更新的是激活版本，同步到 agent
            active_id = _get_active_prompt_id(store)
            if active_id == vid:
                manager = request.app.state.agent_manager
                manager.set_system_prompt(v["content"] if v["content"] else None)
            return {"ok": True, "version": v}
    return JSONResponse({"ok": False, "error": "版本不存在"}, status_code=404)


@router.delete("/system-prompt/versions/{vid}")
def delete_prompt_version(vid: str, request: Request):
    """删除提示词版本"""
    store, _ = _get_shared(request)
    versions = _migrate_old_prompt(store)
    new_versions = [v for v in versions if v["id"] != vid]
    if len(new_versions) == len(versions):
        return JSONResponse({"ok": False, "error": "版本不存在"}, status_code=404)
    _save_prompt_versions(store, new_versions)
    # 如果删除的是激活版本，重置为默认
    active_id = _get_active_prompt_id(store)
    if active_id == vid:
        _set_active_prompt_id(store, None)
        manager = request.app.state.agent_manager
        manager.set_system_prompt(None)
    return {"ok": True}


@router.post("/system-prompt/activate/{vid}")
def activate_prompt_version(vid: str, request: Request):
    """激活某个提示词版本"""
    store, _ = _get_shared(request)
    versions = _migrate_old_prompt(store)
    manager = request.app.state.agent_manager
    # vid == "default" 表示切回内置默认
    if vid == "default":
        _set_active_prompt_id(store, None)
        manager.set_system_prompt(None)
        return {"ok": True}
    for v in versions:
        if v["id"] == vid:
            _set_active_prompt_id(store, vid)
            manager.set_system_prompt(v["content"] if v["content"] else None)
            return {"ok": True}
    return JSONResponse({"ok": False, "error": "版本不存在"}, status_code=404)


@router.get("/system-prompt")
def get_system_prompt(request: Request):
    """获取当前激活的系统提示词（兼容旧接口）"""
    store, _ = _get_shared(request)
    versions = _migrate_old_prompt(store)
    active_id = _get_active_prompt_id(store)
    if active_id:
        for v in versions:
            if v["id"] == active_id and v["content"]:
                return {"content": v["content"], "is_default": False}
    return {"content": ECON_SYSTEM_PROMPT, "is_default": True}


@router.put("/system-prompt")
def update_system_prompt(req: SystemPromptRequest, request: Request):
    """更新激活版本的内容（兼容旧接口）"""
    store, _ = _get_shared(request)
    manager = request.app.state.agent_manager
    content = req.content.strip()
    if not content:
        _set_active_prompt_id(store, None)
        manager.set_system_prompt(None)
        return {"ok": True}
    # 如果有激活版本，更新它；否则新建一个
    versions = _migrate_old_prompt(store)
    active_id = _get_active_prompt_id(store)
    now = datetime.now(timezone.utc).isoformat()
    if active_id:
        for v in versions:
            if v["id"] == active_id:
                v["content"] = content
                v["updated_at"] = now
                _save_prompt_versions(store, versions)
                manager.set_system_prompt(content)
                return {"ok": True}
    # 没有激活版本，新建
    vid = uuid.uuid4().hex[:8]
    versions.append({
        "id": vid, "name": "自定义提示词", "content": content,
        "created_at": now, "updated_at": now,
    })
    _save_prompt_versions(store, versions)
    _set_active_prompt_id(store, vid)
    manager.set_system_prompt(content)
    return {"ok": True}


# --- Upload ---

@router.post("/upload/pdf")
def upload_pdf(request: Request, file: UploadFile = File(...)):
    """上传 PDF，解析后存入 /memories/documents/。

    解析策略：MinerU API（优先） → pdfplumber（降级）。
    存储格式与 StoreBackend 一致，Agent 可用 ls/read_file 直接访问。
    """
    _ALLOWED_EXTS = (".pdf", ".doc", ".docx")
    if not file.filename or not any(file.filename.lower().endswith(ext) for ext in _ALLOWED_EXTS):
        return {"ok": False, "error": "请上传 PDF 或 Word 文件"}

    file_bytes = file.file.read()
    if not file_bytes:
        return {"ok": False, "error": "文件为空"}

    # 解析 PDF
    result = parse_pdf(file_bytes, file.filename)
    content = result["content"]
    warning = result.get("warning", "")
    if not content.strip():
        return {"ok": False, "error": warning or "PDF 无可提取的文本内容（可能是扫描件）"}

    # 添加元信息头
    base_name = file.filename.rsplit(".", 1)[0]
    header = (
        f"# {base_name}\n"
        f"- 来源：PDF 上传\n"
        f"- 页数：{result['pages']}\n"
        f"- 解析方式：{result['method']}\n"
        f"\n---\n\n"
    )
    full_content = header + content

    # 写入 StoreBackend 格式：{"content": [lines], "created_at": iso, "modified_at": iso}
    # 同名不同内容防冲突：已有同名文件且内容不同 → 加序号
    store, _ = _get_shared(request)
    store_key = f"/documents/{base_name}.md"
    try:
        existing = store.get(("filesystem",), store_key)
        if existing and existing.value:
            old_text = "\n".join(existing.value.get("content", []))
            if old_text.strip() != full_content.strip():
                # 内容不同，找下一个可用序号
                n = 2
                while True:
                    candidate = f"/documents/{base_name}_{n}.md"
                    ex = store.get(("filesystem",), candidate)
                    if not ex or not ex.value:
                        store_key = candidate
                        break
                    n += 1
    except Exception:
        pass  # store.get 失败不阻塞上传

    now = datetime.now(timezone.utc).isoformat()
    store.put(("filesystem",), store_key, {
        "content": full_content.split("\n"),
        "created_at": now,
        "modified_at": now,
    })

    # 更新记忆索引
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    _update_memory_index(store, store_key, f"{base_name}，{result['pages']}页，{result['method']}解析", today)

    return {
        "ok": True,
        "path": f"/memories/{store_key}",
        "pages": result["pages"],
        "chars": len(full_content),
        "method": result["method"],
    }


@router.post("/upload/pdfs")
def upload_pdfs_batch(request: Request, files: list[UploadFile] = File(...)):
    """批量上传文件（最多 100 个），存入 /memories/documents/。支持 PDF/DOC/DOCX/MD。"""
    if len(files) > _MAX_BATCH_UPLOAD_FILES:
        return {"results": [{"ok": False, "name": "", "error": f"最多同时上传 {_MAX_BATCH_UPLOAD_FILES} 个文件"}]}

    store, _ = _get_shared(request)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # 校验并读取文件，MD 直接处理，PDF/DOC 收集后批量解析
    pdf_files: list[tuple[bytes, str]] = []
    results_out: list[dict] = []
    valid_indices: list[int] = []

    for i, f in enumerate(files):
        _ALLOWED_EXTS = (".pdf", ".doc", ".docx", ".md")
        if not f.filename or not any(f.filename.lower().endswith(ext) for ext in _ALLOWED_EXTS):
            results_out.append({"ok": False, "name": f.filename or "", "error": "不支持的文件格式"})
            continue
        file_bytes = f.file.read()
        if not file_bytes:
            results_out.append({"ok": False, "name": f.filename, "error": "文件为空"})
            continue

        # MD 文件直接存入 store，无需解析
        if f.filename.lower().endswith(".md"):
            base_name = f.filename.rsplit(".", 1)[0]
            content = file_bytes.decode("utf-8", errors="replace")
            store_key = f"/documents/{base_name}.md"
            now = datetime.now(timezone.utc).isoformat()
            store.put(("filesystem",), store_key, {
                "content": content.split("\n"),
                "created_at": now,
                "modified_at": now,
            })
            _update_memory_index(store, store_key, f"{base_name}，Markdown 文档", today)
            results_out.append({
                "ok": True,
                "name": f.filename,
                "path": f"/memories{store_key}",
                "pages": None,
                "chars": len(content),
                "method": "markdown",
            })
            continue

        pdf_files.append((file_bytes, f.filename))
        results_out.append(None)  # placeholder
        valid_indices.append(i)

    if not pdf_files:
        return {"results": [r for r in results_out if r is not None]}

    # 批量解析 PDF/DOC
    parse_results = parse_pdfs_batch(pdf_files)

    for j, pr in enumerate(parse_results):
        idx = valid_indices[j]
        filename = pdf_files[j][1]
        base_name = filename.rsplit(".", 1)[0]

        content = pr["content"]
        warning = pr.get("warning", "")
        if not content.strip():
            results_out[idx] = {"ok": False, "name": filename, "error": warning or "PDF 无可提取的文本内容"}
            continue

        header_text = (
            f"# {base_name}\n"
            f"- 来源：PDF 上传\n"
            f"- 页数：{pr['pages']}\n"
            f"- 解析方式：{pr['method']}\n"
            f"\n---\n\n"
        )
        full_content = header_text + content

        # 同名冲突检测
        store_key = f"/documents/{base_name}.md"
        try:
            existing = store.get(("filesystem",), store_key)
            if existing and existing.value:
                old_text = "\n".join(existing.value.get("content", []))
                if old_text.strip() != full_content.strip():
                    n = 2
                    while True:
                        candidate = f"/documents/{base_name}_{n}.md"
                        ex = store.get(("filesystem",), candidate)
                        if not ex or not ex.value:
                            store_key = candidate
                            break
                        n += 1
        except Exception:
            pass

        now = datetime.now(timezone.utc).isoformat()
        store.put(("filesystem",), store_key, {
            "content": full_content.split("\n"),
            "created_at": now,
            "modified_at": now,
        })
        _update_memory_index(store, store_key, f"{base_name}，{pr['pages']}页，{pr['method']}解析", today)

        results_out[idx] = {
            "ok": True,
            "name": filename,
            "path": f"/memories{store_key}",
            "pages": pr["pages"],
            "chars": len(full_content),
            "method": pr["method"],
        }

    return {"results": [r for r in results_out if r is not None]}


@router.post("/upload/image")
def upload_image(file: UploadFile = File(...)):
    """上传图片，base64 编码后暂存内存，返回 image_id。"""
    _ALLOWED_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".gif")
    if not file.filename or not any(file.filename.lower().endswith(ext) for ext in _ALLOWED_EXTS):
        return {"ok": False, "error": "请上传图片文件（jpg/png/webp/gif）"}
    file_bytes = file.file.read()
    if not file_bytes:
        return {"ok": False, "error": "文件为空"}
    ext = file.filename.rsplit(".", 1)[-1].lower()
    mime = "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"
    data_url = f"data:{mime};base64,{base64.b64encode(file_bytes).decode()}"
    image_id = str(uuid.uuid4())
    _image_store[image_id] = data_url
    return {"ok": True, "image_id": image_id, "name": file.filename}


@router.post("/upload/excel")
def upload_excel(file: UploadFile = File(...)):
    """上传 Excel，保存到 data/tmp/ 并返回磁盘路径。"""
    _ALLOWED_EXTS = (".xlsx", ".xls")
    if not file.filename or not any(file.filename.lower().endswith(ext) for ext in _ALLOWED_EXTS):
        return {"ok": False, "error": "请上传 Excel 文件（xlsx/xls）"}
    file_bytes = file.file.read()
    if not file_bytes:
        return {"ok": False, "error": "文件为空"}

    from src.agent.main import DATA_DIR
    tmp_dir = os.path.join(DATA_DIR, "tmp")
    os.makedirs(tmp_dir, exist_ok=True)
    safe_name = f"{uuid.uuid4().hex[:8]}_{file.filename}"
    save_path = os.path.normpath(os.path.join(tmp_dir, safe_name))
    with open(save_path, "wb") as f:
        f.write(file_bytes)

    return {"ok": True, "name": file.filename, "path": save_path}



_ALLOWED_KB_EXTS = {
    ".pdf", ".docx", ".doc", ".txt", ".md",
    ".pptx", ".ppt", ".xlsx", ".xls", ".html",
    ".png", ".jpg", ".jpeg", ".bmp", ".gif",
}

# 内存中的上传任务状态
_kb_jobs: dict[str, dict] = {}


class KBDeleteRequest(BaseModel):
    document_ids: list[str]
    index_id: Optional[str] = None


class KBRagConfigRequest(BaseModel):
    configs: list[dict]  # [{index_id, name, description}]


@router.get("/kb/list")
def kb_list(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    index_id: Optional[str] = Query(None),
):
    kb_mgr = getattr(request.app.state, "kb_manager", None)
    if kb_mgr is None:
        return JSONResponse(status_code=503, content={"error": "知识库未配置"})
    return kb_mgr.list_documents(index_id=index_id, page=page, page_size=page_size)


@router.post("/kb/upload")
def kb_upload(
    request: Request,
    file: UploadFile = File(...),
    chunk_size: Optional[int] = Form(None),
    overlap_size: Optional[int] = Form(None),
    index_id: Optional[str] = Form(None),
):
    kb_mgr = getattr(request.app.state, "kb_manager", None)
    if kb_mgr is None:
        return JSONResponse(status_code=503, content={"error": "知识库未配置"})

    filename = file.filename or "unnamed"
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in _ALLOWED_KB_EXTS:
        return JSONResponse(
            status_code=400,
            content={"error": f"不支持的文件格式 {ext}，支持：{', '.join(sorted(_ALLOWED_KB_EXTS))}"},
        )

    file_bytes = file.file.read()
    if not file_bytes:
        return JSONResponse(status_code=400, content={"error": "文件为空"})

    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    _kb_jobs[job_id] = {
        "job_id": job_id,
        "filename": filename,
        "status": "uploading",
        "progress": "正在上传...",
        "error": None,
        "file_id": None,
        "created_at": now,
    }

    def _background_upload():
        job = _kb_jobs[job_id]
        try:
            result = kb_mgr.upload_file(file_bytes, filename)
            fid = result["file_id"]
            job["file_id"] = fid

            job["status"] = "parsing"
            job["progress"] = "正在解析文件..."
            parse_status = kb_mgr.poll_file_parse(fid)
            if parse_status != "PARSE_SUCCESS":
                job["status"] = "failed"
                job["error"] = f"文件解析失败: {parse_status}"
                return

            job["status"] = "indexing"
            job["progress"] = "正在建立索引..."
            idx_job_id = kb_mgr.submit_to_index(
                [fid],
                index_id=index_id,
                chunk_size=chunk_size,
                overlap_size=overlap_size,
            )
            idx_result = kb_mgr.poll_index_job(idx_job_id, index_id=index_id)
            if idx_result["status"] != "COMPLETED":
                job["status"] = "failed"
                err_msgs = [
                    f"{d['doc_name']}: {d['message']}"
                    for d in idx_result.get("documents", [])
                    if d.get("message")
                ]
                job["error"] = "索引失败" + (": " + "; ".join(err_msgs) if err_msgs else "")
                return

            job["status"] = "completed"
            job["progress"] = "完成"
        except Exception as e:
            _kb_logger.exception("KB upload failed for %s", filename)
            job["status"] = "failed"
            job["error"] = str(e)

    t = threading.Thread(target=_background_upload, daemon=True)
    t.start()

    return {"job_id": job_id, "filename": filename, "status": "uploading"}


@router.get("/kb/upload/status")
def kb_upload_status(job_id: str = Query(...)):
    job = _kb_jobs.get(job_id)
    if job is None:
        return JSONResponse(status_code=404, content={"error": "任务不存在"})
    return job


@router.delete("/kb/delete")
def kb_delete(req: KBDeleteRequest, request: Request):
    kb_mgr = getattr(request.app.state, "kb_manager", None)
    if kb_mgr is None:
        return JSONResponse(status_code=503, content={"error": "知识库未配置"})
    kb_mgr.delete_documents(req.document_ids, index_id=req.index_id)
    return {"ok": True}


@router.get("/kb/rag/config")
def kb_rag_config_get():
    from src.tools.rag import get_rag_kb_configs, _init_default_config
    _init_default_config()
    return {"configs": get_rag_kb_configs()}


@router.post("/kb/rag/config")
def kb_rag_config_set(req: KBRagConfigRequest):
    from src.tools.rag import set_rag_kb_configs
    set_rag_kb_configs(req.configs)
    return {"ok": True}


# --- Settings ---

class SettingsUpdateRequest(BaseModel):
    settings: dict[str, str]


@router.get("/settings/schema")
def settings_schema():
    return {"schema": SETTINGS_SCHEMA}


@router.get("/settings")
def settings_get(request: Request):
    from src.agent.main import DATA_DIR
    return {"settings": get_settings_for_api(DATA_DIR)}


@router.put("/settings")
def settings_update(req: SettingsUpdateRequest, request: Request):
    from src.agent.main import DATA_DIR
    result = update_settings(DATA_DIR, req.settings)

    changed = set(result.get("changed_keys", []))
    if not changed:
        return result

    # API Key 变更 → 清 agent 缓存
    api_key_keys = {
        "DEEPSEEK_API_KEY", "MOONSHOT_API_KEY", "DASHSCOPE_API_KEY",
        "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_SUB_TOKEN", "OPENAI_API_KEY",
        "TAVILY_API_KEY",
        "MINERU_API_KEY",
    }
    if changed & api_key_keys:
        request.app.state.agent_manager.invalidate_cache()

    # 百炼 ID 变更 → 重新实例化 KBManager
    bailian_keys = {"BAILIAN_WORKSPACE_ID", "ALIBABA_CLOUD_ACCESS_KEY_ID", "ALIBABA_CLOUD_ACCESS_KEY_SECRET"}
    if changed & bailian_keys:
        if os.environ.get("BAILIAN_WORKSPACE_ID") and os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_ID"):
            try:
                from src.tools.kb_uploader import BailianKBManager
                request.app.state.kb_manager = BailianKBManager()
            except Exception:
                request.app.state.kb_manager = None
        else:
            request.app.state.kb_manager = None

    return result


# --- Skills ---

def _get_skills_dir() -> str:
    from src.agent.main import SKILLS_DIR
    return SKILLS_DIR


def _parse_skill_md(path: str) -> dict:
    """解析 SKILL.md，提取 YAML frontmatter 中的 name 和 description。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except Exception:
        return {"name": "", "description": "", "content": ""}

    name = ""
    description = ""
    content = text

    # 解析 YAML frontmatter
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            frontmatter = text[3:end]
            content = text[end + 3:].lstrip("\n")
            for line in frontmatter.splitlines():
                if line.startswith("name:"):
                    name = line[5:].strip().strip('"').strip("'")
                elif line.startswith("description:"):
                    description = line[12:].strip().strip('"').strip("'")

    return {"name": name, "description": description, "content": content}


@router.get("/skills")
def list_skills():
    """列出所有 skill（从 skills/ 目录读取 SKILL.md frontmatter）"""
    os.makedirs(_get_skills_dir(), exist_ok=True)
    skills = []
    for entry in sorted(os.listdir(_get_skills_dir())):
        skill_dir = os.path.join(_get_skills_dir(), entry)
        skill_md = os.path.join(skill_dir, "SKILL.md")
        if os.path.isdir(skill_dir) and os.path.isfile(skill_md):
            info = _parse_skill_md(skill_md)
            skills.append({
                "name": info["name"] or entry,
                "dir_name": entry,
                "description": info["description"],
            })
    return {"skills": skills}


@router.get("/skills/{skill_name}")
def get_skill(skill_name: str):
    """读取指定 skill 的完整 SKILL.md 内容"""
    skill_md = os.path.join(_get_skills_dir(), skill_name, "SKILL.md")
    if not os.path.isfile(skill_md):
        return JSONResponse(status_code=404, content={"error": "Skill 不存在"})
    try:
        with open(skill_md, "r", encoding="utf-8") as f:
            raw = f.read()
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
    info = _parse_skill_md(skill_md)
    return {"dir_name": skill_name, "name": info["name"], "description": info["description"], "raw": raw}


class SkillUpdateRequest(BaseModel):
    name: str
    description: str = ""
    content: str = ""


class SkillFileRequest(BaseModel):
    content: str


@router.put("/skills/{skill_name}")
def update_skill(skill_name: str, req: SkillUpdateRequest):
    """创建或更新 skill 的 SKILL.md（完整覆盖写入）"""
    # 目录名只允许字母数字下划线横线
    if not re.match(r"^[a-zA-Z0-9_-]+$", skill_name):
        return JSONResponse(status_code=400, content={"error": "Skill 名称只允许字母、数字、下划线、横线"})

    skill_dir = os.path.join(_get_skills_dir(), skill_name)
    os.makedirs(skill_dir, exist_ok=True)

    # 构建 SKILL.md：YAML frontmatter + content body
    desc_escaped = req.description.replace('"', '\\"')
    frontmatter = f'---\nname: {req.name}\ndescription: "{desc_escaped}"\n---\n\n'
    full = frontmatter + req.content

    skill_md = os.path.join(skill_dir, "SKILL.md")
    with open(skill_md, "w", encoding="utf-8") as f:
        f.write(full)

    return {"ok": True, "dir_name": skill_name}


@router.delete("/skills/{skill_name}")
def delete_skill(skill_name: str):
    """删除整个 skill 目录"""
    skill_dir = os.path.join(_get_skills_dir(), skill_name)
    if not os.path.isdir(skill_dir):
        return JSONResponse(status_code=404, content={"error": "Skill 不存在"})
    shutil.rmtree(skill_dir)
    return {"ok": True}


@router.get("/skills/{skill_name}/files")
def list_skill_files(skill_name: str):
    """列出 skill 目录下的所有文件（递归），返回相对路径列表"""
    skill_dir = os.path.join(_get_skills_dir(), skill_name)
    if not os.path.isdir(skill_dir):
        return JSONResponse(status_code=404, content={"error": "Skill 不存在"})
    files = []
    for root, _dirs, filenames in os.walk(skill_dir):
        for fn in sorted(filenames):
            full = os.path.join(root, fn)
            rel = os.path.relpath(full, skill_dir).replace("\\", "/")
            size = os.path.getsize(full)
            files.append({"path": rel, "size": size})
    return {"files": files}


@router.get("/skills/{skill_name}/files/{file_path:path}")
def read_skill_file(skill_name: str, file_path: str):
    """读取 skill 目录下的指定文件内容"""
    skill_dir = os.path.join(_get_skills_dir(), skill_name)
    target = os.path.normpath(os.path.join(skill_dir, file_path))
    # 防止路径穿越
    if not target.startswith(os.path.normpath(skill_dir)):
        return JSONResponse(status_code=400, content={"error": "非法路径"})
    if not os.path.isfile(target):
        return JSONResponse(status_code=404, content={"error": "文件不存在"})
    try:
        with open(target, "r", encoding="utf-8") as f:
            content = f.read()
        return {"path": file_path, "content": content}
    except UnicodeDecodeError:
        return {"path": file_path, "content": "(二进制文件，无法预览)", "binary": True}


@router.put("/skills/{skill_name}/files/{file_path:path}")
def write_skill_file(skill_name: str, file_path: str, req: SkillFileRequest):
    """写入 skill 目录下的指定文件"""
    if not re.match(r"^[a-zA-Z0-9_-]+$", skill_name):
        return JSONResponse(status_code=400, content={"error": "非法 skill 名称"})
    skill_dir = os.path.join(_get_skills_dir(), skill_name)
    target = os.path.normpath(os.path.join(skill_dir, file_path))
    if not target.startswith(os.path.normpath(skill_dir)):
        return JSONResponse(status_code=400, content={"error": "非法路径"})
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8") as f:
        f.write(req.content)
    return {"ok": True}


@router.delete("/skills/{skill_name}/files/{file_path:path}")
def delete_skill_file(skill_name: str, file_path: str):
    """删除 skill 目录下的指定文件"""
    skill_dir = os.path.join(_get_skills_dir(), skill_name)
    target = os.path.normpath(os.path.join(skill_dir, file_path))
    if not target.startswith(os.path.normpath(skill_dir)):
        return JSONResponse(status_code=400, content={"error": "非法路径"})
    if not os.path.isfile(target):
        return JSONResponse(status_code=404, content={"error": "文件不存在"})
    os.remove(target)
    return {"ok": True}


# --- Workspace ---

class WorkspaceSetRequest(BaseModel):
    path: str


def _walk_workspace(root: str) -> list[dict]:
    """递归列出工作区文件树（最多 500 个节点，避免误选超大目录）"""
    result = []
    count = 0
    for dirpath, dirnames, filenames in os.walk(root):
        # 跳过隐藏目录
        dirnames[:] = [d for d in sorted(dirnames) if not d.startswith(".")]
        rel_dir = os.path.relpath(dirpath, root).replace("\\", "/")
        if rel_dir == ".":
            rel_dir = ""
        for fn in sorted(filenames):
            if count >= 500:
                break
            rel_path = f"{rel_dir}/{fn}".lstrip("/")
            full = os.path.join(dirpath, fn)
            result.append({
                "path": rel_path,
                "size": os.path.getsize(full),
                "modified": datetime.fromtimestamp(os.path.getmtime(full)).strftime("%Y-%m-%d %H:%M"),
            })
            count += 1
        if count >= 500:
            break
    return result


@router.get("/workspace")
def workspace_get(request: Request):
    """获取当前工作区信息（路径 + 文件列表）"""
    manager = request.app.state.agent_manager
    workspace_dir = manager._workspace_dir
    files = _walk_workspace(workspace_dir) if os.path.isdir(workspace_dir) else []
    return {
        "path": workspace_dir,
        "files": files,
    }


@router.post("/workspace/set")
def workspace_set(req: WorkspaceSetRequest, request: Request):
    """切换工作区目录"""
    path = os.path.normpath(req.path)
    if not os.path.isdir(path):
        try:
            os.makedirs(path, exist_ok=True)
        except Exception as e:
            return JSONResponse(status_code=400, content={"error": f"目录不存在且无法创建: {e}"})

    store, _ = _get_shared(request)
    store.put(("settings",), "workspace_dir", {"path": path})

    manager = request.app.state.agent_manager
    manager.set_workspace(path)

    return {"ok": True, "path": path}


@router.post("/workspace/pick")
def workspace_pick(request: Request):
    """弹出系统文件夹选择器（tkinter 子进程），选中后自动设为工作区。"""
    # 用 PowerShell 原生文件夹选择器，不依赖 tkinter（打包后嵌入式 Python 没有 tkinter）
    ps_script = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "$d = New-Object System.Windows.Forms.FolderBrowserDialog; "
        "$d.Description = '选择工作区目录'; "
        "$d.ShowNewFolderButton = $true; "
        "if ($d.ShowDialog() -eq 'OK') { Write-Output $d.SelectedPath }"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True, text=True, timeout=120,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        chosen = result.stdout.strip()
    except Exception:
        chosen = ""

    if not chosen:
        return {"path": None}

    # 自动执行 set workspace 逻辑
    path = os.path.normpath(chosen)
    if not os.path.isdir(path):
        return JSONResponse(status_code=400, content={"error": "所选目录不存在"})

    store, _ = _get_shared(request)
    store.put(("settings",), "workspace_dir", {"path": path})
    manager = request.app.state.agent_manager
    manager.set_workspace(path)

    return {"path": path}


class RevealRequest(BaseModel):
    path: str | None = None


@router.post("/workspace/reveal")
def workspace_reveal(req: RevealRequest, request: Request):
    """在 Windows 资源管理器中打开文件/目录。"""
    manager = request.app.state.agent_manager
    workspace_dir = manager._workspace_dir

    if req.path:
        target = os.path.normpath(os.path.join(workspace_dir, req.path))
        if not target.startswith(os.path.normpath(workspace_dir)):
            return JSONResponse(status_code=400, content={"error": "非法路径"})
        if os.path.isfile(target):
            subprocess.Popen(["explorer", "/select,", target])
        elif os.path.isdir(target):
            os.startfile(target)
        else:
            return JSONResponse(status_code=404, content={"error": "路径不存在"})
    else:
        if os.path.isdir(workspace_dir):
            os.startfile(workspace_dir)
        else:
            return JSONResponse(status_code=404, content={"error": "工作区目录不存在"})

    return {"ok": True}


@router.get("/workspace/raw/{file_path:path}")
def workspace_raw_file(file_path: str, request: Request):
    """返回工作区文件的原始内容（用于图片 <img src> 等）。"""
    manager = request.app.state.agent_manager
    workspace_dir = manager._workspace_dir
    target = os.path.normpath(os.path.join(workspace_dir, file_path))
    if not target.startswith(os.path.normpath(workspace_dir)):
        return JSONResponse(status_code=400, content={"error": "非法路径"})
    if not os.path.isfile(target):
        return JSONResponse(status_code=404, content={"error": "文件不存在"})
    return FileResponse(target)


@router.get("/workspace/file/{file_path:path}")
def workspace_read_file(file_path: str, request: Request):
    """读取工作区内某个文件的内容"""
    manager = request.app.state.agent_manager
    workspace_dir = manager._workspace_dir
    target = os.path.normpath(os.path.join(workspace_dir, file_path))
    if not target.startswith(os.path.normpath(workspace_dir)):
        return JSONResponse(status_code=400, content={"error": "非法路径"})
    if not os.path.isfile(target):
        return JSONResponse(status_code=404, content={"error": "文件不存在"})
    try:
        with open(target, "r", encoding="utf-8") as f:
            content = f.read()
        return {"path": file_path, "content": content}
    except UnicodeDecodeError:
        return {"path": file_path, "content": "(二进制文件，无法预览)", "binary": True}


@router.delete("/workspace/file/{file_path:path}")
def workspace_delete_file(file_path: str, request: Request):
    """删除工作区内某个文件"""
    manager = request.app.state.agent_manager
    workspace_dir = manager._workspace_dir
    target = os.path.normpath(os.path.join(workspace_dir, file_path))
    if not target.startswith(os.path.normpath(workspace_dir)):
        return JSONResponse(status_code=400, content={"error": "非法路径"})
    if not os.path.isfile(target):
        return JSONResponse(status_code=404, content={"error": "文件不存在"})
    os.remove(target)
    return {"ok": True}
