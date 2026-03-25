"""
百炼知识库 RAG 代理 — 部署在 VPS 上，客户端通过 HTTP 调用。
"""
import os
import logging

from fastapi import FastAPI
from pydantic import BaseModel

from alibabacloud_bailian20231229.client import Client as BailianClient
from alibabacloud_bailian20231229 import models as bailian_models
from alibabacloud_tea_openapi import models as openapi_models
from alibabacloud_tea_util import models as util_models

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="RAG Proxy")

# --- 百炼客户端 ---

WORKSPACE_ID = os.environ.get("BAILIAN_WORKSPACE_ID", "")
INDEX_ID = os.environ.get("BAILIAN_INDEX_ID", "")

_client = None
_runtime = util_models.RuntimeOptions(read_timeout=15000, connect_timeout=5000)


def _get_client() -> BailianClient:
    global _client
    if _client is None:
        config = openapi_models.Config(
            access_key_id=os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_ID"),
            access_key_secret=os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_SECRET"),
        )
        config.endpoint = "bailian.cn-beijing.aliyuncs.com"
        _client = BailianClient(config)
    return _client


# --- 请求/响应模型 ---

class RetrieveRequest(BaseModel):
    query: str
    index_id: str | None = None


# --- 路由 ---

@app.get("/health")
def health():
    return {"ok": True}


@app.post("/rag/retrieve")
def retrieve(req: RetrieveRequest):
    idx = req.index_id or INDEX_ID
    if not idx:
        return {"results": [], "error": "未配置 BAILIAN_INDEX_ID"}

    try:
        client = _get_client()
        bailian_req = bailian_models.RetrieveRequest(
            index_id=idx,
            query=req.query,
        )
        response = client.retrieve_with_options(
            WORKSPACE_ID, bailian_req, {}, _runtime
        )

        results = []
        if (
            hasattr(response, "body")
            and response.body
            and hasattr(response.body, "data")
            and response.body.data
            and hasattr(response.body.data, "nodes")
            and response.body.data.nodes
        ):
            for node in response.body.data.nodes:
                text = node.metadata.get("content", "") if node.metadata else ""
                score = node.metadata.get("_score", 0) if node.metadata else 0
                if text:
                    results.append({"text": text, "score": score})

        return {"results": results}

    except Exception as e:
        logger.exception("Retrieve failed")
        return {"results": [], "error": str(e)}
