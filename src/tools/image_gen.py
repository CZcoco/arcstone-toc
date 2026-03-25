"""
图片生成工具 — 通过 New API 调用文生图/图生图模型
"""
import base64
import os
import re
import uuid

import httpx
from langchain_core.tools import tool


def _make_filename(prompt: str) -> str:
    """从 prompt 生成有意义的文件名"""
    # 取前30个字符，去掉不安全字符
    name = prompt[:30].strip()
    # 只保留中文、英文、数字、空格、下划线、连字符
    name = re.sub(r'[^\w\u4e00-\u9fff\s-]', '', name)
    name = re.sub(r'\s+', '_', name).strip('_')
    if not name:
        name = f"generated_{uuid.uuid4().hex[:8]}"
    # 加短 hash 避免重名
    short_id = uuid.uuid4().hex[:4]
    return f"{name}_{short_id}.png"


def _api_url() -> str:
    return os.environ.get("NEW_API_URL", "http://43.128.44.82:3000/v1")


def _api_key() -> str:
    return os.environ.get("ECON_USER_TOKEN", "")


def _workspace_dir() -> str:
    """获取当前工作区目录"""
    try:
        from src.tools.path_resolver import resolve_virtual_path
        path = resolve_virtual_path("/workspace/")
        if path and not path.startswith("/workspace"):
            return path
    except Exception:
        pass
    # Fallback: 直接从 main 模块获取
    from src.agent.main import DATA_DIR
    return os.path.join(DATA_DIR, "workspace")


@tool
def generate_image(prompt: str, model: str = "qwen-image-2.0-pro-2026-03-03", size: str = "1024x1024") -> str:
    """根据文字描述生成图片。

    参数：
        prompt: 图片描述（英文效果更好，中文也支持）
        model: 模型名称（留空则使用服务端默认模型）
        size: 图片尺寸，可选 "1024x1024", "1024x1792", "1792x1024"

    返回：
        生成的图片保存路径
    """
    api_key = _api_key()
    if not api_key:
        return "错误：未登录，无法生成图片"

    body: dict = {
        "prompt": prompt,
        "n": 1,
        "size": size,
    }
    if model:
        body["model"] = model

    try:
        resp = httpx.post(
            f"{_api_url()}/images/generations",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()

        images = data.get("data", [])
        if not images:
            return "图片生成失败：API 返回空结果"

        item = images[0]

        # 处理 base64 格式
        if item.get("b64_json"):
            img_bytes = base64.b64decode(item["b64_json"])
            filename = _make_filename(prompt)
            ws = _workspace_dir()
            os.makedirs(ws, exist_ok=True)
            filepath = os.path.join(ws, filename)
            with open(filepath, "wb") as f:
                f.write(img_bytes)
            return f"图片已生成并保存到 /workspace/{filename}，用户已可在聊天中直接看到图片，无需再调用 read_image。\n\n![{prompt[:50]}](/workspace/{filename})"

        # 处理 URL 格式
        if item.get("url"):
            url = item["url"]
            filename = _make_filename(prompt)
            # 尝试下载保存到本地
            try:
                img_resp = httpx.get(url, timeout=60, follow_redirects=True)
                img_resp.raise_for_status()
                ws = _workspace_dir()
                os.makedirs(ws, exist_ok=True)
                filepath = os.path.join(ws, filename)
                with open(filepath, "wb") as f:
                    f.write(img_resp.content)
                return f"图片已生成并保存到 /workspace/{filename}，用户已可在聊天中直接看到图片，无需再调用 read_image。\n\n![{prompt[:50]}](/workspace/{filename})"
            except Exception:
                # 下载失败，直接返回远程 URL
                return f"图片已生成，用户已可在聊天中直接看到图片，无需再调用 read_image。\n\n![{prompt[:50]}]({url})"

        return "图片生成失败：未知的响应格式"

    except httpx.HTTPStatusError as e:
        error_body = e.response.text[:200] if e.response else ""
        return f"图片生成失败 (HTTP {e.response.status_code}): {error_body}"
    except Exception as e:
        return f"图片生成失败: {e}"
