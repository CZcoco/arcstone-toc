# 经济学论文智能体 —— 项目架构

## 一句话

用户说一句话（"帮我写一篇关于数字经济对就业的论文"），智能体自动跑完：选题 → 文献综述 → 数据获取 → 实证分析 → Word 论文输出。面向国内本科经济学生的毕业论文全流程助手。

## 系统全貌

```
用户（前端/终端）
    │
    ▼
FastAPI (src/api/app.py)
    │  SSE 流式 (src/api/stream.py)
    │
    ▼
主 Agent (create_econ_agent)
    ├─ tools: bailian_rag, internet_search, fetch_website,
    │         run_python, read_pdf, read_image, memory_search
    │
    ├─ subagent: topic-agent        选题策划
    ├─ subagent: literature-agent   文献综述（零幻觉）
    ├─ subagent: empirical-agent    实证分析
    └─ subagent: writing-agent      论文写作 + Word 生成
```

## 目录结构（核心）

```
D:/econ-agent/
├── src/
│   ├── agent/
│   │   ├── config.py          # 模型配置（deepseek/claude/kimi）
│   │   ├── main.py            # create_econ_agent() 工厂函数 + subagents
│   │   └── prompts.py         # 主 prompt + 4 个 sub-agent prompt
│   ├── api/
│   │   ├── app.py             # FastAPI 入口 + AgentManager
│   │   ├── routes.py          # 全部 HTTP 路由
│   │   └── stream.py          # SSE 流式输出封装
│   ├── tools/
│   │   ├── code_runner.py     # run_python（subprocess 执行）
│   │   ├── pdf_reader.py      # read_pdf（PDF/Word 文档读取）
│   │   ├── read_image.py      # read_image（图片 base64，DeepSeek 降级）
│   │   ├── path_resolver.py   # 虚拟路径 ↔ 真实路径
│   │   ├── rag.py             # bailian_rag（百炼知识库）
│   │   ├── search.py          # internet_search + fetch_website
│   │   ├── memory_search.py   # 语义搜索记忆
│   │   └── calculate.py       # calculate_irr（已从工具列表移除，代码保留）
│   ├── settings.py            # 设置管理（API Key 等）
│   ├── store.py               # SqliteStore 持久化
│   └── memory_search.py       # 全局搜索引擎
├── skills/
│   ├── literature/            # 文献检索 skill
│   │   ├── SKILL.md           #   防幻觉协议 + 使用说明
│   │   └── scripts/
│   │       ├── search_openalex.py    # OpenAlex API（免费）
│   │       └── search_semantic.py    # Semantic Scholar API（免费）
│   ├── data/                  # 数据获取 skill
│   │   ├── SKILL.md           #   五大数据源 + 常用指标速查
│   │   └── scripts/
│   │       ├── get_stats_cn.py       # 国家统计局
│   │       ├── get_world_bank.py     # World Bank（wbgapi）
│   │       ├── get_fred.py           # FRED（需 API Key）
│   │       ├── get_imf.py            # IMF（imfp）
│   │       └── get_comtrade.py       # UN Comtrade
│   ├── pdf/                   # PDF 操作 skill（继承自原项目）
│   └── xlsx/                  # Excel/Word 操作 skill（继承自原项目）
├── data/
│   ├── memories.db            # 持久化记忆
│   ├── checkpoints.db         # LangGraph 会话检查点
│   ├── settings.json          # 用户设置
│   └── workspace/             # 用户可见工作区（论文/数据/图表输出）
├── frontend/                  # React + Electron 前端（不动）
├── run.py                     # 终端交互入口
└── run_api.py                 # API 启动入口
```

## 虚拟路径系统

Agent 和 skills 脚本使用虚拟路径，`path_resolver.py` 自动转换：

| 虚拟路径 | 真实路径 | 用途 |
|----------|----------|------|
| `/workspace/` | `data/workspace/` | 论文、数据、图表输出 |
| `/skills/` | `skills/` | 只读技能文档和脚本 |
| `/memories/` | StoreBackend | 跨会话持久化记忆 |

## 数据流

### 典型论文生成流程

```
1. 用户："帮我写一篇关于数字经济对就业的论文"
       │
2. 主 Agent → topic-agent
       │  扫描 /skills/data/ 看哪些数据可获取
       │  搜索文献评估方向可行性
       │  输出 2-3 个选题候选
       ▼
3. 用户选定选题
       │
4. 主 Agent → literature-agent
       │  调用 search_openalex.py / search_semantic.py
       │  逐条验证 DOI / 摘要（零幻觉）
       │  输出参考文献列表 + 文献综述草稿
       ▼
5. 主 Agent → 数据准备
       │  调用 /skills/data/scripts/ 获取公开数据
       │  或引导用户上传 CSMAR/WIND CSV
       │  保存到 /workspace/data/
       ▼
6. 主 Agent → empirical-agent
       │  读取数据 → 描述性统计 → 回归分析
       │  结果 → /workspace/results/*.csv
       │  图表 → /workspace/figures/*.png
       ▼
7. 主 Agent → writing-agent
       │  整合文献 + 数据 + 实证结果
       │  生成 python-docx Word 文档
       │  保存到 /workspace/paper_数字经济就业.docx
       ▼
8. 用户下载 Word 论文
```

## 三条红线

1. **参考文献零幻觉**：只引用通过 OpenAlex/Semantic Scholar API 验证有真实记录的文献
2. **实证零编造**：所有系数/显著性从 Python/Stata 实际运行输出提取
3. **数据透明**：每个变量标注来源数据集和获取脚本

## 基础设施复用（来自原项目）

以下模块直接复用，不做改动：
- 记忆系统（SqliteStore + 语义搜索）
- SSE 流式输出（stream.py）
- 会话管理（checkpoints.db + thread_id）
- PDF/Word 解析（pdf_reader.py + pdf_parser.py）
- 前端（React + Electron）
- 设置系统（settings.py + settings.json）
- 百炼知识库集成（可选）

## 技术栈

- **框架**：LangChain Deep Agents 0.4.1 + LangGraph
- **模型**：DeepSeek V3.2（128K，开发阶段）/ Claude / Kimi（可切换）
- **后端**：FastAPI + SSE
- **前端**：React + Electron（不动）
- **持久化**：SQLite（记忆 + 检查点 + 设置）
- **数据API**：OpenAlex / Semantic Scholar / World Bank / NBS / FRED / IMF / Comtrade
