"""
百炼知识库上传测试脚本

验证完整 6 步流程：
1. ApplyFileUploadLease - 申请上传租约
2. PUT 上传文件到 OSS
3. AddFile - 注册文件
4. 轮询 DescribeFile 等待解析完成
5. SubmitIndexAddDocumentsJob - 提交到知识库索引
6. 轮询 GetIndexJobStatus 等待索引完成
7. ListIndexDocuments - 验证文件出现
8. DeleteIndexDocument - 清理测试文件
"""

import hashlib
import os
import sys
import time

import requests as http_requests
from dotenv import load_dotenv

load_dotenv()

from alibabacloud_bailian20231229.client import Client as BailianClient
from alibabacloud_bailian20231229 import models as bailian_models
from alibabacloud_tea_openapi import models as openapi_models
from alibabacloud_tea_util import models as util_models


def create_client() -> BailianClient:
    config = openapi_models.Config(
        access_key_id=os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_ID"),
        access_key_secret=os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_SECRET"),
    )
    config.endpoint = "bailian.cn-beijing.aliyuncs.com"
    return BailianClient(config)


def main():
    workspace_id = os.environ.get("BAILIAN_WORKSPACE_ID")
    index_id = os.environ.get("BAILIAN_INDEX_ID")
    category_id = os.environ.get("BAILIAN_CATEGORY_ID", "default")

    if not workspace_id or not index_id:
        print("ERROR: 缺少 BAILIAN_WORKSPACE_ID 或 BAILIAN_INDEX_ID")
        sys.exit(1)

    client = create_client()
    runtime = util_models.RuntimeOptions()

    # 创建测试文件
    test_content = b"This is a test file for Bailian knowledge base upload.\n\nArcstone test at " + time.strftime("%Y-%m-%d %H:%M:%S").encode()
    test_filename = "arcstone_upload_test.txt"
    file_md5 = hashlib.md5(test_content).hexdigest()

    print(f"=== Step 1: ApplyFileUploadLease ===")
    print(f"  file: {test_filename}, size: {len(test_content)}, md5: {file_md5}")
    lease_req = bailian_models.ApplyFileUploadLeaseRequest(
        file_name=test_filename,
        md_5=file_md5,
        size_in_bytes=str(len(test_content)),
    )
    lease_resp = client.apply_file_upload_lease_with_options(
        category_id, workspace_id, lease_req, {}, runtime
    )
    lease_data = lease_resp.body.data
    lease_id = lease_data.file_upload_lease_id
    upload_url = lease_data.param.url
    upload_headers_raw = lease_data.param.headers
    print(f"  lease_id: {lease_id}")
    print(f"  upload_url: {upload_url[:80]}...")

    # 处理 headers：可能是 Tea model 对象，需转 dict
    if hasattr(upload_headers_raw, "to_map"):
        upload_headers = upload_headers_raw.to_map()
    elif isinstance(upload_headers_raw, dict):
        upload_headers = upload_headers_raw
    else:
        upload_headers = {}
    print(f"  upload_headers: {upload_headers}")

    print(f"\n=== Step 2: PUT upload to OSS ===")
    put_resp = http_requests.put(upload_url, data=test_content, headers=upload_headers)
    put_resp.raise_for_status()
    print(f"  status: {put_resp.status_code}")

    print(f"\n=== Step 3: AddFile ===")
    add_req = bailian_models.AddFileRequest(
        lease_id=lease_id,
        parser="DASHSCOPE_DOCMIND",
        category_id=category_id,
    )
    add_resp = client.add_file_with_options(workspace_id, add_req, {}, runtime)
    file_id = add_resp.body.data.file_id
    print(f"  file_id: {file_id}")

    print(f"\n=== Step 4: Poll DescribeFile (wait for PARSE_SUCCESS) ===")
    for i in range(60):  # 最多等 5 分钟
        desc_resp = client.describe_file_with_options(workspace_id, file_id, {}, runtime)
        status = desc_resp.body.data.status
        print(f"  [{i+1}] status: {status}")
        if status == "PARSE_SUCCESS":
            break
        if status == "PARSE_FAILED":
            print("  ERROR: 文件解析失败")
            sys.exit(1)
        time.sleep(5)
    else:
        print("  ERROR: 文件解析超时")
        sys.exit(1)

    print(f"\n=== Step 5: SubmitIndexAddDocumentsJob ===")
    submit_req = bailian_models.SubmitIndexAddDocumentsJobRequest(
        index_id=index_id,
        source_type="DATA_CENTER_FILE",
        document_ids=[file_id],
    )
    submit_resp = client.submit_index_add_documents_job_with_options(
        workspace_id, submit_req, {}, runtime
    )
    job_id = submit_resp.body.data.id
    print(f"  job_id: {job_id}")

    print(f"\n=== Step 6: Poll GetIndexJobStatus (wait for COMPLETED) ===")
    for i in range(120):  # 最多等 10 分钟
        job_req = bailian_models.GetIndexJobStatusRequest(
            index_id=index_id,
            job_id=job_id,
        )
        job_resp = client.get_index_job_status_with_options(
            workspace_id, job_req, {}, runtime
        )
        job_status = job_resp.body.data.status
        print(f"  [{i+1}] status: {job_status}")
        if job_status == "COMPLETED":
            break
        if job_status == "FAILED":
            print("  ERROR: 索引任务失败")
            # 打印文档级别错误
            if job_resp.body.data.documents:
                for doc in job_resp.body.data.documents:
                    print(f"    doc {doc.doc_name}: {doc.status} - {doc.message}")
            sys.exit(1)
        time.sleep(5)
    else:
        print("  ERROR: 索引任务超时")
        sys.exit(1)

    print(f"\n=== Step 7: ListIndexDocuments (verify) ===")
    list_req = bailian_models.ListIndexDocumentsRequest(
        index_id=index_id,
        page_number=1,
        page_size=20,
    )
    list_resp = client.list_index_documents_with_options(
        workspace_id, list_req, {}, runtime
    )
    doc_id = None
    for doc in list_resp.body.data.documents:
        print(f"  doc: {doc.name} (id={doc.id}, status={doc.status})")
        if doc.name == test_filename:
            doc_id = doc.id
            print(f"  >>> Found test file! doc_id={doc_id}")

    if not doc_id:
        print("  WARNING: 测试文件未在列表中找到（可能延迟，跳过删除）")
        return

    print(f"\n=== Step 8: DeleteIndexDocument (cleanup) ===")
    del_req = bailian_models.DeleteIndexDocumentRequest(
        index_id=index_id,
        document_ids=[doc_id],
    )
    del_resp = client.delete_index_document_with_options(
        workspace_id, del_req, {}, runtime
    )
    print(f"  deleted: {del_resp.body.data.deleted_document}")

    print(f"\n=== ALL STEPS PASSED ===")


if __name__ == "__main__":
    main()
