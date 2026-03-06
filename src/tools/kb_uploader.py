"""
百炼知识库管理 - 文件上传/删除/列表

封装百炼 API 的完整上传流程：
申请租约 → PUT 上传 → AddFile → 轮询解析 → 提交索引 → 轮询索引
"""

import hashlib
import os
import time
import logging

import requests as http_requests
from alibabacloud_bailian20231229.client import Client as BailianClient
from alibabacloud_bailian20231229 import models as bailian_models
from alibabacloud_tea_openapi import models as openapi_models
from alibabacloud_tea_util import models as util_models

logger = logging.getLogger(__name__)


def _create_bailian_client() -> BailianClient:
    config = openapi_models.Config(
        access_key_id=os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_ID"),
        access_key_secret=os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_SECRET"),
    )
    config.endpoint = "bailian.cn-beijing.aliyuncs.com"
    return BailianClient(config)


class BailianKBManager:
    def __init__(self):
        self.client = _create_bailian_client()
        self.workspace_id = os.environ.get("BAILIAN_WORKSPACE_ID")
        self.default_index_id = os.environ.get("BAILIAN_INDEX_ID")
        self._category_id = os.environ.get("BAILIAN_CATEGORY_ID", "default")
        self._runtime = util_models.RuntimeOptions()

    def _resolve_index(self, index_id: str | None) -> str:
        return index_id or self.default_index_id

    def upload_file(self, file_bytes: bytes, filename: str) -> dict:
        """申请租约 → PUT 上传 → AddFile，返回 {file_id, filename}"""
        file_md5 = hashlib.md5(file_bytes).hexdigest()

        lease_req = bailian_models.ApplyFileUploadLeaseRequest(
            file_name=filename,
            md_5=file_md5,
            size_in_bytes=str(len(file_bytes)),
        )
        lease_resp = self.client.apply_file_upload_lease_with_options(
            self._category_id, self.workspace_id, lease_req, {}, self._runtime
        )
        lease_data = lease_resp.body.data
        lease_id = lease_data.file_upload_lease_id
        upload_url = lease_data.param.url

        raw_headers = lease_data.param.headers
        if hasattr(raw_headers, "to_map"):
            upload_headers = raw_headers.to_map()
        elif isinstance(raw_headers, dict):
            upload_headers = raw_headers
        else:
            upload_headers = {}

        put_resp = http_requests.put(upload_url, data=file_bytes, headers=upload_headers)
        put_resp.raise_for_status()

        add_req = bailian_models.AddFileRequest(
            lease_id=lease_id,
            parser="DASHSCOPE_DOCMIND",
            category_id=self._category_id,
        )
        add_resp = self.client.add_file_with_options(
            self.workspace_id, add_req, {}, self._runtime
        )
        file_id = add_resp.body.data.file_id
        logger.info("Uploaded file %s, file_id=%s", filename, file_id)
        return {"file_id": file_id, "filename": filename}

    def poll_file_parse(self, file_id: str, timeout: int = 300) -> str:
        """轮询 describe_file 直到 PARSE_SUCCESS / PARSE_FAILED"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            resp = self.client.describe_file_with_options(
                self.workspace_id, file_id, {}, self._runtime
            )
            status = resp.body.data.status
            if status in ("PARSE_SUCCESS", "PARSE_FAILED"):
                return status
            time.sleep(5)
        return "TIMEOUT"

    def submit_to_index(
        self,
        file_ids: list[str],
        index_id: str | None = None,
        chunk_size: int | None = None,
        overlap_size: int | None = None,
    ) -> str:
        """SubmitIndexAddDocumentsJob，返回 job_id"""
        kwargs: dict = {
            "index_id": self._resolve_index(index_id),
            "source_type": "DATA_CENTER_FILE",
            "document_ids": file_ids,
        }
        if chunk_size is not None:
            kwargs["chunk_size"] = chunk_size
        if overlap_size is not None:
            kwargs["overlap_size"] = overlap_size

        req = bailian_models.SubmitIndexAddDocumentsJobRequest(**kwargs)
        resp = self.client.submit_index_add_documents_job_with_options(
            self.workspace_id, req, {}, self._runtime
        )
        job_id = resp.body.data.id
        logger.info("Submitted index job %s for files %s", job_id, file_ids)
        return job_id

    def poll_index_job(self, job_id: str, index_id: str | None = None, timeout: int = 600) -> dict:
        """轮询 GetIndexJobStatus"""
        idx = self._resolve_index(index_id)
        deadline = time.time() + timeout
        while time.time() < deadline:
            req = bailian_models.GetIndexJobStatusRequest(
                index_id=idx,
                job_id=job_id,
            )
            resp = self.client.get_index_job_status_with_options(
                self.workspace_id, req, {}, self._runtime
            )
            data = resp.body.data
            status = data.status
            if status in ("COMPLETED", "FAILED"):
                documents = []
                if data.documents:
                    for doc in data.documents:
                        documents.append({
                            "doc_id": doc.doc_id,
                            "doc_name": doc.doc_name,
                            "status": doc.status,
                            "message": doc.message,
                        })
                return {"status": status, "documents": documents}
            time.sleep(5)
        return {"status": "TIMEOUT", "documents": []}

    def list_documents(self, index_id: str | None = None, page: int = 1, page_size: int = 20) -> dict:
        """ListIndexDocuments"""
        req = bailian_models.ListIndexDocumentsRequest(
            index_id=self._resolve_index(index_id),
            page_number=page,
            page_size=page_size,
        )
        resp = self.client.list_index_documents_with_options(
            self.workspace_id, req, {}, self._runtime
        )
        data = resp.body.data
        documents = []
        if data.documents:
            for doc in data.documents:
                documents.append({
                    "id": doc.id,
                    "name": doc.name,
                    "size": doc.size or 0,
                    "status": doc.status or "",
                    "modified_at": doc.gmt_modified or 0,
                })
        return {
            "documents": documents,
            "total_count": data.total_count or 0,
        }

    def delete_documents(self, document_ids: list[str], index_id: str | None = None) -> bool:
        """DeleteIndexDocument"""
        req = bailian_models.DeleteIndexDocumentRequest(
            index_id=self._resolve_index(index_id),
            document_ids=document_ids,
        )
        self.client.delete_index_document_with_options(
            self.workspace_id, req, {}, self._runtime
        )
        logger.info("Deleted documents: %s", document_ids)
        return True

    def retrieve(self, query: str, index_id: str | None = None) -> str:
        """从指定知识库检索，返回格式化文本"""
        idx = self._resolve_index(index_id)
        req = bailian_models.RetrieveRequest(
            index_id=idx,
            query=query,
        )
        response = self.client.retrieve_with_options(
            self.workspace_id, req, {}, self._runtime
        )
        if (
            hasattr(response, "body")
            and response.body
            and hasattr(response.body, "data")
            and response.body.data
            and hasattr(response.body.data, "nodes")
            and response.body.data.nodes
        ):
            results = []
            for i, node in enumerate(response.body.data.nodes, 1):
                content = node.metadata.get("content", "")
                score = node.metadata.get("_score", "N/A")
                if content:
                    results.append(f"[片段{i}] (相关度:{score})\n{content}")
            if results:
                return "\n\n".join(results)
        return ""
