"""
Arcstone-econ API - FastAPI 应用入口
"""
import sys
import os
import shutil
import sqlite3
import logging
import threading
from contextlib import asynccontextmanager

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
from src.agent.config import MODEL_CONFIG
from src.store import SqliteStore


class AgentManager:
    """按 model_name 缓存 agent 实例，共享 store 和 checkpointer。"""

    def __init__(self, store: SqliteStore, checkpointer: SqliteSaver, workspace_dir: str):
        self.store = store
        self.checkpointer = checkpointer
        self._agents: dict = {}
        self._lock = threading.Lock()
        self._custom_prompt: str | None = None
        self._workspace_dir: str = workspace_dir

    def get(self, model_name: str = "deepseek"):
        with self._lock:
            if model_name not in self._agents:
                agent, _, _ = create_econ_agent(
                    model_name=model_name,
                    store=self.store,
                    checkpointer=self.checkpointer,
                    system_prompt=self._custom_prompt,
                    workspace_dir=self._workspace_dir,
                )
                self._agents[model_name] = agent
            return self._agents[model_name]

    def set_system_prompt(self, prompt: str | None):
        """更新自定义 system prompt 并清除 agent 缓存，下次 get() 时重建。"""
        with self._lock:
            self._custom_prompt = prompt
            self._agents.clear()

    def set_workspace(self, path: str):
        """切换工作区目录，清除 agent 缓存，下次 get() 时以新路径重建。"""
        from src.tools.path_resolver import set_virtual_root
        with self._lock:
            self._workspace_dir = path
            self._agents.clear()
        set_virtual_root("/workspace/", path)

    def invalidate_cache(self):
        """清除 agent 缓存，下次 get() 时重建（用于配置变更后）。"""
        with self._lock:
            self._agents.clear()

    def available_models(self) -> list[dict]:
        """返回可用模型列表（有 API Key 的才算可用）"""
        models = []
        for name, cfg in MODEL_CONFIG.items():
            has_key = bool(os.getenv(cfg["env_key"]))
            models.append({
                "id": name,
                "name": name,
                "model": cfg["model"],
                "available": has_key,
            })
        return models


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
    if not os.path.exists(SKILLS_DIR) and os.path.exists(skills_default):
        shutil.copytree(skills_default, SKILLS_DIR)

    db_path = os.path.join(DATA_DIR, "memories.db")
    checkpoint_path = os.path.join(DATA_DIR, "checkpoints.db")

    store = SqliteStore(db_path)
    os.makedirs(os.path.dirname(os.path.abspath(checkpoint_path)), exist_ok=True)
    checkpoint_conn = sqlite3.connect(checkpoint_path, check_same_thread=False)
    checkpointer = SqliteSaver(checkpoint_conn)

    # 注册语义检索引擎（供 Agent 工具全局访问）+ 索引已有记忆
    from src.memory_search import set_global_search_engine
    set_global_search_engine(store.search_engine)
    indexed = store.search_engine.backfill()
    if indexed:
        logging.getLogger(__name__).info("Backfilled %d memory files into search index", indexed)

    # settings.json 覆盖 os.environ（在 load_dotenv 之后）
    apply_settings_to_environ(DATA_DIR)

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

    # 初始化百炼知识库管理器（可选，需要环境变量）
    if os.environ.get("BAILIAN_WORKSPACE_ID") and os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_ID"):
        try:
            from src.tools.kb_uploader import BailianKBManager
            app.state.kb_manager = BailianKBManager()
            logging.getLogger(__name__).info("BailianKBManager initialized")
        except Exception as e:
            logging.getLogger(__name__).warning("Failed to init BailianKBManager: %s", e)
            app.state.kb_manager = None
    else:
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
