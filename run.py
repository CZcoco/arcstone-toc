"""
Arcstone-econ - 终端运行脚本（流式输出）
"""
import sys
import os
import uuid

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT_DIR, ".env"))

from langchain_core.messages import AIMessage, AIMessageChunk, ToolMessage


def _extract_text(content) -> str:
    """从 message.content 提取纯文本（兼容 Anthropic list 格式）。"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
        )
    return str(content)
from src.agent.main import create_econ_agent

# --- 终端颜色 ---
GRAY = "\033[90m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
BOLD = "\033[1m"
RESET = "\033[0m"


def print_status(text: str):
    """灰色状态信息"""
    print(f"{GRAY}  {text}{RESET}")


def print_tool_call(name: str, args: dict):
    """显示工具调用"""
    args_summary = ", ".join(f"{k}={repr(v)[:60]}" for k, v in args.items())
    print(f"{YELLOW}  ⚡ 调用工具: {name}({args_summary}){RESET}")


def print_tool_result(name: str, content: str):
    """显示工具返回（截断）"""
    preview = content[:200].replace("\n", " ")
    if len(content) > 200:
        preview += "..."
    print(f"{GREEN}  ✓ {name} 返回: {preview}{RESET}")


def stream_agent(agent, user_input: str, config: dict):
    """流式运行 Agent，实时显示思考过程和工具调用"""
    print()

    # 用 stream_mode=["messages", "updates"] 同时获取 token 流和步骤更新
    ai_text_started = False
    current_tool_calls = {}

    for stream_mode, data in agent.stream(
        {"messages": [{"role": "user", "content": user_input}]},
        config=config,
        stream_mode=["messages", "updates"],
    ):
        if stream_mode == "messages":
            token, metadata = data
            node = metadata.get("langgraph_node", "")

            # AI 文本 token 流式输出
            if isinstance(token, AIMessageChunk):
                # 检查是否有工具调用 chunk
                if token.tool_call_chunks:
                    for tc in token.tool_call_chunks:
                        call_id = tc.get("id") or tc.get("index", "")
                        if call_id and call_id not in current_tool_calls:
                            current_tool_calls[call_id] = True
                            if ai_text_started:
                                print()  # 换行，从文本输出切到工具调用
                                ai_text_started = False
                            print_status("思考中...")
                # 文本内容流式打印
                elif hasattr(token, "content") and token.content:
                    text = _extract_text(token.content)
                    if text:
                        if not ai_text_started:
                            print(f"{BOLD}AI:{RESET} ", end="", flush=True)
                            ai_text_started = True
                        print(text, end="", flush=True)

        elif stream_mode == "updates":
            if not isinstance(data, dict):
                continue
            for node_name, update in data.items():
                if not isinstance(update, dict):
                    continue
                if node_name == "tools":
                    # 工具节点完成，显示工具调用和结果
                    messages = update.get("messages", [])
                    for msg in messages:
                        if isinstance(msg, ToolMessage):
                            content = _extract_text(msg.content)
                            print_tool_result(msg.name, content)
                elif node_name == "agent" or node_name == "model":
                    messages = update.get("messages", [])
                    for msg in messages:
                        if isinstance(msg, AIMessage) and msg.tool_calls:
                            for tc in msg.tool_calls:
                                print_tool_call(tc["name"], tc["args"])

    # 最终换行
    if ai_text_started:
        print()
    print()


DATA_DIR = os.path.join(ROOT_DIR, "data")
THREAD_ID_FILE = os.path.join(DATA_DIR, "thread_id.txt")


def load_thread_id() -> str:
    """读取或创建 thread_id"""
    os.makedirs(DATA_DIR, exist_ok=True)
    if os.path.exists(THREAD_ID_FILE):
        with open(THREAD_ID_FILE, "r") as f:
            tid = f.read().strip()
            if tid:
                return tid
    return new_thread_id()


def new_thread_id() -> str:
    """生成并保存新 thread_id"""
    tid = str(uuid.uuid4())
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(THREAD_ID_FILE, "w") as f:
        f.write(tid)
    return tid


ARCHIVE_PROMPT = (
    "请回顾我们这次的完整对话，将有价值的信息归档到 /memories/。具体要求：\n"
    "1. 如果讨论了具体项目，将项目的关键数据、分析结论、待办事项完整写入 /memories/projects/{项目名}.md\n"
    "2. 如果有投资决策，写入 /memories/decisions/{日期}_{项目}_{决策}.md\n"
    "3. 如果发现了新的用户偏好或我纠正了你的错误，更新 /memories/user_profile.md 或 /memories/instructions.md\n"
    "4. 归档内容要详细、有结构，包含具体数据和数字，不要只写结论\n"
    "请直接执行归档，完成后简要告诉我归档了哪些内容。"
)


def archive_conversation(agent, config: dict):
    """归档当前会话——让 Agent 提取完整对话信息写入记忆"""
    print(f"\n{GRAY}  正在归档对话...{RESET}")
    stream_agent(agent, ARCHIVE_PROMPT, config)


def count_memory_files(store) -> int:
    """统计记忆文件数"""
    items = store.search(("filesystem",))
    return len(items)


def main():
    model_name = sys.argv[1] if len(sys.argv) > 1 else "claude-sonnet"
    os.environ["CURRENT_MODEL"] = model_name

    print(f"{BOLD}Arcstone-econ{RESET}")
    print(f"{GRAY}模型: {model_name} | 输入 exit 退出{RESET}")
    print(f"{GRAY}命令: /new 新会话 | /memory 查看记忆 | /archive 归档对话{RESET}")
    print(f"{GRAY}{'─' * 50}{RESET}")

    agent, store, checkpointer = create_econ_agent(model_name=model_name)
    thread_id = load_thread_id()
    config = {"configurable": {"thread_id": thread_id}}

    mem_count = count_memory_files(store)
    if mem_count > 0:
        print(f"{GREEN}  已加载 {mem_count} 条记忆{RESET}")

    # 检测是否有上次未完的会话（checkpointer 中有记录）
    existing = checkpointer.get(config)
    if existing:
        print(f"{GREEN}  已恢复上次会话 ({thread_id[:8]}...){RESET}")

    has_conversation = existing is not None

    try:
        while True:
            try:
                user_input = input(f"\n{CYAN}你: {RESET}").strip()
            except (EOFError, KeyboardInterrupt):
                if has_conversation:
                    print(f"\n{GRAY}  提示: 输入 /archive 可以归档本次对话{RESET}")
                print(f"{GRAY}再见！{RESET}")
                break

            if not user_input:
                continue

            if user_input.lower() in ("exit", "quit", "退出"):
                if has_conversation:
                    try:
                        ans = input(f"{GRAY}  是否归档本次对话？(y/n): {RESET}").strip().lower()
                        if ans in ("y", "yes", "是"):
                            archive_conversation(agent, config)
                    except (EOFError, KeyboardInterrupt):
                        pass
                print(f"{GRAY}再见！{RESET}")
                break

            if user_input == "/new":
                if has_conversation:
                    try:
                        ans = input(f"{GRAY}  是否先归档当前对话？(y/n): {RESET}").strip().lower()
                        if ans in ("y", "yes", "是"):
                            archive_conversation(agent, config)
                    except (EOFError, KeyboardInterrupt):
                        pass
                thread_id = new_thread_id()
                config = {"configurable": {"thread_id": thread_id}}
                has_conversation = False
                print(f"{GREEN}  新会话已创建{RESET}")
                continue

            if user_input == "/archive":
                if has_conversation:
                    archive_conversation(agent, config)
                else:
                    print(f"{GRAY}  当前会话没有对话内容{RESET}")
                continue

            if user_input == "/memory":
                items = store.search(("filesystem",), limit=100)
                print(f"{BOLD}  记忆文件 ({len(items)}):{RESET}")
                for item in items:
                    print(f"{GRAY}    /memories{item.key}{RESET}")
                if not items:
                    print(f"{GRAY}    (空){RESET}")
                continue

            try:
                stream_agent(agent, user_input, config)
                has_conversation = True
            except KeyboardInterrupt:
                print(f"\n{GRAY}已中断{RESET}")
            except Exception as e:
                print(f"\n{YELLOW}错误: {e}{RESET}")
    finally:
        # 关闭 checkpointer 持有的 SQLite 连接
        if hasattr(checkpointer, "conn"):
            checkpointer.conn.close()


if __name__ == "__main__":
    main()
