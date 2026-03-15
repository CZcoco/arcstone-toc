# econ-agent

> 基于 LangChain Deep Agents 的经济学论文智能体，面向国内本科经济学生的毕业论文全流程助手。

## 项目一句话

用户给一句研究想法，`econ-agent` 自动协助完成选题、文献检索、数据获取、实证分析和 Word 论文输出。

## 当前定位

这个仓库最初来自矿业投资智能体 `Arcstone`，但现在已经作为独立新项目继续演进，业务层完全切换为经济学论文场景：

- 主 Agent 已改为 `create_econ_agent()`
- 主 Prompt 和 4 个 sub-agent Prompt 已改为论文工作流
- `skills/literature` 与 `skills/data` 已用于文献与数据获取
- 记忆、SSE、会话管理、工作区、前端框架继续复用

## 核心能力

| 模块 | 能力 |
|------|------|
| 选题 | 根据研究方向、数据可得性、文献基础，给出 2-3 个本科可落地选题 |
| 文献 | 通过 OpenAlex / Semantic Scholar 检索并验证真实文献，避免引用幻觉 |
| 数据 | 通过 World Bank / 国家统计局 / FRED / IMF / Comtrade 脚本拉取公开数据 |
| 实证 | 用 Python 执行描述统计、回归分析、出图出表 |
| 写作 | 汇总结果，生成论文草稿和 `.docx` 文件 |
| 记忆 | 记住用户偏好、论文草稿、历史会话和工作区产物 |

## 核心架构

```text
用户（Electron / 终端）
    ↓
FastAPI + SSE
    ↓
create_econ_agent()
    ├── tools: bailian_rag / internet_search / fetch_website
    │         / run_python / read_pdf / read_image / memory_search
    ├── topic-agent
    ├── literature-agent
    ├── empirical-agent
    └── writing-agent
```

详细架构见 [docs/econ/architecture.md](./docs/econ/architecture.md)。

## 关键目录

| 路径 | 说明 |
|------|------|
| [src/agent/main.py](./src/agent/main.py) | `create_econ_agent()` 工厂函数 |
| [src/agent/prompts.py](./src/agent/prompts.py) | 主 Prompt + 4 个 sub-agent Prompt |
| [src/api/app.py](./src/api/app.py) | FastAPI 入口和 AgentManager |
| [skills/literature](./skills/literature) | 文献检索 skill |
| [skills/data](./skills/data) | 数据获取 skill |
| [docs/econ/architecture.md](./docs/econ/architecture.md) | 经济学论文版本架构说明 |
| [docs/dev/refined-development.md](./docs/dev/refined-development.md) | 当前开发速查手册 |

## 数据与安装隔离

这是一个全新项目，安装和运行时数据不应与旧 `Arcstone` 重叠。

- Electron 安装包标识使用 `econ-agent`
- 用户数据目录使用 `%APPDATA%/econ-agent/`
- Python 侧环境变量使用 `ECON_AGENT_USER_DATA`
- 前端 localStorage key 使用 `econ-agent-*`

旧矿业文档仍保留在 `docs/` 中，仅作历史参考，不参与当前产品身份定义。
