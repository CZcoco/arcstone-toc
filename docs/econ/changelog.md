# 改动日志

## 2026-03-10：新增 Claude 订阅线路模型 + GPT-5.4 + 清理直连模型

- `src/agent/config.py`：新增 `claude-opus-plan`、`claude-sonnet-plan`（base_url: apiport.cc.cd，ANTHROPIC_AUTH_TOKEN）和 `gpt`（GPT-5.4，OPENAI_API_KEY）；删除 `claude` 直连条目
- `frontend/src/components/ModelSelector.tsx`：新增 "Claude Opus 4.6 Plan" / "Claude Sonnet 4.6 Plan" / "GPT-5.4" 显示名；删除 "Claude" 直连
- `src/settings.py`：删除 ANTHROPIC_API_KEY 设置项；"Claude (代理)" 改名为 "Claude（API额度）"；新增 OPENAI_API_KEY 设置项
- `src/api/routes.py`：api_key_keys 移除 ANTHROPIC_API_KEY，新增 OPENAI_API_KEY

## 2026-03-05：从矿业智能体改造为经济学论文智能体

### 背景

将 Arcstone（矿业投资智能体）改造为经济学毕业论文生成智能体，面向国内本科经济学生。核心思路：基础设施全部复用（记忆、SSE、会话管理、前端），改动集中在 prompt + agent 工厂 + 新增工具和 skills。

### 新建文件

| 文件 | 说明 |
|------|------|
| `src/tools/read_image.py` | 读取工作区图片转 base64 返回给 agent，DeepSeek 自动降级为文字提示 |
| `skills/literature/SKILL.md` | 文献检索技能文档，含防幻觉协议 |
| `skills/literature/scripts/search_openalex.py` | OpenAlex 免费 API 文献检索，支持中英文 |
| `skills/literature/scripts/search_semantic.py` | Semantic Scholar 免费 API 文献检索，英文效果好 |
| `skills/data/SKILL.md` | 数据获取技能文档，含 5 个数据源说明和常用指标速查 |
| `skills/data/scripts/get_stats_cn.py` | 国家统计局 API 查询 |
| `skills/data/scripts/get_world_bank.py` | World Bank API 查询（wbgapi） |
| `skills/data/scripts/get_fred.py` | FRED API 查询（fredapi，需 FRED_API_KEY） |
| `skills/data/scripts/get_imf.py` | IMF API 查询（imfp） |
| `skills/data/scripts/get_comtrade.py` | UN Comtrade 贸易数据查询 |
| `docs/econ/architecture.md` | 项目架构文档 |
| `docs/econ/changelog.md` | 本文件 |

### 修改文件

| 文件 | 改动内容 |
|------|---------|
| `src/agent/prompts.py` | `MINING_SYSTEM_PROMPT` → `ECON_SYSTEM_PROMPT`；工具指南删 `calculate_irr` 加 `read_image`；**追加**（非替换）经济学论文工作流、三条红线、文献/数据检索方法、Word 输出规范；新增 `TOPIC_AGENT_PROMPT`、`LITERATURE_AGENT_PROMPT`、`EMPIRICAL_AGENT_PROMPT`、`WRITING_AGENT_PROMPT` |
| `src/agent/main.py` | `create_mining_agent` → `create_econ_agent`；工具列表删 `calculate_irr` 加 `read_image`；新增 4 个 subagents 配置（topic/literature/empirical/writing） |
| `src/api/app.py` | import 和调用处 `create_mining_agent` → `create_econ_agent` |
| `src/api/routes.py` | import 和引用处 `MINING_SYSTEM_PROMPT` → `ECON_SYSTEM_PROMPT` |
| `run.py` | import 和调用处 `create_mining_agent` → `create_econ_agent` |
| `.claude/CLAUDE.md` | 项目名和描述从矿业改为经济学论文 |

### 未动的文件

- `src/api/stream.py` — SSE 流式输出，完全复用
- `src/tools/calculate.py` — IRR 计算工具代码保留，只是不再注册到 agent 工具列表
- `src/tools/code_runner.py` — 代码执行工具，完全复用
- `src/tools/pdf_reader.py` — PDF 读取，完全复用
- `src/tools/path_resolver.py` — 路径解析，完全复用
- `frontend/` — 前端，完全不动
- `data/` — 数据目录，结构不变

### 验证结果

- `src.tools.read_image` import 通过
- `src.agent.prompts` 5 个 prompt 变量 import 通过
- `src.agent.main.create_econ_agent` import 通过
- `src.api.app` import 通过
- `search_openalex.py` 实测搜索 "digital economy employment" 返回真实文献（含 DOI）
- `search_semantic.py` 实测搜索正常（Semantic Scholar 有频率限制，脚本已优雅处理 429）
- 全局 grep `create_mining_agent` / `MINING_SYSTEM_PROMPT` 在 src/ 和 run.py 中无残留（docs/ 中的旧文档引用未改，不影响运行）

## 2026-03-06：Sub-agent Prompt 全面升级 + 主 Prompt 路径修正

### 背景

新增了 literature-search（v2 三引擎）、stata、word 三个 skill，但 sub-agent prompt 还停留在旧版，没有写入具体的 skill 调用方法。sub-agent 拿到 prompt 后不知道怎么调用这些工具。本次把所有 skill 的 API 细节精准写入对应 sub-agent 的 system_prompt。

### 修改文件

| 文件 | 改动内容 |
|------|---------|
| `src/agent/prompts.py` | 见下方详细说明 |

### ECON_SYSTEM_PROMPT 改动（主 prompt）

- 文献路径修正：`/skills/literature/` → `/skills/literature-search/`（3处）
- 文献检索方法：从旧的 `search_openalex.py` / `search_semantic.py` 脚本引用改为 `LiteratureSearch` 类 API
- 工作流步骤4：加入 `/skills/stata/` 作为首选实证分析工具
- 工作流步骤5：加入 `/skills/word/` 脚本生成规范 Word 文档
- Word 输出规范：从笼统的 python-docx 描述改为具体的 4 个脚本（create_docx / add_table / add_formula / add_references）
- 格式标准：从"四号宋体"修正为"宋体小四"，页边距从 2.5cm 修正为 2.54cm/3.17cm（与 Word skill 一致）

### TOPIC_AGENT_PROMPT 改动

- 新增文献检索工具段：LiteratureSearch 初始化 + search/trend 用法示例
- 新增数据可得性扫描段：World Bank / 国家统计局调用示例 + 常用指标速查
- 输出格式增加"因果机制（X → Z → Y）"和"是否已验证可获取"

### LITERATURE_AGENT_PROMPT 改动（重写）

- 修复旧版代码块未闭合、方法说明挤在一行的格式问题
- 工具初始化：清晰的 import 代码块
- 核心方法：每个方法独立一段（search / detail / cite_trace / author / verify / trend / google_query）
- 新增标准工作流（6步）和搜索技巧
- 核心规则（红线）独立成段，强调摘要原文输出

### EMPIRICAL_AGENT_PROMPT 改动（重写）

- 新增 Stata 分析段（首选）：inline 命令和 .do 文件两种调用方式的完整代码示例
- 新增常用 Stata 命令速查：OLS / FE / RE / Hausman / IV / DID / RDD / esttab
- Python 分析降为备选
- 工作规范增加：过度识别检验、Stata 无状态提醒

### WRITING_AGENT_PROMPT 改动（重写）

- 新增 Word skill programmatic API 完整示例：create_academic_paper → setup_heading_styles → insert_toc → add_heading_with_style → insert_formula → insert_three_line_table → insert_image → add_reference_list → save
- 新增 CLI 脚本用法速查
- 新增 Stata/Python 结果读取段
- 论文结构增加封面（add_cover_page）和目录（insert_toc）
- 格式标准：完整字体表（标题/正文/表格 5 级）+ 页面设置 + 三线表规格
- 写作原则增加脚注用法（add_footnote）

### 影响范围

- 仅改动 `src/agent/prompts.py` 一个文件
- 不影响 agent 工厂函数、API 路由、前端
- sub-agent 的 tools 列表不变（在 main.py 中配置），本次只改 system_prompt 内容

## 2026-03-06：read_image 改为多模态模型识别 + CURRENT_MODEL 修复

### 背景

`read_image` 工具之前的设计是把图片 base64 塞进 ToolMessage 返回给 agent，但 LangChain 的 ToolMessage 不支持多模态内容，模型收到的只是一大坨 base64 文本，无法"看"图。同时 `CURRENT_MODEL` 环境变量从未被设置，默认值 `"deepseek"` 导致所有模型都被降级。

### 改动

| 文件 | 改动内容 |
|------|---------|
| `src/tools/read_image.py` | 重写：tool 内部调用多模态模型识别图片，返回结构化文字描述；不再返回 base64 |
| `src/api/stream.py` | 在 `_run_agent` 开头设置 `os.environ["CURRENT_MODEL"] = model`；新增 `import os` |
| `run.py` | 终端入口设置 `os.environ["CURRENT_MODEL"] = model_name` |

### read_image 新逻辑

1. 读图片 → base64 data URL
2. 检查 `CURRENT_MODEL`：DeepSeek → 降级返回文件元信息
3. 其他模型 → 调用 `get_llm(CURRENT_MODEL)` 创建模型实例，发送带图片的 HumanMessage
4. 模型返回图表描述（类型、轴含义、趋势、关键数值等）
5. 返回纯文字 `str` 给 agent（不再返回 `str | list`）

### CURRENT_MODEL 设置时机

- API 模式：`stream.py` 的 `_run_agent()` 在每次请求开头设置（model 参数从路由层传入）
- 终端模式：`run.py` 的 `main()` 在启动时设置
- 单用户桌面应用，进程级环境变量足够
