"""
Python 代码执行工具

让 Agent 能够编写并运行 Python 代码进行数据分析、数值计算、画图等。
每次执行在独立子进程中运行，无状态，默认超时 30 秒（可配置）。
"""
import os
import re
import subprocess
import tempfile
import sys

from langchain_core.tools import tool

from src.tools.path_resolver import resolve_virtual_paths_in_code

# 定位 Python 解释器：环境变量 > embedded Python > sys.executable
def _find_python():
    # 1. 显式环境变量
    p = os.environ.get("PYTHON_EXECUTABLE")
    if p and os.path.isfile(p):
        return p
    # 2. 打包后结构: resources/app/src/tools/ → resources/python/python.exe
    embedded = os.path.normpath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "..", "..", "python", "python.exe"
    ))
    if os.path.isfile(embedded):
        return embedded
    # 3. 当前进程的 Python
    return sys.executable

_PYTHON = _find_python()

_DEFAULT_TIMEOUT = 30  # 默认超时（秒）
_MAX_TIMEOUT = 300  # 最大超时限制（5 分钟）
_MAX_OUTPUT = 10_000  # 最大输出字符数

# --- 安全检查：防止代码删除文件/目录 ---
_DANGEROUS_PATTERNS = [
    (r'\bshutil\s*\.\s*rmtree\b', "禁止使用 shutil.rmtree（递归删除目录）"),
    (r'\bos\s*\.\s*remove\b', "禁止使用 os.remove（删除文件）"),
    (r'\bos\s*\.\s*unlink\b', "禁止使用 os.unlink（删除文件）"),
    (r'\bos\s*\.\s*rmdir\b', "禁止使用 os.rmdir（删除目录）"),
    (r'\bos\s*\.\s*removedirs\b', "禁止使用 os.removedirs（递归删除目录）"),
    (r'\bsend2trash\b', "禁止使用 send2trash（删除文件）"),
    (r'\.\s*unlink\s*\(', "禁止使用 .unlink()（删除文件）"),
    (r'\.\s*rmdir\s*\(', "禁止使用 .rmdir()（删除目录）"),
]

def _check_code_safety(code: str) -> str | None:
    """检查代码是否包含文件删除操作，返回拒绝原因或 None（安全）。"""
    for pattern, reason in _DANGEROUS_PATTERNS:
        if re.search(pattern, code):
            return reason
    return None

# 工作目录：data/tmp（上传的 Excel 等文件存放于此）
_user_data = os.environ.get("ARCSTONE_ECON_USER_DATA")
if _user_data:
    _WORK_DIR = os.path.normpath(os.path.join(_user_data, "data", "tmp"))
else:
    _WORK_DIR = os.path.normpath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "tmp"
    ))
os.makedirs(_WORK_DIR, exist_ok=True)


@tool
def run_python(code: str, timeout: int = 30) -> str:
    """运行 Python 代码并返回输出结果。

    适用场景：
        - 数值计算（IRR、NPV、DCF、敏感性分析、蒙特卡洛模拟）
        - 数据处理（pandas 读取/分析 CSV/Excel）
        - 画图（matplotlib/plotly，用 plt.savefig() 保存）
        - 任何需要编程才能完成的分析任务

    参数：
        code: 要执行的 Python 代码（完整脚本，print() 输出结果）
        timeout: 超时时间（秒），默认 30 秒。大计算量任务可设置更长，最大 300 秒

    返回：
        代码的标准输出。如果有错误则返回 stderr。

    注意：
        - 每次执行独立，变量不跨次保留
        - 默认超时 30 秒，大计算量任务可通过 timeout 参数延长（如 timeout=120）
        - 可用库：numpy, scipy, pandas, matplotlib 等已安装的库
        - 安装新包：用 subprocess.run(["uv", "pip", "install", "--system", "--python", sys.executable, "包名"], check=True)，速度最快且确保装到当前环境
        - 备选：subprocess.run([sys.executable, "-m", "pip", "install", "包名"], check=True)
        - 国内镜像加速：加 "-i", "https://mirrors.aliyun.com/pypi/simple/" 参数
        - 画图请用 plt.savefig

    示例：
        run_python("import numpy as np\\nprint(np.irr([-1000, 300, 400, 500, 600]))")
        run_python("# 大计算量任务\\nimport time\\ntime.sleep(60)", timeout=120)
    """
    # 限制超时范围
    timeout = max(1, min(timeout, _MAX_TIMEOUT))

    # 安全检查：拒绝危险代码
    danger = _check_code_safety(code)
    if danger:
        return f"代码安全检查未通过：{danger}。该操作存在安全风险，已被自动拦截。"

    # 将代码中的虚拟路径（/workspace/xxx）替换为真实磁盘路径
    code = resolve_virtual_paths_in_code(code)

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, encoding="utf-8"
    ) as f:
        f.write(code)
        tmp_path = f.name

    try:
        # 构建干净的环境变量，强制 UTF-8 避免 Windows GBK 解码炸裂
        clean_env = {
            **os.environ,
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUTF8": "1",  # PEP 686: 令子进程及其孙进程全部默认 UTF-8
        }
        result = subprocess.run(
            [_PYTHON, tmp_path],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=_WORK_DIR,
            env=clean_env,
            encoding="utf-8",
            errors="replace",
        )

        stdout = result.stdout or ""
        stderr = result.stderr or ""

        if result.returncode == 0:
            output = stdout.strip()
            if not output:
                output = "(代码执行成功，无输出。如需查看结果请用 print())"
        else:
            output = f"执行出错 (exit code {result.returncode}):\n{stderr.strip()}"
            if stdout.strip():
                output = f"{stdout.strip()}\n\n{output}"

        if len(output) > _MAX_OUTPUT:
            output = output[:_MAX_OUTPUT] + f"\n\n... (输出已截断，共 {len(output)} 字符)"

        return output

    except subprocess.TimeoutExpired:
        return f"执行超时（{timeout} 秒）。请优化代码、减少计算量，或使用更长的 timeout 参数（最大 {_MAX_TIMEOUT} 秒）。"
    except FileNotFoundError:
        return f"Python 解释器未找到: {_PYTHON}。请检查 PYTHON_EXECUTABLE 环境变量。"
    except Exception as e:
        return f"执行失败: {e}"
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
