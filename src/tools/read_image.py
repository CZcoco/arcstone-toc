"""
图片读取工具

读取工作区中的图片文件，调用多模态模型识别内容，返回结构化文字描述。
"""
import os
import base64
import logging

from langchain_core.tools import tool
from langchain_core.messages import HumanMessage

logger = logging.getLogger(__name__)

_ALLOWED_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".webp")
_MAX_SIZE_BYTES = 5 * 1024 * 1024  # 5MB

_IMAGE_DESCRIBE_PROMPT = (
    "请仔细查看这张图片，描述其内容。如果是统计图表，请说明：\n"
    "1. 图表类型（散点图/折线图/柱状图/热力图等）\n"
    "2. X轴和Y轴分别代表什么\n"
    "3. 数据的主要趋势或模式\n"
    "4. 图中标注的关键数值（如有）\n"
    "5. 图表标题和图例（如有）\n"
    "请用中文回答，简洁准确。"
)


def _resolve_path(file_path: str) -> str:
    """虚拟路径转真实路径。"""
    try:
        from src.tools.path_resolver import resolve_virtual_path
        return resolve_virtual_path(file_path).replace("\\", "/")
    except ImportError:
        return file_path.replace("\\", "/")


def _is_vision_unsupported() -> bool:
    """检测当前模型是否不支持图像输入。

    v0.5.11 起所有支持的模型（Claude、GPT）均支持多模态。
    CURRENT_MODEL 由 stream.py 在每次请求时设置。
    """
    return False


def _describe_image(data_url: str, file_path: str) -> str:
    """调用当前多模态模型识别图片内容，返回文字描述。"""
    model_name = os.environ.get("CURRENT_MODEL", "")
    if not model_name:
        return "(无法识别图片：未检测到当前模型)"

    try:
        from src.agent.config import get_llm
        llm = get_llm(model_name)
    except Exception as e:
        logger.warning("Failed to get LLM for image description: %s", e)
        return f"(无法识别图片：获取模型失败 - {e})"

    msg = HumanMessage(content=[
        {"type": "text", "text": _IMAGE_DESCRIBE_PROMPT},
        {"type": "image_url", "image_url": {"url": data_url}},
    ])

    try:
        resp = llm.invoke([msg])
        text = resp.content if isinstance(resp.content, str) else str(resp.content)
        return f"图片路径：{file_path}\n\n{text}"
    except Exception as e:
        logger.warning("Image description failed: %s", e)
        return f"图片路径：{file_path}\n(图片识别失败：{e})"


@tool
def read_image(file_path: str) -> str:
    """读取工作区中的图片文件，识别并描述图片内容。

    使用场景：
    - 查看 Stata/Python 生成的回归系数图、散点图等
    - 核实论文中需要嵌入的图表样式

    参数：
        file_path: 图片路径（支持虚拟路径如 /workspace/figures/result.png）

    返回：
        图片内容的文字描述（由多模态模型识别），或降级信息（模型不支持视觉时）
    """
    real_path = _resolve_path(file_path)

    if not os.path.exists(real_path):
        return f"文件不存在: {file_path}"

    ext = os.path.splitext(real_path)[1].lower()
    if ext not in _ALLOWED_EXTS:
        return f"不支持的图片格式: {ext}，支持 {', '.join(_ALLOWED_EXTS)}"

    size = os.path.getsize(real_path)
    if size > _MAX_SIZE_BYTES:
        return f"图片文件过大（{size / 1024 / 1024:.1f}MB），超过 5MB 限制，请压缩后重试。"

    size_kb = size / 1024

    # 不支持图像的模型，降级返回文件元信息（当前所有模型均支持多模态）
    if _is_vision_unsupported():
        model = os.environ.get("CURRENT_MODEL", "unknown")
        return (
            f"【当前模型（{model}）不支持图像识别，无法查看图片内容】\n"
            f"图片路径：{file_path}\n"
            f"文件大小：{size_kb:.1f}KB\n"
            f"如需分析图表内容，请切换到支持多模态的模型（如 Claude、GPT）。"
        )

    # 读取图片并转 base64
    with open(real_path, "rb") as f:
        img_bytes = f.read()

    b64 = base64.b64encode(img_bytes).decode("utf-8")
    mime_ext = ext.lstrip(".")
    if mime_ext == "jpg":
        mime_ext = "jpeg"
    data_url = f"data:image/{mime_ext};base64,{b64}"

    # 调用多模态模型识别图片内容
    return _describe_image(data_url, file_path)
