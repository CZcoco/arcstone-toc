"""
Arcstone-econ API - FastAPI 应用入口
"""
import sys
import os
import json
import shutil
import sqlite3
import logging
import threading
from contextlib import asynccontextmanager

_INSTALL_ROOT_ENV = os.environ.get("ARCSTONE_ECON_INSTALL_ROOT")
if _INSTALL_ROOT_ENV:
    ROOT_DIR = _INSTALL_ROOT_ENV
else:
    ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT_DIR, ".env"))

from src.settings import apply_settings_to_environ

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from langgraph.checkpoint.sqlite import SqliteSaver

from src.agent.main import create_econ_agent, DATA_DIR, SKILLS_DIR, DEFAULT_WORKSPACE_DIR
from src.agent.config import NEW_API_BASE_URL
from src.store import SqliteStore


def _emit_startup_status(event: str, *, title: str, detail: str = "", current: int | None = None, total: int | None = None, status: str = "info", extra: dict[str, object] | None = None):
    payload: dict[str, object] = {
        "event": event,
        "status": status,
        "title": title,
        "detail": detail,
    }
    if current is not None:
        payload["current"] = current
    if total is not None:
        payload["total"] = total
    if extra:
        payload.update(extra)
    print(f"ARCSTONE_STATUS={json.dumps(payload, ensure_ascii=False)}", flush=True)


class AgentManager:
    """按 (model_name, workspace_dir) 缓存 agent 实例，共享 store 和 checkpointer。"""

    def __init__(self, store: SqliteStore, checkpointer: SqliteSaver, workspace_dir: str):
        self.store = store
        self.checkpointer = checkpointer
        self._agents: dict = {}
        self._lock = threading.Lock()
        self._custom_prompt: str | None = None
        self._workspace_dir: str = workspace_dir

    def get(self, model_name: str = "deepseek-chat", workspace_dir: str | None = None):
        ws = workspace_dir or self._workspace_dir
        cache_key = (model_name, ws)
        with self._lock:
            if cache_key not in self._agents:
                agent, _, _ = create_econ_agent(
                    model_name=model_name,
                    store=self.store,
                    checkpointer=self.checkpointer,
                    system_prompt=self._custom_prompt,
                    workspace_dir=ws,
                )
                self._agents[cache_key] = agent
            return self._agents[cache_key]

    def set_system_prompt(self, prompt: str | None):
        """更新自定义 system prompt 并清除 agent 缓存，下次 get() 时重建。"""
        with self._lock:
            self._custom_prompt = prompt
            self._agents.clear()

    def set_workspace(self, path: str):
        """切换全局默认工作区目录。不清缓存（agent 按 workspace 分别缓存）。"""
        from src.tools.path_resolver import set_virtual_root
        with self._lock:
            self._workspace_dir = path
        set_virtual_root("/workspace/", path)

    def invalidate_cache(self):
        """清除 agent 缓存，下次 get() 时重建（用于配置变更后）。"""
        with self._lock:
            self._agents.clear()

    def available_models(self) -> list[dict]:
        """从 New API 动态获取可用模型列表"""
        import httpx
        token = os.environ.get("ECON_USER_TOKEN", "")
        if not token:
            return []
        try:
            resp = httpx.get(
                f"{NEW_API_BASE_URL}/models",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json().get("data", [])
            return [
                {
                    "id": m["id"],
                    "name": m.get("name", m["id"]),
                    "model": m["id"],
                    "available": True,
                }
                for m in data
            ]
        except Exception:
            return []


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时创建共享 store/checkpointer 和 AgentManager"""
    os.makedirs(DATA_DIR, exist_ok=True)

    # --- 安装目录（模板文件所在地）---
    INSTALL_ROOT = ROOT_DIR

    # --- 旧数据迁移（从安装目录 data/ 迁移到用户数据目录，优先于模板复制）---
    old_data_dir = os.path.join(INSTALL_ROOT, "data")
    if os.path.normpath(old_data_dir) != os.path.normpath(DATA_DIR):
        for fname in ("memories.db", "checkpoints.db", "settings.json", "store.db"):
            old_file = os.path.join(old_data_dir, fname)
            new_file = os.path.join(DATA_DIR, fname)
            if os.path.exists(old_file) and not os.path.exists(new_file):
                shutil.move(old_file, new_file)
        old_skills = os.path.join(INSTALL_ROOT, "skills")
        if os.path.isdir(old_skills) and not os.path.exists(SKILLS_DIR):
            shutil.copytree(old_skills, SKILLS_DIR)
            shutil.rmtree(old_skills, ignore_errors=True)
        old_workspace = os.path.join(old_data_dir, "workspace")
        new_workspace = os.path.join(DATA_DIR, "workspace")
        if os.path.isdir(old_workspace) and not os.path.exists(new_workspace):
            shutil.copytree(old_workspace, new_workspace)
            shutil.rmtree(old_workspace, ignore_errors=True)

    # --- 首次启动：从安装目录模板复制到用户数据目录（仅迁移后仍缺失时）---
    settings_default = os.path.join(INSTALL_ROOT, "data", "settings.default.json")
    settings_target = os.path.join(DATA_DIR, "settings.json")
    if not os.path.exists(settings_target) and os.path.exists(settings_default):
        shutil.copy2(settings_default, settings_target)

    skills_default = os.path.join(INSTALL_ROOT, "skills.default")
    if os.path.exists(skills_default) and (
        not os.path.exists(SKILLS_DIR) or not os.listdir(SKILLS_DIR)
    ):
        shutil.copytree(skills_default, SKILLS_DIR, dirs_exist_ok=True)

    db_path = os.path.join(DATA_DIR, "memories.db")
    checkpoint_path = os.path.join(DATA_DIR, "checkpoints.db")

    store = SqliteStore(db_path)
    os.makedirs(os.path.dirname(os.path.abspath(checkpoint_path)), exist_ok=True)
    checkpoint_conn = sqlite3.connect(checkpoint_path, check_same_thread=False)
    checkpointer = SqliteSaver(checkpoint_conn)

    # 注册语义检索引擎（供 Agent 工具全局访问）
    from src.memory_search import set_global_search_engine
    set_global_search_engine(store.search_engine)

    # settings.json 覆盖 os.environ（在 load_dotenv 之后，backfill 之前，确保 DASHSCOPE_API_KEY 可用）
    apply_settings_to_environ(DATA_DIR)

    # 后台线程索引已有记忆，不阻塞启动
    def _backfill_in_background():
        try:
            indexed = store.search_engine.backfill()
            if indexed:
                logging.getLogger(__name__).info("Backfilled %d memory files into search index", indexed)
        except Exception:
            logging.getLogger(__name__).exception("Background backfill failed")

    threading.Thread(target=_backfill_in_background, daemon=True).start()

    # --- 首次启动：自动安装 Python 依赖（v0.6.0 在线安装版）---
    try:
        from src.api.dependency_installer import DependencyInstaller
        from langgraph.store.base import PutOp

        target_python = os.environ.get("PYTHON_EXECUTABLE")
        installer = DependencyInstaller(target_python)
        _emit_startup_status(
            "dependency_check",
            status="info",
            title="检查启动依赖",
            detail="正在检查最小启动依赖是否已就绪。",
            extra={"python": installer.python},
        )
        missing_before, probe_error = installer.probe_core_dependencies()

        def report_install_progress(message: str, current: int, total: int):
            event = "install_progress"
            status = "info"
            title = "正在安装启动依赖"
            detail = message
            display_current: int | None = None
            display_total: int | None = None

            if message.startswith("Stage "):
                title = "准备安装依赖阶段"
                display_current = current + 1
                display_total = total
            elif "uv failed, using pip" in message:
                event = "install_fallback"
                status = "warning"
                title = "uv 安装失败，切换 pip"
            elif message.endswith(": OK"):
                status = "success"
                title = "依赖阶段完成"
            elif ": FAILED - " in message:
                status = "error"
                title = "依赖阶段失败"

            _emit_startup_status(
                event,
                status=status,
                title=title,
                detail=detail,
                current=display_current,
                total=display_total,
            )

        if missing_before:
            _emit_startup_status(
                "install_required",
                status="warning",
                title="首次启动需要安装依赖",
                detail=f"缺少 {len(missing_before)} 项核心依赖，正在联网安装最小启动集。",
                extra={"missing": missing_before, "python": installer.python},
            )
            logging.getLogger(__name__).info(
                "First launch detected, installing minimum startup dependencies into %s...",
                installer.python,
            )
            result = await installer.install_startup(progress_callback=report_install_progress)
            _emit_startup_status(
                "dependency_verify",
                status="info",
                title="校验安装结果",
                detail="正在确认核心依赖是否已就绪。",
                extra={"verified": result.get("verified", False)},
            )
            status = "ok" if result["can_start"] else "failed"
            store.batch([
                PutOp(
                    namespace=("settings",),
                    key="install_status",
                    value={
                        "status": status,
                        "python": result.get("python"),
                        "verified": result.get("verified", False),
                        "missing_before": result.get("missing_before", []),
                        "missing_after": result.get("missing_after", []),
                        "failed_packages": [p for p, _ in result["failed"]],
                        "installed_stages": result.get("installed_stages", []),
                        "skipped_stages": result.get("skipped_stages", []),
                        "message": (
                            "Minimum startup dependencies installed successfully"
                            if result["can_start"]
                            else f"Core dependencies failed: {result['critical_failed']}"
                        ),
                    }
                )
            ])
            if result["can_start"]:
                _emit_startup_status(
                    "install_complete",
                    status="success",
                    title="启动依赖已就绪",
                    detail="最小启动依赖安装完成，正在继续启动后端服务。",
                    extra={
                        "installed_stages": result.get("installed_stages", []),
                        "skipped_stages": result.get("skipped_stages", []),
                    },
                )
                logging.getLogger(__name__).info(
                    "Startup dependencies installed into %s: %d packages, failed: %d, skipped optional stages: %s",
                    result.get("python"),
                    len(result["installed"]),
                    len(result["failed"]),
                    result.get("skipped_stages", []),
                )
            else:
                _emit_startup_status(
                    "install_complete",
                    status="error",
                    title="启动依赖安装失败",
                    detail=f"核心依赖未通过校验：{result['critical_failed']}",
                    extra={
                        "missing_after": result.get("missing_after", []),
                        "critical_failed": result.get("critical_failed", []),
                    },
                )
                logging.getLogger(__name__).error(
                    "Critical dependencies failed for %s: %s (missing_after=%s)",
                    result.get("python"),
                    result["critical_failed"],
                    result.get("missing_after", []),
                )
        else:
            store.batch([
                PutOp(
                    namespace=("settings",),
                    key="install_status",
                    value={
                        "status": "skipped",
                        "python": installer.python,
                        "verified": True,
                        "missing_before": [],
                        "missing_after": [],
                        "failed_packages": [],
                        "installed_stages": [],
                        "skipped_stages": installer.get_extension_stage_names(),
                        "message": "Minimum startup dependencies already available",
                    }
                )
            ])
            _emit_startup_status(
                "install_skipped",
                status="success",
                title="启动依赖已就绪",
                detail="最小启动依赖已存在，跳过首启安装。",
                extra={"python": installer.python, "probe_error": probe_error},
            )
    except Exception as e:
        _emit_startup_status(
            "install_error",
            status="error",
            title="依赖检查异常",
            detail=str(e),
        )
        logging.getLogger(__name__).warning("Dependency check skipped: %s", e)

    # 读取持久化的工作区路径（没有则用默认值）
    ws_item = store.get(("settings",), "workspace_dir")
    workspace_dir = DEFAULT_WORKSPACE_DIR
    if ws_item and isinstance(ws_item.value, dict) and ws_item.value.get("path"):
        candidate = ws_item.value["path"]
        if os.path.isdir(candidate):
            workspace_dir = candidate
    os.makedirs(workspace_dir, exist_ok=True)

    # 注册虚拟路径映射，让 subprocess 工具能把 /workspace/、/skills/ 转成真实磁盘路径
    from src.tools.path_resolver import set_virtual_root
    set_virtual_root("/workspace/", workspace_dir)
    set_virtual_root("/skills/", SKILLS_DIR)

    os.makedirs(SKILLS_DIR, exist_ok=True)

    manager = AgentManager(store, checkpointer, workspace_dir)

    # 恢复用户自定义的 system prompt（多版本系统）
    active_pid = store.get(("settings",), "active_prompt_id")
    if active_pid and isinstance(active_pid.value, dict) and active_pid.value.get("id"):
        vid = active_pid.value["id"]
        pv = store.get(("settings",), "prompt_versions")
        if pv and isinstance(pv.value, dict):
            for v in pv.value.get("versions", []):
                if v["id"] == vid and v.get("content"):
                    manager.set_system_prompt(v["content"])
                    break

    app.state.agent_manager = manager
    app.state.store = store
    app.state.checkpointer = checkpointer

    # 知识库管理已迁移到服务端 RAG 代理
    app.state.kb_manager = None

    yield

    checkpoint_conn.close()
    if hasattr(store, "conn"):
        store.conn.close()


app = FastAPI(title="Arcstone-econ API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
from src.api.routes import router
app.include_router(router, prefix="/api")

# 如果前端已 build，直接 serve 静态文件（生产模式）
DIST_DIR = os.path.join(ROOT_DIR, "frontend", "dist")
if os.path.isdir(DIST_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(DIST_DIR, "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_frontend(full_path: str):
        return FileResponse(os.path.join(DIST_DIR, "index.html"))
