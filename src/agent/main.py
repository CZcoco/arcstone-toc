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
from src.agent.prompts import (
    ECON_SYSTEM_PROMPT,
    TOPIC_AGENT_PROMPT,
    LITERATURE_AGENT_PROMPT,
    EMPIRICAL_AGENT_PROMPT,
    WRITING_AGENT_PROMPT,
)
from src.store import SqliteStore
from src.tools.rag import bailian_rag
from src.tools.search import internet_search, fetch_website
from src.tools.code_runner import run_python
from src.tools.pdf_reader import read_pdf
from src.tools.read_image import read_image
from src.tools.memory_search import memory_search

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
    model_name: str = "claude-sonnet",
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
        ],
        subagents=[
            {
                "name": "topic-agent",
                "description": "当用户提出一个研究方向/领域和当前研究想法和兴趣后，负责结合可获得的数据（公开和用户提供）和文献，策划出切实可行论文选题。",
                "system_prompt": TOPIC_AGENT_PROMPT,
                "tools": [internet_search, fetch_website, bailian_rag, run_python],
            },
        #     {
        #         "name": "literature-agent",
        #         "description": "用于搜索和整理学术文献、生成参考文献列表。调用时机：选题确定后，需要文献综述时；或需要验证某篇引用是否真实存在时。",
        #         "system_prompt": LITERATURE_AGENT_PROMPT,
        #         "tools": [internet_search, fetch_website, bailian_rag, run_python],
        #     },
            {
                "name": "empirical-agent",
                "description": "用于实证分析：主要使用python进行数据清洗，stata skill执行回归、生成表格和图表。调用时机：数据和选题都确定后，需要执行计量经济学分析时。",
                "system_prompt": EMPIRICAL_AGENT_PROMPT,
                "tools": [run_python, read_image],
            },
            {
                "name": "writing-agent",
                "description": "用于撰写论文章节和生成 Word 文档。调用时机：文献综述和实证结果都已就绪，需要整合写作时。",
                "system_prompt": WRITING_AGENT_PROMPT,
                "tools": [run_python, read_image, read_pdf],
            },
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
