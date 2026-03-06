"""
测试百炼知识库 Retrieve API
"""
import os
from alibabacloud_bailian20231229.client import Client as bailian20231229Client
from alibabacloud_bailian20231229 import models as bailian_20231229_models
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_tea_util import models as util_models


def create_client() -> bailian20231229Client:
    """创建百炼客户端"""
    config = open_api_models.Config(
        access_key_id=os.environ.get('ALIBABA_CLOUD_ACCESS_KEY_ID'),
        access_key_secret=os.environ.get('ALIBABA_CLOUD_ACCESS_KEY_SECRET')
    )
    config.endpoint = 'bailian.cn-beijing.aliyuncs.com'
    return bailian20231229Client(config)


def retrieve(client, workspace_id: str, index_id: str, query: str):
    """
    检索知识库

    Args:
        client: 百炼客户端
        workspace_id: 业务空间ID
        index_id: 知识库ID
        query: 查询文本

    Returns:
        检索到的文本切片列表
    """
    request = bailian_20231229_models.RetrieveRequest(
        index_id=index_id,
        query=query
    )
    runtime = util_models.RuntimeOptions()
    response = client.retrieve_with_options(workspace_id, request, {}, runtime)
    return response.body


def main():
    WORKSPACE_ID = 'llm-fo524vmjsvgfy4fo'
    INDEX_ID = '33vwcp3n7u'

    # 测试查询
    test_query = "铜的看法"

    print(f"Workspace ID: {WORKSPACE_ID}")
    print(f"Index ID: {INDEX_ID}")
    print(f"Query: {test_query}")
    print("-" * 50)

    try:
        client = create_client()
        result = retrieve(client, WORKSPACE_ID, INDEX_ID, test_query)

        print("检索结果:")
        if hasattr(result, 'data') and result.data and hasattr(result.data, 'nodes') and result.data.nodes:
            for i, node in enumerate(result.data.nodes, 1):
                print(f"\n--- 切片 {i} ---")
                print(f"Score: {node.metadata.get('_score', 'N/A')}")
                print(f"Doc ID: {node.metadata.get('doc_id', 'N/A')}")
                content = node.metadata.get('content', '')
                print(f"Text: {content[:300]}..." if len(content) > 300 else f"Text: {content}")
        else:
            print("未检索到相关内容")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
