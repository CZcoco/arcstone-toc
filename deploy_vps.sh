#!/bin/bash
set -e
echo "====== VPS 部署脚本 ======"

# --- 1. Caddy ---
echo "[1/6] 设置 Caddy 权限..."
chmod +x /usr/local/bin/caddy
caddy version

# --- 2. 配置文件 ---
echo "[2/6] 创建配置文件..."
mkdir -p /srv/config

cat > /srv/config/keys.json << 'KEYSEOF'
{
  "tavily": [
    "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",
    "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"
  ],
  "mineru": [
    "eyJ0eXBlIjoiSldUIiwiYWxnIjoiSFM1MTIifQ.eyJqdGkiOiI4ODYwMDA5MSIsInJvbCI6IlJPTEVfUkVHSVNURVIiLCJpc3MiOiJPcGVuWExhYiIsImlhdCI6MTc3MTQwNjc0NSwiY2xpZW50SWQiOiJsa3pkeDU3bnZ5MjJqa3BxOXgydyIsInBob25lIjoiMTM3NjM4NzI4NjYiLCJvcGVuSWQiOm51bGwsInV1aWQiOiJiZDViNzY1YS04NGY4LTQyZTgtYWYzOS0yMjdjYzMyN2ZjZDEiLCJlbWFpbCI6IiIsImV4cCI6MTc3OTE4Mjc0NX0.6-b5-p0NtguySBv_mKwJ0j26fJUJmW8XBqiMqAzJfIETFk3I6Rhifm4C2UaQI4wHSmuw5yCH0ohPr4FO5ZKtCw"
  ]
}
KEYSEOF

cat > /srv/config/modes.json << 'MODESEOF'
{"modes":[{"id":"default","name":"通用助手","description":"智能对话，帮你完成各种任务","icon":"bot"},{"id":"thesis","name":"论文辅导","description":"毕业论文全流程：选题、文献、数据、写作","icon":"graduation-cap","system_prompt":"你是一个经济学论文写作AI助手，专门帮助本科生完成毕业论文全流程。\n\n核心能力：\n1. 选题推荐：根据学生兴趣和数据可得性，推荐可行的论文题目\n2. 文献检索：通过 literature-search 技能搜索 OpenAlex/Semantic Scholar 的真实文献，绝不编造\n3. 数据获取：使用 data 技能从世界银行、国家统计局、FRED 等获取数据\n4. 实证分析：用 Stata/Python 运行计量回归（OLS、面板FE、IV/2SLS、DID、RDD）\n5. 论文生成：用 word 技能按学术规范生成 Word 文档（三线表、GB/T 7714 参考文献）\n\n红线规则：\n- 参考文献零幻觉：只引用通过搜索验证的真实文献\n- 数据零编造：所有回归结果必须来自实际代码执行\n- 不确定就问：缺少关键信息时主动向用户提问\n\n工作方法：\n- 多步任务先列计划再执行\n- 善于组合使用工具，主动搜索验证\n- 每完成一步简要说明发现，最后给出整体结论"},{"id":"homework","name":"写作业","description":"解题思路讲解与作业辅导","icon":"pencil-line","system_prompt":"你是一个耐心的作业辅导助手，帮助经济学本科生理解和完成课程作业。\n\n辅导原则：\n1. 先理解题意：仔细分析题目要求，拆解为可执行的步骤\n2. 启发式引导：不直接给答案，先引导学生思考，给出解题思路\n3. 分步讲解：复杂问题分步骤解释，每步确认学生理解\n4. 代码辅助：需要计算时用 Python 演示，附带详细注释\n5. 举一反三：解完题后总结方法，提供类似练习建议\n\n擅长领域：\n- 微观经济学（供需分析、消费者/生产者理论、博弈论）\n- 宏观经济学（IS-LM、AD-AS、索洛模型、经济增长）\n- 计量经济学（回归分析、假设检验、面板数据）\n- 数理经济学（最优化、拉格朗日乘数法）\n- 统计学（概率分布、置信区间、方差分析）\n\n注意：鼓励学生独立思考，不要替代学习过程。"},{"id":"ppt","name":"做 PPT","description":"生成演示文稿大纲和内容","icon":"presentation","system_prompt":"你是一个专业的演示文稿制作助手，帮助学生制作课堂汇报和答辩 PPT。\n\n工作流程：\n1. 了解需求：确认主题、时长、受众、场合（课堂展示/毕业答辩/学术会议）\n2. 设计大纲：根据时长规划页数和每页要点（一般每页1-2分钟）\n3. 撰写内容：每页标题 + 3-5个要点，语言精炼\n4. 生成文件：用 Python 的 python-pptx 库生成 .pptx 文件\n\n设计原则：\n- 一页一个核心观点，不堆砌文字\n- 标题用结论性语句\n- 数据用图表呈现，避免大段文字\n- 答辩 PPT 结构：研究背景-文献综述-研究设计-实证结果-结论建议\n- 配色简洁专业\n\n输出格式：\n- 先展示文字大纲让用户确认\n- 确认后用 python-pptx 生成文件保存到 /workspace/"}]}
MODESEOF

echo "  keys.json 和 modes.json 已创建"

# --- 3. RAG 代理 ---
echo "[3/6] 构建 RAG 代理..."
mkdir -p /home/ubuntu/rag-proxy

cat > /home/ubuntu/rag-proxy/requirements.txt << 'EOF'
fastapi==0.115.0
uvicorn==0.30.6
alibabacloud_bailian20231229>=1.2.0
alibabacloud_tea_openapi>=0.3.0
alibabacloud_tea_util>=0.3.0
EOF

cat > /home/ubuntu/rag-proxy/Dockerfile << 'EOF'
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/
COPY app.py .
EXPOSE 8100
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8100"]
EOF

cat > /home/ubuntu/rag-proxy/app.py << 'PYEOF'
import os, logging
from fastapi import FastAPI
from pydantic import BaseModel
from alibabacloud_bailian20231229.client import Client as BailianClient
from alibabacloud_bailian20231229 import models as bailian_models
from alibabacloud_tea_openapi import models as openapi_models
from alibabacloud_tea_util import models as util_models

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
app = FastAPI()

WORKSPACE_ID = os.environ.get("BAILIAN_WORKSPACE_ID", "")
INDEX_ID = os.environ.get("BAILIAN_INDEX_ID", "")
_client = None
_runtime = util_models.RuntimeOptions(read_timeout=15000, connect_timeout=5000)

def _get_client():
    global _client
    if _client is None:
        cfg = openapi_models.Config(
            access_key_id=os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_ID"),
            access_key_secret=os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_SECRET"),
        )
        cfg.endpoint = "bailian.cn-beijing.aliyuncs.com"
        _client = BailianClient(cfg)
    return _client

class RetrieveRequest(BaseModel):
    query: str
    index_id: str | None = None

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/rag/retrieve")
def retrieve(req: RetrieveRequest):
    idx = req.index_id or INDEX_ID
    if not idx:
        return {"results": [], "error": "no INDEX_ID"}
    try:
        r = _get_client().retrieve_with_options(
            WORKSPACE_ID,
            bailian_models.RetrieveRequest(index_id=idx, query=req.query),
            {}, _runtime,
        )
        results = []
        if r.body and r.body.data and r.body.data.nodes:
            for n in r.body.data.nodes:
                text = n.metadata.get("content", "") if n.metadata else ""
                score = n.metadata.get("_score", 0) if n.metadata else 0
                if text:
                    results.append({"text": text, "score": score})
        return {"results": results}
    except Exception as e:
        logger.exception("retrieve failed")
        return {"results": [], "error": str(e)}
PYEOF

cd /home/ubuntu/rag-proxy
docker build -t rag-proxy .
docker rm -f rag-proxy 2>/dev/null || true
docker run -d --name rag-proxy --restart always \
  -p 127.0.0.1:8100:8100 \
  -e BAILIAN_WORKSPACE_ID=${BAILIAN_WORKSPACE_ID:?请设置环境变量} \
  -e BAILIAN_INDEX_ID=${BAILIAN_INDEX_ID:?请设置环境变量} \
  -e ALIBABA_CLOUD_ACCESS_KEY_ID=${ALIBABA_CLOUD_ACCESS_KEY_ID:?请设置环境变量} \
  -e ALIBABA_CLOUD_ACCESS_KEY_SECRET=${ALIBABA_CLOUD_ACCESS_KEY_SECRET:?请设置环境变量} \
  rag-proxy
echo "  RAG 代理已启动"

# --- 4. 重建 New API (localhost:3001) ---
echo "[4/6] 重建 New API Docker..."
docker stop new-api && docker rm new-api
docker run -d --name new-api --restart always \
  -p 127.0.0.1:3001:3000 \
  -v /home/ubuntu/data/new-api:/data \
  -e TZ=Asia/Shanghai \
  calciumion/new-api:latest
echo "  New API 已在 localhost:3001 重启"

# --- 5. Caddy ---
echo "[5/6] 配置 Caddy..."
mkdir -p /etc/caddy
cat > /etc/caddy/Caddyfile << 'EOF'
:3000, :80 {
    handle /config/* {
        root * /srv
        file_server
    }
    handle /rag/* {
        reverse_proxy 127.0.0.1:8100
    }
    handle {
        reverse_proxy 127.0.0.1:3001
    }
}
EOF

# 停掉可能存在的旧 caddy 进程
caddy stop 2>/dev/null || true
sleep 1
caddy start --config /etc/caddy/Caddyfile
echo "  Caddy 已启动在 :3000 和 :80"

# --- 6. 验证 ---
echo "[6/6] 验证服务..."
sleep 2
echo "--- keys.json ---"
curl -s http://127.0.0.1:3000/config/keys.json | head -c 120
echo ""
echo "--- modes.json ---"
curl -s http://127.0.0.1:3000/config/modes.json | head -c 120
echo ""
echo "--- New API models ---"
curl -s http://127.0.0.1:3000/v1/models | head -c 120
echo ""
echo "--- RAG health ---"
curl -s http://127.0.0.1:3000/rag/health
echo ""
echo "--- RAG retrieve ---"
curl -s -X POST http://127.0.0.1:3000/rag/retrieve -H "Content-Type: application/json" -d '{"query":"经济增长"}'
echo ""
echo ""
echo "====== 部署完成 ======"
