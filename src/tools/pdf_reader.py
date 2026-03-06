"""
PDF、Word文档读取工具

支持 PDF / DOC / DOCX。
优先使用 parse_pdf（MinerU + 本地降级），打包环境下降级为 subprocess。
解析结果自动保存为原文件同级 output/ 目录下的 .md 文件（缓存 + 供 agent 用 read_file 读取全文）。
"""
import os
import subprocess
import tempfile

from langchain_core.tools import tool

_PYTHON = os.environ.get("PYTHON_EXECUTABLE", __import__("sys").executable)
_TIMEOUT = 60  # 文档可能较大，给 60 秒

_ALLOWED_EXTS = (".pdf", ".doc", ".docx")


def _resolve_path(file_path: str) -> str:
    """虚拟路径转真实路径，import 失败时原样返回。"""
    try:
        from src.tools.path_resolver import resolve_virtual_path
        return resolve_virtual_path(file_path).replace("\\", "/")
    except ImportError:
        return file_path.replace("\\", "/")


def _to_virtual_path(real_path: str) -> str:
    """真实路径转回虚拟路径（用于返回给 agent 的提示信息）。"""
    try:
        from src.tools.path_resolver import _VIRTUAL_ROOTS
        normalized = real_path.replace("\\", "/")
        for prefix, real_dir in _VIRTUAL_ROOTS.items():
            real_forward = real_dir.replace("\\", "/")
            if normalized.startswith(real_forward):
                relative = normalized[len(real_forward):].lstrip("/")
                return prefix + relative
    except ImportError:
        pass
    return real_path


def _cache_path(file_path: str) -> str:
    """原文件路径 → 同级 output/ 目录下同名 .md 缓存路径。"""
    dirname = os.path.dirname(file_path)
    basename = os.path.splitext(os.path.basename(file_path))[0]
    output_dir = os.path.join(dirname, "output")
    os.makedirs(output_dir, exist_ok=True)
    return os.path.join(output_dir, basename + ".md")


def _read_cache(file_path: str) -> str | None:
    """缓存存在则读取返回，否则返回 None。"""
    cp = _cache_path(file_path)
    if os.path.exists(cp):
        try:
            with open(cp, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            pass
    return None


def _write_cache(file_path: str, content: str):
    """写入缓存，失败静默。"""
    cp = _cache_path(file_path)
    try:
        with open(cp, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception:
        pass


def _read_via_parser(file_path: str) -> str | None:
    """用 parse_pdf 直接在进程内解析，返回文本。不可用时返回 None。"""
    try:
        from src.tools.pdf_parser import parse_pdf
    except ImportError:
        return None

    with open(file_path, "rb") as f:
        file_bytes = f.read()

    filename = os.path.basename(file_path)
    result = parse_pdf(file_bytes, filename)

    content = result.get("content", "")
    if not content.strip():
        warning = result.get("warning", "")
        return warning or "文档无可提取的文本内容"

    method = result.get("method", "unknown")
    pages = result.get("pages", 0)
    header = f"总页数: {pages} | 解析方式: {method}\n\n"
    return header + content


def _read_via_subprocess_pdf(file_path: str) -> str:
    """降级方案：subprocess + pdfplumber。"""
    code = f'''
import pdfplumber, sys
sys.stdout.reconfigure(encoding="utf-8")
pdf = pdfplumber.open(r"{file_path}")
print(f"总页数: {{len(pdf.pages)}}\\n")
for i, p in enumerate(pdf.pages):
    t = p.extract_text()
    if t:
        print(f"=== Page {{i+1}} ===")
        print(t)
        print()
pdf.close()
'''
    return _run_subprocess(code)


def _read_via_subprocess_word(file_path: str) -> str:
    """降级方案：subprocess + python-docx（.doc/.docx）。"""
    code = f'''
import sys, io
sys.stdout.reconfigure(encoding="utf-8")
from docx import Document
with open(r"{file_path}", "rb") as f:
    doc = Document(io.BytesIO(f.read()))
for para in doc.paragraphs:
    text = para.text.strip()
    if text:
        print(text)
'''
    return _run_subprocess(code)


def _run_subprocess(code: str) -> str:
    """执行 subprocess 代码并返回输出。"""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, encoding="utf-8"
    ) as f:
        f.write(code)
        tmp_path = f.name

    try:
        result = subprocess.run(
            [_PYTHON, tmp_path],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            encoding="utf-8",
            errors="replace",
        )
        stdout = result.stdout or ""
        stderr = result.stderr or ""

        if result.returncode == 0:
            output = stdout.strip()
            if not output:
                output = "文档无可提取的文本内容"
        else:
            output = f"读取失败:\n{stderr.strip()}"
        return output

    except subprocess.TimeoutExpired:
        return f"读取超时（{_TIMEOUT} 秒），文件可能过大。"
    except Exception as e:
        return f"读取失败: {e}"
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


@tool
def read_pdf(file_path: str) -> str:
    """读取PDF或Word文档文件并提取全部文本内容。支持 PDF、DOC、DOCX。

    解析结果会自动保存为原文件同级 output/ 目录下的 .md 文件。
    返回保存路径，请用 read_file 按需读取完整内容。

    适用场景：
        - 读取用户提供的 PDF、Word 文档

    参数：
        file_path: 文件路径（支持虚拟路径如 /workspace/xxx.pdf）

    返回：
        解析摘要和 .md 文件路径（需用 read_file 读取完整内容）
    """
    file_path = _resolve_path(file_path)

    if not os.path.exists(file_path):
        return f"文件不存在: {file_path}"

    ext = os.path.splitext(file_path)[1].lower()
    if ext not in _ALLOWED_EXTS:
        return f"不支持的文件格式: {ext}，支持 PDF/DOC/DOCX"

    md_virtual = _to_virtual_path(_cache_path(file_path))

    # 缓存命中
    cached = _read_cache(file_path)
    if cached:
        return f"文档已缓存在 {md_virtual}（共 {len(cached)} 字符）。\n请用 read_file 读取该文件获取内容。"

    # 优先：进程内 parse_pdf（MinerU + 本地降级）
    output = _read_via_parser(file_path)

    # 降级：subprocess（打包环境，parser 模块 import 失败）
    if output is None:
        if ext == ".pdf":
            output = _read_via_subprocess_pdf(file_path)
        else:
            output = _read_via_subprocess_word(file_path)

    # 保存 .md 缓存
    _write_cache(file_path, output)
    md_virtual = _to_virtual_path(_cache_path(file_path))

    # 从 output 提取页数和解析方式信息
    method = "unknown"
    pages = 0
    for line in output.split("\n", 3):
        if "解析方式:" in line:
            method = line.split("解析方式:")[-1].strip()
        if "总页数:" in line:
            try:
                pages = int(line.split("总页数:")[-1].split("|")[0].strip())
            except ValueError:
                pass

    return f"文档已解析并保存到 {md_virtual}（共 {len(output)} 字符，{pages} 页，{method} 解析）。\n请用 read_file 读取该文件获取内容。"
