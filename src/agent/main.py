"""
经济学论文智能体 - 主入口
"""
import sys
import os

# 将项目根目录加入 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import sqlite3

from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, StateBackend, StoreBackend
from deepagents.backends.filesystem import FilesystemBackend
from langgraph.checkpoint.sqlite import SqliteSaver

from src.agent.config import get_llm
from src.agent.prompts import ECON_SYSTEM_PROMPT
from src.store import SqliteStore
from src.tools.rag import bailian_rag
from src.tools.search import internet_search, fetch_website
from src.tools.code_runner import run_python
from src.tools.pdf_reader import read_pdf
from src.tools.read_image import read_image
from src.tools.memory_search import memory_search
from src.tools.image_gen import generate_image

_INSTALL_ROOT_ENV = os.environ.get("ARCSTONE_ECON_INSTALL_ROOT")
if _INSTALL_ROOT_ENV:
    _PROJECT_ROOT = _INSTALL_ROOT_ENV
else:
    _PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_user_data = os.environ.get("ARCSTONE_ECON_USER_DATA")
if _user_data:
    DATA_DIR = os.path.join(_user_data, "data")
    SKILLS_DIR = os.path.join(DATA_DIR, "skills")
else:
    # 开发环境 fallback
    DATA_DIR = os.path.join(_PROJECT_ROOT, "data")
    SKILLS_DIR = os.path.join(_PROJECT_ROOT, "skills")
DEFAULT_WORKSPACE_DIR = os.path.join(DATA_DIR, "workspace")
DEFAULT_DB_PATH = os.path.join(DATA_DIR, "memories.db")
DEFAULT_CHECKPOINT_PATH = os.path.join(DATA_DIR, "checkpoints.db")


def create_econ_agent(
    model_name: str = "deepseek-chat",
    db_path: str = DEFAULT_DB_PATH,
    checkpoint_path: str = DEFAULT_CHECKPOINT_PATH,
    store=None,
    checkpointer=None,
    system_prompt: str | None = None,
    workspace_dir: str = DEFAULT_WORKSPACE_DIR,
):
    """创建经济学论文智能体（带持久化记忆和持久化会话）

    Returns:
        (agent, store, checkpointer) 元组。
        agent 是 CompiledStateGraph，store 是 SqliteStore，
        checkpointer 是 SqliteSaver（持有 sqlite3 连接，需要关闭）。

    可传入已有的 store/checkpointer 实现多模型共享。
    """
    llm = get_llm(model_name)

    if store is None:
        store = SqliteStore(db_path)
    if checkpointer is None:
        os.makedirs(os.path.dirname(os.path.abspath(checkpoint_path)), exist_ok=True)
        checkpoint_conn = sqlite3.connect(checkpoint_path, check_same_thread=False)
        checkpointer = SqliteSaver(checkpoint_conn)

    agent = create_deep_agent(
        model=llm,
        tools=[
            bailian_rag,
            internet_search,
            fetch_website,
            run_python,
            read_pdf,
            read_image,
            memory_search,
            generate_image,
        ],
        system_prompt=system_prompt or ECON_SYSTEM_PROMPT,
        store=store,
        backend=lambda rt: CompositeBackend(
            default=StateBackend(rt),
            routes={
                "/memories/": StoreBackend(
                    rt, namespace=lambda ctx: ("filesystem",)
                ),
                "/skills/": FilesystemBackend(
                    root_dir=SKILLS_DIR, virtual_mode=True
                ),
                "/workspace/": FilesystemBackend(
                    root_dir=workspace_dir, virtual_mode=True
                ),
            },
        ),
        skills=["/skills/"],
        checkpointer=checkpointer,
    )

    return agent, store, checkpointer
