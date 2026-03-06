"""
PDF 解析模块

支持两种解析方式：
1. MinerU API（云端，质量更好，需要 API key）
2. pdfplumber（本地，兜底方案）

MinerU key 过期或不可用时自动降级到 pdfplumber。
"""
import io
import os
import time
import zipfile
import logging

import requests
import pdfplumber

logger = logging.getLogger(__name__)

_MINERU_BATCH_URL = "https://mineru.net/api/v4/file-urls/batch"
_MINERU_RESULT_URL = "https://mineru.net/api/v4/extract-results/batch"
_MINERU_POLL_INTERVAL = 5  # 秒
_MINERU_POLL_MAX = 60  # 最多轮询次数（5分钟）


def parse_pdf(file_bytes: bytes, filename: str) -> dict:
    """解析 PDF，返回 {"content": str, "pages": int, "method": str}。

    优先 MinerU API（失败重试 1 次），再降级 pdfplumber。
    pdfplumber 提取为空时返回 warning 提示用户。
    """
    token = os.environ.get("MINERU_API_KEY", "")
    if token:
        last_err = None
        for attempt in range(2):
            try:
                result = _parse_with_mineru(file_bytes, filename, token)
                logger.info("MinerU 解析成功: %s (%d chars)", filename, len(result["content"]))
                return result
            except Exception as e:
                last_err = e
                if attempt == 0:
                    logger.warning("MinerU 第 1 次失败，重试: %s", e)
                    time.sleep(2)
                else:
                    logger.warning("MinerU 重试仍失败，降级到 pdfplumber: %s", e)

    result = _local_fallback(file_bytes, filename)
    if not result["content"].strip():
        logger.warning("本地解析未提取到文本（可能是扫描件）: %s", filename)
        if not result.get("warning"):
            result["warning"] = "未提取到文本内容，该文件可能是扫描件（图片PDF），建议使用 OCR 处理后重新上传。"
    else:
        logger.info("本地解析成功: %s (%d chars, %s)", filename, len(result["content"]), result["method"])
    return result


def _parse_with_mineru(file_bytes: bytes, filename: str, token: str) -> dict:
    """MinerU API 解析流程：申请上传URL → PUT上传 → 轮询结果 → 下载zip → 提取md"""
    header = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }

    # Step 1: 申请上传 URL
    res = requests.post(
        _MINERU_BATCH_URL,
        headers=header,
        json={
            "files": [{"name": filename}],
            "model_version": "vlm",
            "enable_table": True,
        },
        timeout=30,
    )
    res.raise_for_status()
    data = res.json()
    if data.get("code") != 0:
        raise RuntimeError(f"MinerU 申请上传失败: {data.get('msg', data)}")

    batch_id = data["data"]["batch_id"]
    upload_url = data["data"]["file_urls"][0]

    # Step 2: PUT 上传文件
    res_upload = requests.put(upload_url, data=file_bytes, timeout=120)
    if res_upload.status_code != 200:
        raise RuntimeError(f"MinerU 上传失败: HTTP {res_upload.status_code}")

    # Step 3: 轮询结果
    zip_url = ""
    total_pages = 0
    for _ in range(_MINERU_POLL_MAX):
        time.sleep(_MINERU_POLL_INTERVAL)
        res = requests.get(
            f"{_MINERU_RESULT_URL}/{batch_id}",
            headers=header,
            timeout=30,
        )
        results = res.json().get("data", {}).get("extract_result", [])
        if not results:
            continue

        state = results[0].get("state", "")
        progress = results[0].get("extract_progress", {})
        if progress.get("total_pages"):
            total_pages = progress["total_pages"]

        if state == "done":
            zip_url = results[0]["full_zip_url"]
            break
        elif state == "failed":
            raise RuntimeError(f"MinerU 解析失败: {results[0].get('err_msg', '')}")
    else:
        raise RuntimeError("MinerU 解析超时")

    # Step 4: 下载 zip，提取 full.md
    zip_res = requests.get(zip_url, timeout=120)
    zip_res.raise_for_status()
    z = zipfile.ZipFile(io.BytesIO(zip_res.content))

    md_files = [f for f in z.namelist() if f.endswith(".md")]
    if not md_files:
        raise RuntimeError("MinerU 结果中无 .md 文件")

    content = z.read(md_files[0]).decode("utf-8")

    return {"content": content, "pages": total_pages or 1, "method": "mineru"}


def parse_pdfs_batch(files: list[tuple[bytes, str]]) -> list[dict]:
    """批量解析 PDF。每个元素 (file_bytes, filename)。

    MinerU 一个 batch 提交所有文件，轮询等全部完成。
    单个文件 MinerU 失败的独立降级 pdfplumber。
    返回 list[dict]，顺序与输入一致。每个 dict 同 parse_pdf 返回格式。
    """
    if len(files) == 1:
        return [parse_pdf(files[0][0], files[0][1])]

    token = os.environ.get("MINERU_API_KEY", "")
    if not token:
        # 无 API key，全部走本地解析
        results = []
        for file_bytes, filename in files:
            r = _local_fallback(file_bytes, filename)
            if not r["content"].strip() and not r.get("warning"):
                r["warning"] = "未提取到文本内容，该文件可能是扫描件（图片PDF），建议使用 OCR 处理后重新上传。"
            results.append(r)
        return results

    # MinerU 批量解析
    try:
        batch_results = _parse_batch_with_mineru(files, token)
    except Exception as e:
        logger.warning("MinerU 批量请求整体失败，全部降级 pdfplumber: %s", e)
        batch_results = [e] * len(files)

    # 处理结果：成功的直接用，失败的降级 pdfplumber
    final = []
    for i, r in enumerate(batch_results):
        file_bytes, filename = files[i]
        if isinstance(r, Exception):
            logger.warning("MinerU 文件 %s 失败，降级本地解析: %s", filename, r)
            fallback = _local_fallback(file_bytes, filename)
            if not fallback["content"].strip() and not fallback.get("warning"):
                fallback["warning"] = "未提取到文本内容，该文件可能是扫描件（图片PDF），建议使用 OCR 处理后重新上传。"
            final.append(fallback)
        else:
            logger.info("MinerU 批量解析成功: %s (%d chars)", filename, len(r["content"]))
            final.append(r)
    return final


def _parse_batch_with_mineru(files: list[tuple[bytes, str]], token: str) -> list:
    """MinerU 批量解析：一个 batch 提交所有文件，轮询等全部完成。

    返回 list，长度与 files 一致。成功的位置放 dict，失败的放 Exception。
    """
    header = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }

    # Step 1: 申请上传 URL（所有文件一次请求）
    file_specs = [{"name": fn} for _, fn in files]
    res = requests.post(
        _MINERU_BATCH_URL,
        headers=header,
        json={
            "files": file_specs,
            "model_version": "vlm",
            "enable_table": True,
        },
        timeout=30,
    )
    res.raise_for_status()
    data = res.json()
    if data.get("code") != 0:
        raise RuntimeError(f"MinerU 批量申请上传失败: {data.get('msg', data)}")

    batch_id = data["data"]["batch_id"]
    upload_urls = data["data"]["file_urls"]

    # Step 2: 逐个 PUT 上传
    for i, (file_bytes, filename) in enumerate(files):
        res_upload = requests.put(upload_urls[i], data=file_bytes, timeout=120)
        if res_upload.status_code != 200:
            logger.warning("MinerU 上传失败 %s: HTTP %d", filename, res_upload.status_code)

    # Step 3: 轮询，等所有文件到终态
    # 注意：MinerU 返回的 file_name 可能与上传时的 name 不同（从 PDF 元数据提取），
    # 但 extract_result 数组顺序与提交的 files 数组顺序一致，用索引匹配。
    # total_pages 仅在 running 状态下返回，done 时不返回，需要在 running 阶段记录。
    final_results: list = [None] * len(files)
    pages_cache: list[int] = [0] * len(files)

    for _ in range(_MINERU_POLL_MAX):
        time.sleep(_MINERU_POLL_INTERVAL)
        res = requests.get(
            f"{_MINERU_RESULT_URL}/{batch_id}",
            headers=header,
            timeout=30,
        )
        extract_results = res.json().get("data", {}).get("extract_result", [])
        if not extract_results:
            continue

        all_done = True
        for idx, er in enumerate(extract_results):
            if idx >= len(files):
                break
            state = er.get("state", "")
            fname = er.get("file_name", files[idx][1])

            progress = er.get("extract_progress", {})
            if progress.get("total_pages"):
                pages_cache[idx] = progress["total_pages"]

            if state == "done":
                if final_results[idx] is None:
                    try:
                        zip_url = er["full_zip_url"]
                        zip_res = requests.get(zip_url, timeout=120)
                        zip_res.raise_for_status()
                        z = zipfile.ZipFile(io.BytesIO(zip_res.content))
                        md_files = [f for f in z.namelist() if f.endswith(".md")]
                        if not md_files:
                            final_results[idx] = RuntimeError(f"MinerU 结果中无 .md: {fname}")
                        else:
                            content = z.read(md_files[0]).decode("utf-8")
                            pages = pages_cache[idx] or 1
                            final_results[idx] = {"content": content, "pages": pages, "method": "mineru"}
                    except Exception as e:
                        final_results[idx] = RuntimeError(f"下载结果失败 {fname}: {e}")
            elif state == "failed":
                if final_results[idx] is None:
                    final_results[idx] = RuntimeError(f"MinerU 解析失败 {fname}: {er.get('err_msg', '')}")
            else:
                all_done = False

        if all_done and all(r is not None for r in final_results):
            break
    else:
        for i, r in enumerate(final_results):
            if r is None:
                final_results[i] = RuntimeError(f"MinerU 解析超时: {files[i][1]}")

    return final_results


def _parse_with_pdfplumber(file_bytes: bytes, filename: str) -> dict:
    """pdfplumber 本地解析"""
    pdf = pdfplumber.open(io.BytesIO(file_bytes))
    pages = len(pdf.pages)
    parts = []
    for i, page in enumerate(pdf.pages):
        text = page.extract_text()
        if text:
            parts.append(f"## Page {i + 1}\n\n{text}")
    pdf.close()

    content = "\n\n---\n\n".join(parts) if parts else ""
    return {"content": content, "pages": pages, "method": "pdfplumber"}


def _parse_with_docx(file_bytes: bytes, filename: str) -> dict:
    """python-docx 本地解析 .docx 文件"""
    from docx import Document
    doc = Document(io.BytesIO(file_bytes))
    parts = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            parts.append(text)
    content = "\n\n".join(parts) if parts else ""
    return {"content": content, "pages": 1, "method": "python-docx"}


def _local_fallback(file_bytes: bytes, filename: str) -> dict:
    """根据文件类型选择本地降级方案。"""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext == "pdf":
        return _parse_with_pdfplumber(file_bytes, filename)
    elif ext == "docx":
        return _parse_with_docx(file_bytes, filename)
    elif ext == "doc":
        # .doc 旧格式：尝试 python-docx（部分 .doc 实际是 OOXML 可以打开）
        try:
            return _parse_with_docx(file_bytes, filename)
        except Exception:
            return {"content": "", "pages": 0, "method": "none",
                    "warning": ".doc 旧格式本地解析失败，建议另存为 .docx 后重新上传"}
    else:
        return {"content": "", "pages": 0, "method": "none",
                "warning": f"不支持 .{ext} 的本地解析，MinerU 解析也失败了"}
