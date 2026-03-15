"""
依赖安装器 - 管理 embedded Python 的首启依赖安装

首次启动只安装最小必要依赖，让应用尽快可用。
统计分析、文档解析等扩展能力保留为可选依赖，缺失时不阻塞应用启动。
"""
import os
import sys
import json
import subprocess
import asyncio
from pathlib import Path
import logging
from typing import Any

logger = logging.getLogger(__name__)

StageDef = dict[str, Any]
ALIBABA_PYPI_MIRROR = "https://mirrors.aliyun.com/pypi/simple/"

# 通过 embedded Python 自检的首启核心模块
CORE_MODULES = [
    "fastapi",
    "uvicorn",
    "deepagents",
    "langchain_openai",
    "langchain_anthropic",
    "langgraph.checkpoint.sqlite",
    "dotenv",
    "multipart",
]

# 依赖分阶段安装
# startup=True 的阶段会在首次启动时自动安装；其余为可选扩展，不阻塞应用启动。
DEPENDENCY_STAGES = [
    {
        "name": "应用框架",
        "critical": True,
        "startup": True,
        "packages": [
            "deepagents>=0.4.1",
            "langchain-openai>=1.1.0",
            "langchain-anthropic>=1.3.0",
            "langgraph-checkpoint-sqlite>=3.0.0",
            "fastapi>=0.115.0",
            "uvicorn[standard]>=0.34.0",
            "openai>=1.0.0",
            "anthropic>=0.40.0",
            "python-dotenv>=1.0.0",
            "python-multipart>=0.0.7",
            "tzdata>=2024.1",
        ],
    },
    {
        "name": "基础分析运行时",
        "critical": False,
        "startup": False,
        "packages": [
            "numpy>=1.24.0",
            "pandas>=2.1.0",
            "matplotlib>=3.8.0",
            "tzdata>=2024.1",
        ],
    },
    {
        "name": "数据分析扩展",
        "critical": False,
        "startup": False,
        "packages": [
            "scipy>=1.12.0",
            "statsmodels>=0.14.0",
            "plotly>=5.24.0",
        ],
    },
    {
        "name": "搜索与记忆扩展",
        "critical": False,
        "startup": False,
        "packages": [
            "tavily-python>=0.7.0",
            "jieba>=0.42.1",
        ],
    },
    {
        "name": "文档与表格扩展",
        "critical": False,
        "startup": False,
        "packages": [
            "requests>=2.31.0",
            "python-docx>=1.1.0",
            "pdfplumber>=0.10.0",
            "openpyxl>=3.1.0",
            "pillow>=10.0.0",
            "lxml>=5.0.0",
            "defusedxml>=0.7.1",
            "pypdf>=4.0.0",
            "pdf2image>=1.17.0",
        ],
    },
    {
        "name": "知识库扩展",
        "critical": False,
        "startup": False,
        "packages": [
            "alibabacloud_bailian20231229>=1.0.0",
            "alibabacloud_tea_openapi>=0.3.0",
            "alibabacloud_tea_util>=0.3.0",
        ],
    },
]


class DependencyInstaller:
    """依赖安装管理器"""

    def __init__(self, python_executable: str | None = None):
        self.python: str = self._resolve_python_executable(python_executable)
        self.uv_path: str | None = self._find_uv()
        self.installed: list[str] = []
        self.failed: list[tuple[str, str]] = []  # (package, error)
        self.critical_failed: list[str] = []

    def _resolve_python_executable(self, python_executable: str | None) -> str:
        """定位目标解释器：显式参数 > PYTHON_EXECUTABLE > sys.executable。"""
        for candidate in (
            python_executable,
            os.environ.get("PYTHON_EXECUTABLE"),
            sys.executable,
        ):
            if candidate and os.path.isfile(candidate):
                return candidate
        return python_executable or os.environ.get("PYTHON_EXECUTABLE") or sys.executable

    def _find_uv(self) -> str | None:
        """查找 uv 可执行文件"""
        uv_embedded = Path(self.python).parent / "Scripts" / "uv.exe"
        if uv_embedded.exists():
            return str(uv_embedded)

        try:
            result = subprocess.run(
                ["where", "uv"] if sys.platform == "win32" else ["which", "uv"],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip().split("\n")[0]
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

        return None

    def _reset_run_state(self):
        self.installed = []
        self.failed = []
        self.critical_failed = []

    def get_extension_stage_names(self) -> list[str]:
        return [stage["name"] for stage in DEPENDENCY_STAGES if not stage.get("startup", False)]

    def _get_stage_plan(self, startup_only: bool) -> tuple[list[dict], list[str]]:
        stages = [
            stage for stage in DEPENDENCY_STAGES
            if not startup_only or stage.get("startup", False)
        ]
        skipped = [
            stage["name"] for stage in DEPENDENCY_STAGES
            if startup_only and not stage.get("startup", False)
        ]
        return stages, skipped

    def _probe_core_dependencies(self) -> tuple[list[str], str]:
        """用目标解释器检查首启核心依赖与时区数据。"""
        probe_code = f"""
import importlib
import json
missing = []
for name in {CORE_MODULES!r}:
    try:
        importlib.import_module(name)
    except Exception:
        missing.append(name)
try:
    from zoneinfo import ZoneInfo
    ZoneInfo("Asia/Shanghai")
except Exception:
    missing.append("tzdata")
print(json.dumps(missing, ensure_ascii=False))
"""
        try:
            result = subprocess.run(
                [self.python, "-c", probe_code],
                capture_output=True,
                text=True,
                timeout=60,
                encoding="utf-8",
                errors="replace",
            )
        except FileNotFoundError:
            return CORE_MODULES + ["tzdata"], f"Python interpreter not found: {self.python}"
        except Exception as e:
            return CORE_MODULES + ["tzdata"], str(e)

        if result.returncode != 0:
            error = (result.stderr or result.stdout or "Dependency probe failed").strip()
            return CORE_MODULES + ["tzdata"], error

        try:
            missing = json.loads((result.stdout or "[]").strip() or "[]")
        except json.JSONDecodeError:
            return CORE_MODULES + ["tzdata"], f"Unexpected probe output: {(result.stdout or '').strip()}"

        return missing, ""

    def _install_with_uv(self, packages: list[str]) -> tuple[bool, str]:
        """使用 uv 安装包，返回 (success, error_message)"""
        if not self.uv_path:
            return False, "uv not found"

        cmd = [
            self.uv_path,
            "pip", "install",
            "--python", self.python,
            "--index-url", ALIBABA_PYPI_MIRROR,
            "--no-cache-dir",
        ] + packages

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
                encoding="utf-8",
                errors="replace",
            )
            if result.returncode == 0:
                return True, ""
            return False, result.stderr or "Unknown error"
        except subprocess.TimeoutExpired:
            return False, "Installation timeout (5 minutes)"
        except Exception as e:
            return False, str(e)

    def _install_with_pip(self, packages: list[str]) -> tuple[bool, str]:
        """使用 pip 安装包（降级方案）"""
        cmd = [
            self.python, "-m", "pip", "install",
            "--index-url", ALIBABA_PYPI_MIRROR,
            "--no-cache-dir",
            "--no-warn-script-location",
        ] + packages

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,
                encoding="utf-8",
                errors="replace",
            )
            if result.returncode == 0:
                return True, ""
            return False, result.stderr or "Unknown error"
        except subprocess.TimeoutExpired:
            return False, "Installation timeout (10 minutes)"
        except Exception as e:
            return False, str(e)

    async def install_stage(self, stage: dict, progress_callback=None) -> bool:
        """安装一个阶段的依赖"""
        stage_name = stage["name"]
        packages = stage["packages"]
        is_critical = stage.get("critical", False)

        if progress_callback:
            progress_callback(f"Installing {stage_name}...", 0, len(packages))

        success, error = self._install_with_uv(packages)

        if not success:
            logger.warning("uv failed for %s: %s, falling back to pip", stage_name, error)
            if progress_callback:
                progress_callback(f"{stage_name}: uv failed, using pip...", 0, len(packages))
            success, error = self._install_with_pip(packages)

        if success:
            self.installed.extend(packages)
            if progress_callback:
                progress_callback(f"{stage_name}: OK", len(packages), len(packages))
            return True

        for pkg in packages:
            self.failed.append((pkg, error))
        if is_critical:
            self.critical_failed.append(stage_name)
        if progress_callback:
            progress_callback(f"{stage_name}: FAILED - {error}", 0, len(packages))
        return False

    async def _install_by_mode(self, startup_only: bool, progress_callback=None) -> dict:
        self._reset_run_state()
        missing_before, probe_error = self._probe_core_dependencies()
        stages, skipped_stage_names = self._get_stage_plan(startup_only)
        installed_stage_names: list[str] = []
        total_stages = len(stages)

        for i, stage in enumerate(stages):
            if progress_callback:
                progress_callback(
                    f"Stage {i+1}/{total_stages}: {stage['name']}",
                    i,
                    total_stages,
                )

            success = await self.install_stage(stage, progress_callback)
            if success:
                installed_stage_names.append(stage["name"])

        missing_after, verify_error = self._probe_core_dependencies()
        verified = len(missing_after) == 0
        if not verified and "核心依赖校验" not in self.critical_failed:
            self.critical_failed.append("核心依赖校验")

        can_start = len(self.critical_failed) == 0 and verified

        return {
            "success": can_start,
            "installed": self.installed,
            "failed": self.failed,
            "critical_failed": self.critical_failed,
            "can_start": can_start,
            "python": self.python,
            "uv_path": self.uv_path,
            "verified": verified,
            "missing_before": missing_before,
            "missing_after": missing_after,
            "probe_error": verify_error or probe_error,
            "mode": "startup" if startup_only else "full",
            "installed_stages": installed_stage_names,
            "skipped_stages": skipped_stage_names,
        }

    async def install_startup(self, progress_callback=None) -> dict:
        """仅安装首启最小必要依赖。"""
        return await self._install_by_mode(startup_only=True, progress_callback=progress_callback)

    async def install_all(self, progress_callback=None) -> dict:
        """安装所有依赖（包含可选扩展）。"""
        return await self._install_by_mode(startup_only=False, progress_callback=progress_callback)

    def probe_core_dependencies(self) -> tuple[list[str], str]:
        """返回缺失的核心依赖列表与探测错误信息。"""
        return self._probe_core_dependencies()

    def check_core_dependencies(self) -> bool:
        """检查首启最小必要依赖是否已安装。"""
        missing, _ = self.probe_core_dependencies()
        return len(missing) == 0


_installer: DependencyInstaller | None = None


def get_installer(python_executable: str | None = None) -> DependencyInstaller:
    """获取或创建安装器实例"""
    global _installer
    if _installer is None:
        _installer = DependencyInstaller(python_executable)
    return _installer


async def ensure_dependencies(
    python_executable: str | None = None,
    progress_callback=None,
    install_optional: bool = False,
) -> dict[str, object]:
    """
    确保依赖已安装（默认仅安装首启最小必要依赖）。

    Args:
        python_executable: Python 解释器路径
        progress_callback: 进度回调函数
        install_optional: 是否同时安装可选扩展依赖

    Returns:
        安装结果字典
    """
    installer = get_installer(python_executable)
    missing_before, probe_error = installer._probe_core_dependencies()

    if not missing_before:
        return {
            "success": True,
            "installed": [],
            "failed": [],
            "critical_failed": [],
            "can_start": True,
            "skipped": True,
            "python": installer.python,
            "uv_path": installer.uv_path,
            "verified": True,
            "missing_before": [],
            "missing_after": [],
            "probe_error": probe_error,
            "mode": "full" if install_optional else "startup",
            "installed_stages": [],
            "skipped_stages": [] if install_optional else installer.get_extension_stage_names(),
        }

    if install_optional:
        return await installer.install_all(progress_callback)
    return await installer.install_startup(progress_callback)


if __name__ == "__main__":
    async def print_progress(msg, cur, total):
        print(f"[{cur}/{total}] {msg}")

    result = asyncio.run(ensure_dependencies(progress_callback=print_progress))
    print("\nResult:", result)
