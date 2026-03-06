阿里云百炼知识库提供开放的API接口，便于您快速接入现有业务系统，实现自动化操作，并应对复杂的检索需求。

重要
本文档仅适用于文档搜索类知识库。

前置步骤
子账号（主账号不需要）需获取API权限（AliyunBailianDataFullAccess策略），并加入一个业务空间，然后才能通过阿里云API操作知识库。

子账号只能操作已加入业务空间中的知识库；主账号可操作所有业务空间下的知识库。
安装最新版阿里云百炼SDK，以调用知识库相关的阿里云API。如何安装请参考阿里云SDK开发参考目录下文档。

如果SDK不能满足需求，可以通过签名机制（较为复杂）HTTP请求知识库的相关接口。具体对接方式请参见API概览。
获取AccessKey和AccessKey Secret以及业务空间 ID，并将它们配置到系统环境变量，以运行示例代码。以Linux操作系统为例：

如果您使用了 IDE 或其他辅助开发插件，需自行将ALIBABA_CLOUD_ACCESS_KEY_ID、ALIBABA_CLOUD_ACCESS_KEY_SECRET和WORKSPACE_ID变量配置到相应的开发环境中。
 
export ALIBABA_CLOUD_ACCESS_KEY_ID='您的阿里云访问密钥ID'
export ALIBABA_CLOUD_ACCESS_KEY_SECRET='您的阿里云访问密钥密码'
export WORKSPACE_ID='您的阿里云百炼业务空间ID'
准备好示例知识文档阿里云百炼系列手机产品介绍.docx，用于创建知识库。

完整示例代码
创建知识库
接下来通过示例，引导您在给定的业务空间下创建一个文档搜索类知识库。

1. 初始化客户端
在开始上传文件和创建知识库之前，您需要使用配置好的AccessKey和AccessKey Secret初始化客户端（Client），以完成身份验证和接入点endpoint配置。

公网接入地址：

请确保您的客户端可以访问公网。
公有云：bailian.cn-beijing.aliyuncs.com

金融云：bailian.cn-shanghai-finance-1.aliyuncs.com

VPC接入地址：

若您的客户端部署在阿里云北京地域cn-beijing（公有云）或上海地域cn-shanghai-finance-1（金融云），且处于VPC网络环境中，可以使用以下VPC接入地址（不支持跨地域访问）。
公有云：bailian-vpc.cn-beijing.aliyuncs.com

金融云：bailian-vpc.cn-shanghai-finance-1.aliyuncs.com

创建完成后，您将得到一个Client对象，用于后续的 API 调用。

PythonJavaPHPNode.jsC#Go
 
def create_client() -> bailian20231229Client:
    """
    创建并配置客户端（Client）。

    返回:
        bailian20231229Client: 配置好的客户端（Client）。
    """
    config = open_api_models.Config(
        access_key_id=os.environ.get('ALIBABA_CLOUD_ACCESS_KEY_ID'),
        access_key_secret=os.environ.get('ALIBABA_CLOUD_ACCESS_KEY_SECRET')
    )
    # 下方接入地址以公有云的公网接入地址为例，可按需更换接入地址。
    config.endpoint = 'bailian.cn-beijing.aliyuncs.com'
    return bailian20231229Client(config)
2. 上传知识库文件
2.1. 申请文件上传租约
在创建知识库前，您需先将文件上传至同一业务空间，作为知识库的知识来源。上传文件前，需调用ApplyFileUploadLease接口申请一个文件上传租约。该租约是一个临时的授权，允许您在限定时间内（有效期为分钟级）上传文件。

workspace_id：如何获取业务空间ID

category_id：本示例中，请传入default。阿里云百炼使用类目管理您上传的文件，系统会自动创建一个默认类目。您亦可调用AddCategory接口创建新类目，并获取对应的category_id。

file_name：请传入上传文件的名称（包括后缀）。其值必须与实际文件名一致。例如，上传图中的文件时，请传入阿里云百炼系列手机产品介绍.docx。

image

file_md5：请传入上传文件的MD5值（但当前阿里云不对该值进行校验，便于您使用URL地址上传文件）。

以Python为例，MD5值可使用hashlib模块获取。其他语言请参见完整示例代码。
代码示例

file_size：请传入上传文件的字节大小。

以Python为例，该值可使用os模块获取。其他语言请参见完整示例代码。
代码示例

申请临时上传租约成功后，您将获得：

一组临时上传参数：

Data.FileUploadLeaseId

Data.Param.Method

Data.Param.Headers中的X-bailian-extra

Data.Param.Headers中的Content-Type

一个临时上传URL：Data.Param.Url

您将在下一步中用到它们。

重要
子账号调用本示例前需获取API权限（AliyunBailianDataFullAccess策略）。

本示例支持在线调试及多语言代码示例生成。

PythonJavaPHPNode.jsC#Go
 
def apply_lease(client, category_id, file_name, file_md5, file_size, workspace_id):
    """
    从阿里云百炼服务申请文件上传租约。

    参数:
        client (bailian20231229Client): 客户端（Client）。
        category_id (str): 类目ID。
        file_name (str): 文件名称。
        file_md5 (str): 文件的MD5值。
        file_size (int): 文件大小（以字节为单位）。
        workspace_id (str): 业务空间ID。

    返回:
        阿里云百炼服务的响应。
    """
    headers = {}
    request = bailian_20231229_models.ApplyFileUploadLeaseRequest(
        file_name=file_name,
        md_5=file_md5,
        size_in_bytes=file_size,
    )
    runtime = util_models.RuntimeOptions()
    return client.apply_file_upload_lease_with_options(category_id, workspace_id, request, headers, runtime)
请求示例

响应示例

2.2. 上传文件到临时存储
取得上传租约后，您即可使用租约中的临时上传参数和临时上传URL，将本地存储或可通过公网访问的文件上传至阿里云百炼服务器。请注意，每个业务空间最多支持10万个文件。目前支持上传的格式包括：PDF、DOCX、DOC、TXT、Markdown、PPTX、PPT、XLSX、XLS、HTML、PNG、JPG、JPEG、BMP 和 GIF。

pre_signed_url：请传入申请文件上传租约时接口返回的Data.Param.Url。

该 URL 为预签名 URL，不支持 FormData 方式上传，需使用二进制方式上传（详见示例代码）。
重要
本示例不支持在线调试和多语言示例代码生成。

本地上传URL地址上传
PythonJavaPHPNode.jsC#Go
 
import requests
from urllib.parse import urlparse

def upload_file(pre_signed_url, file_path):
    """
    将本地文件上传至临时存储。

    参数:
        pre_signed_url (str): 上传租约中的URL。
        file_path (str): 文件本地路径。
    
    返回:
        阿里云百炼服务的响应。
    """
    try:
        # 设置请求头
        headers = {
            "X-bailian-extra": "请替换为您在上一步中调用ApplyFileUploadLease接口实际返回的Data.Param.Headers中X-bailian-extra字段的值",
            "Content-Type": "请替换为您在上一步中调用ApplyFileUploadLease接口实际返回的Data.Param.Headers中Content-Type字段的值（返回空值时，传空值即可）"
        }

        # 读取文件并上传
        with open(file_path, 'rb') as file:
            # 下方设置请求方法用于文件上传，需与您在上一步中调用ApplyFileUploadLease接口实际返回的Data.Param中Method字段的值一致
            response = requests.put(pre_signed_url, data=file, headers=headers)

        # 检查响应状态码
        if response.status_code == 200:
            print("File uploaded successfully.")
        else:
            print(f"Failed to upload the file. ResponseCode: {response.status_code}")

    except Exception as e:
        print(f"An error occurred: {str(e)}")

if __name__ == "__main__":

    pre_signed_url_or_http_url = "请替换为您在上一步中调用ApplyFileUploadLease接口实际返回的Data.Param中Url字段的值"

    # 将本地文件上传至临时存储
    file_path = "请替换为您需要上传文件的实际本地路径（以Linux为例：/xxx/xxx/阿里云百炼系列手机产品介绍.docx）"
    upload_file(pre_signed_url_or_http_url, file_path)
2.3. 添加文件到类目中
阿里云百炼使用类目管理您上传的文件。因此，接下来您需要调用AddFile接口将已上传的文件添加到同一业务空间下的类目中。

parser：请传入DASHSCOPE_DOCMIND。

lease_id：请传入申请文件上传租约时接口返回的Data.FileUploadLeaseId。

category_id：本示例中，请传入default。若您使用了自建类目上传，则需传入对应的category_id。

完成添加后，阿里云百炼将返回该文件的FileId，并自动开始解析您的文件。同时lease_id（租约ID）随即失效，请勿再使用相同的租约ID重复提交。

重要
子账号调用本示例前需获取API权限（AliyunBailianDataFullAccess策略）。

本示例支持在线调试及多语言代码示例生成。

PythonJavaPHPNode.jsC#Go
 
def add_file(client: bailian20231229Client, lease_id: str, parser: str, category_id: str, workspace_id: str):
    """
    将文件添加到阿里云百炼服务的指定类目中。

    参数:
        client (bailian20231229Client): 客户端（Client）。
        lease_id (str): 租约ID。
        parser (str): 用于文件的解析器。
        category_id (str): 类目ID。
        workspace_id (str): 业务空间ID。

    返回:
        阿里云百炼服务的响应。
    """
    headers = {}
    request = bailian_20231229_models.AddFileRequest(
        lease_id=lease_id,
        parser=parser,
        category_id=category_id,
    )
    runtime = util_models.RuntimeOptions()
    return client.add_file_with_options(workspace_id, request, headers, runtime)
请求示例

响应示例

2.4. 查询文件的解析状态
未解析完成的文件无法用于知识库，在请求高峰时段，该过程可能需要数小时。您可以调用DescribeFile接口查询文件的解析状态。

file_id：请传入添加文件到类目中时接口返回的FileId。

当本接口返回的Data.Status字段值为PARSE_SUCCESS时，表示文件已解析完成，可以将其导入知识库。

重要
子账号调用本示例前需获取API权限（AliyunBailianDataFullAccess或AliyunBailianDataReadOnlyAccess策略）。

本示例支持在线调试及多语言代码示例生成。

PythonJavaPHPNode.jsC#Go
 
def describe_file(client, workspace_id, file_id):
    """
    获取文件的基本信息。

    参数:
        client (bailian20231229Client): 客户端（Client）。
        workspace_id (str): 业务空间ID。
        file_id (str): 文件ID。

    返回:
        阿里云百炼服务的响应。
    """
    headers = {}
    runtime = util_models.RuntimeOptions()
    return client.describe_file_with_options(workspace_id, file_id, headers, runtime)
请求示例

响应示例

3. 创建知识库
3.1. 初始化知识库
文件解析完成后，您即可将其导入同一业务空间下的知识库。初始化（非最终提交）一个文档搜索类知识库，可以调用CreateIndex接口。

workspace_id：如何获取业务空间ID

file_id：请传入添加文件到类目中时接口返回的FileId。

若source_type为DATA_CENTER_FILE，则该参数为必传，否则接口将报错。
structure_type：本示例中，请传入unstructured。

source_type：本示例中，请传入DATA_CENTER_FILE。

sink_type：本示例中，请传入BUILT_IN。

本接口返回的Data.Id字段值即为知识库ID，用于后续的索引构建。

请您妥善保管知识库ID，后续该知识库所有相关API操作都将用到它。
重要
子账号调用本示例前需获取API权限（AliyunBailianDataFullAccess策略）。

本示例支持在线调试及多语言代码示例生成。

PythonJavaPHPNode.jsC#Go
 
def create_index(client, workspace_id, file_id, name, structure_type, source_type, sink_type):
    """
    在阿里云百炼服务中创建知识库（初始化）。

    参数:
        client (bailian20231229Client): 客户端（Client）。
        workspace_id (str): 业务空间ID。
        file_id (str): 文件ID。
        name (str): 知识库名称。
        structure_type (str): 知识库的数据类型。
        source_type (str): 应用数据的数据类型，支持类目类型和文件类型。
        sink_type (str): 知识库的向量存储类型。

    返回:
        阿里云百炼服务的响应。
    """
    headers = {}
    request = bailian_20231229_models.CreateIndexRequest(
        structure_type=structure_type,
        name=name,
        source_type=source_type,
        sink_type=sink_type,
        document_ids=[file_id]
    )
    runtime = util_models.RuntimeOptions()
    return client.create_index_with_options(workspace_id, request, headers, runtime)
请求示例

响应示例

3.2. 提交索引任务
初始化知识库后，您需要调用SubmitIndexJob接口提交索引任务，以启动知识库的索引构建。

index_id：请传入初始化知识库时接口返回的Data.Id。

完成提交后，阿里云百炼随即以异步任务方式开始构建索引。本接口返回的Data.Id为对应的任务ID。下一步中，您将用到此ID查询任务的最新状态。

重要
子账号调用本示例前需获取API权限（AliyunBailianDataFullAccess策略）。

本示例支持在线调试及多语言代码示例生成。

PythonJavaPHPNode.jsC#Go
 
def submit_index(client, workspace_id, index_id):
    """
    向阿里云百炼服务提交索引任务。

    参数:
        client (bailian20231229Client): 客户端（Client）。
        workspace_id (str): 业务空间ID。
        index_id (str): 知识库ID。

    返回:
        阿里云百炼服务的响应。
    """
    headers = {}
    submit_index_job_request = bailian_20231229_models.SubmitIndexJobRequest(
        index_id=index_id
    )
    runtime = util_models.RuntimeOptions()
    return client.submit_index_job_with_options(workspace_id, submit_index_job_request, headers, runtime)
请求示例

响应示例

3.3. 等待索引任务完成
索引任务的执行需要一定时间，在请求高峰时段，该过程可能需要数小时。查询其执行状态可以调用GetIndexJobStatus接口。

job_id：请传入提交索引任务时接口返回的Data.Id。

当本接口返回的Data.Status字段值为COMPLETED时，表示知识库已创建完成。

重要
子账号调用本示例前需获取API权限（AliyunBailianDataFullAccess策略）。

本示例支持在线调试及多语言代码示例生成。

PythonJavaPHPNode.jsC#Go
 
def get_index_job_status(client, workspace_id, index_id, job_id):
    """
    查询索引任务状态。

    参数:
        client (bailian20231229Client): 客户端（Client）。
        workspace_id (str): 业务空间ID。
        index_id (str): 知识库ID。
        job_id (str): 任务ID。

    返回:
        阿里云百炼服务的响应。
    """
    headers = {}
    get_index_job_status_request = bailian_20231229_models.GetIndexJobStatusRequest(
        index_id=index_id,
        job_id=job_id
    )
    runtime = util_models.RuntimeOptions()
    return client.get_index_job_status_with_options(workspace_id, get_index_job_status_request, headers, runtime)
请求示例

响应示例

通过以上步骤，您已成功创建了一个知识库，并包含了需要上传的文件。

检索知识库
目前，检索知识库支持两种方式：

使用阿里云百炼应用：调用应用时，通过rag_options传入知识库IDindex_id，为您的大模型应用补充私有知识和提供最新信息。

使用阿里云API：调用Retrieve接口在指定的知识库中检索信息并返回原始文本切片。

二者的区别在于：前者先将检索到的相关文本切片传给您配置的大模型，模型再结合这些切片与用户的原始查询生成最终回答并返回；后者则是直接返回文本切片。

接下来为您介绍使用阿里云API的方式。

在指定的知识库中检索信息，并返回文本切片，可以通过调用Retrieve接口。

client：如何获取client

workspace_id：知识库所在的业务空间。如何获取业务空间ID

子账号只能检索自己已加入的业务空间中的知识库。
若本接口返回的结果包含较多干扰信息，您可以在请求时传入SearchFilters设置检索条件（比如设置标签筛选），以排除干扰信息。

重要
子账号调用本示例前需获取API权限（AliyunBailianDataFullAccess策略）。

本示例支持在线调试及多语言代码示例生成。

PythonJavaPHPNode.jsC#Go
 
def retrieve_index(client, workspace_id, index_id, query):
    """
    在指定的知识库中检索信息。
        
    参数:
        client (bailian20231229Client): 客户端（Client）。
        workspace_id (str): 业务空间ID。
        index_id (str): 知识库ID。
        query (str): 原始输入prompt。

    返回:
        阿里云百炼服务的响应。
    """
    headers = {}
    retrieve_request = bailian_20231229_models.RetrieveRequest(
        index_id=index_id,
        query=query
    )
    runtime = util_models.RuntimeOptions()
    return client.retrieve_with_options(workspace_id, retrieve_request, headers, runtime)
请求示例

响应示例

更新知识库
接下来通过示例，引导您更新文档搜索类知识库。所有引用该知识库的应用会实时生效您本次的更新（新增内容可用于检索和召回，而已删除内容将不再可用）。

数据查询、图片问答类知识库不支持通过API更新。如何更新请参见知识库：更新知识库。
如何增量更新知识库：请您按照以下三步（先上传更新后的文件，再追加文件至知识库，最后删除旧文件）操作。此外暂无其他实现方式。

如何全量更新知识库：对知识库中的所有文件，请您逐一执行以下三步完成更新。

如何实现知识库的自动更新/同步：请详见如何实现知识库的自动更新/同步。

单次更新对文件数量是否有限制：建议不超过10万个，否则可能导致知识库无法正常更新。

1. 上传更新后的文件
按照创建知识库：第二步操作，将更新后的文件上传至该知识库所在的业务空间。

您需要重新申请文件上传租约，为更新后的文件生成一组新的上传参数。
2. 追加文件至知识库
2.1. 提交追加文件任务
上传文件解析完成后，请调用SubmitIndexAddDocumentsJob接口将新文件追加至知识库，并重新构建知识库索引。

client：如何获取client

workspace_id：如何获取业务空间ID

file_id：请传入添加文件到类目中时接口返回的FileId。

source_type：在本示例中，请传入DATA_CENTER_FILE。

完成提交后，阿里云百炼将以异步任务方式开始重新构建知识库。本接口返回的Data.Id为对应的任务ID（job_id）。下一步中，您将用到此ID查询任务的最新状态。

重要
SubmitIndexAddDocumentsJob接口调用成功后，将执行一段时间，您可通过job_id查询任务的最新状态。在任务完成前，请勿重复提交。

重要
子账号调用本示例前需获取API权限（AliyunBailianDataFullAccess策略）。

本示例支持在线调试及多语言代码示例生成。

PythonJavaPHPNode.jsC#Go
 
def submit_index_add_documents_job(client, workspace_id, index_id, file_id, source_type):
    """
    向一个文档搜索类知识库追加导入已解析的文件。

    参数:
        client (bailian20231229Client): 客户端（Client）。
        workspace_id (str): 业务空间ID。
        index_id (str): 知识库ID。
        file_id (str): 文件ID。
        source_type(str): 数据类型。

    返回:
        阿里云百炼服务的响应。
    """
    headers = {}
    submit_index_add_documents_job_request = bailian_20231229_models.SubmitIndexAddDocumentsJobRequest(
        index_id=index_id,
        document_ids=[file_id],
        source_type=source_type
    )
    runtime = util_models.RuntimeOptions()
    return client.submit_index_add_documents_job_with_options(workspace_id, submit_index_add_documents_job_request, headers, runtime)
请求示例

响应示例

2.2. 等待追加任务完成
索引任务的执行需要一定时间，在请求高峰时段，该过程可能需要数小时。查询其执行状态可以调用GetIndexJobStatus接口。

job_id：请传入提交追加文件任务时接口返回的Data.Id。

当本接口返回的Data.Status字段值为COMPLETED，表示本次更新的文件已全部成功追加至知识库。

本接口返回的文件列表Documents为本次追加（由您提供的job_id唯一确定）的所有文件。
重要
子账号调用本示例前需获取API权限（AliyunBailianDataFullAccess策略）。

本示例支持在线调试及多语言代码示例生成。

PythonJavaPHPNode.jsC#Go
 
def get_index_job_status(client, workspace_id, index_id, job_id):
    """
    查询索引任务状态。

    参数:
        client (bailian20231229Client): 客户端（Client）。
        workspace_id (str): 业务空间ID。
        index_id (str): 知识库ID。
        job_id (str): 任务ID。

    返回:
        阿里云百炼服务的响应。
    """
    headers = {}
    get_index_job_status_request = bailian_20231229_models.GetIndexJobStatusRequest(
        index_id=index_id,
        job_id=job_id
    )
    runtime = util_models.RuntimeOptions()
    return client.get_index_job_status_with_options(workspace_id, get_index_job_status_request, headers, runtime)
请求示例

响应示例

3. 删除旧文件
最后，从指定知识库中永久删除旧版本的文件（避免旧的知识被错误检索），可以调用DeleteIndexDocument接口。

file_id：请传入旧版本文件的FileId。

说明
仅能删除知识库中状态为导入失败（INSERT_ERROR）或导入成功（FINISH）的文件。如需查询知识库中的文件状态，可调用ListIndexDocuments接口。

重要
子账号调用本示例前需获取API权限（AliyunBailianDataFullAccess策略）。

本示例支持在线调试及多语言代码示例生成。

PythonJavaPHPNode.jsC#Go
 
def delete_index_document(client, workspace_id, index_id, file_id):
    """
    从指定的文档搜索类知识库中永久删除一个或多个文件。

    参数:
        client (bailian20231229Client): 客户端（Client）。
        workspace_id (str): 业务空间ID。
        index_id (str): 知识库ID。
        file_id (str): 文件ID。

    返回:
        阿里云百炼服务的响应。
    """
    headers = {}
    delete_index_document_request = bailian_20231229_models.DeleteIndexDocumentRequest(
        index_id=index_id,
        document_ids=[file_id]
    )
    runtime = util_models.RuntimeOptions()
    return client.delete_index_document_with_options(workspace_id, delete_index_document_request, headers, runtime)
请求示例

响应示例

管理知识库
创建和使用知识库不支持通过API操作，请使用阿里云百炼控制台操作。
查看知识库
要查看给定业务空间下的一个或多个知识库的信息，可以调用ListIndices接口。

client：如何获取client

workspace_id：如何获取业务空间ID

子账号只能查看自己已加入的业务空间中的知识库。
重要
子账号调用本示例前需获取API权限（AliyunBailianDataFullAccess策略）。

本示例支持在线调试及多语言代码示例生成。

PythonJavaPHPNode.jsC#Go
 
def list_indices(client, workspace_id):
    """
    获取指定业务空间下一个或多个知识库的详细信息。

    参数:
        client (bailian20231229Client): 客户端（Client）。
        workspace_id (str): 业务空间ID。

    返回:
        阿里云百炼服务的响应。
    """
    headers = {}
    list_indices_request = bailian_20231229_models.ListIndicesRequest()
    runtime = util_models.RuntimeOptions()
    return client.list_indices_with_options(workspace_id, list_indices_request, headers, runtime)
请求示例

响应示例

删除知识库
要永久性删除某个知识库，可以调用DeleteIndex接口。删除前，请解除该知识库关联的所有阿里云百炼应用（仅可通过阿里云百炼控制台操作），否则会删除失败。

client：如何获取client

workspace_id：如何获取业务空间ID

子账号只能删除自己已加入的业务空间中的知识库。
index_id：请传入初始化知识库时接口返回的Data.Id。

请注意：本操作不会删除您已添加至类目中的文件。

重要
子账号调用本示例前需获取API权限（AliyunBailianDataFullAccess策略）。

本示例支持在线调试及多语言代码示例生成。

PythonJavaPHPNode.jsC#Go
 
def delete_index(client, workspace_id, index_id):
    """
    永久性删除指定的知识库。

    参数:
        client (bailian20231229Client): 客户端（Client）。
        workspace_id (str): 业务空间ID。
        index_id (str): 知识库ID。

    返回:
        阿里云百炼服务的响应。
    """
    headers = {}
    delete_index_request = bailian_20231229_models.DeleteIndexRequest(
        index_id=index_id
    )
    runtime = util_models.RuntimeOptions()
    return client.delete_index_with_options(workspace_id, delete_index_request, headers, runtime)
请求示例

响应示例

API参考
请参阅API目录（知识库）获取最新完整的知识库API列表及输入输出参数。

常见问题
如何实现知识库的自动更新/同步？

文档搜索类知识库数据查询/图片问答类知识库音视频搜索类知识库
使用对象存储OSS管理文件，通过函数计算FC监听文件变更事件，自动同步更新至知识库，实现知识的实时更新。详见告别手动操作，让AI知识库自动更新。

为什么我新建的知识库里没有内容？

一般是由于没有执行或未能成功执行提交索引任务这一步导致。若调用CreateIndex接口后未成功调用SubmitIndexJob接口，您将得到一个空知识库。此时，您只需重新执行提交索引任务并等待索引任务完成即可。

遇到报错Access your uploaded file failed. Please check if your upload action was successful，应该如何处理？

一般是由于没有执行或未能成功执行上传文件到临时存储这一步导致。请在确认该步骤成功执行后，再调用AddFile接口。

遇到报错Access denied: Either you are not authorized to access this workspace, or the workspace does not exist，应该如何处理？

一般是由于：

您请求的服务地址（服务接入点）有误：以公网接入为例，如果您是中国站用户，应访问北京（公有云用户）或上海（金融云用户）地域的接入地址；如果您是国际站用户，应访问新加坡地域的接入地址。如果您正在使用在线调试功能，请确认您选择的服务地址正确无误（如下图所示）。

image

您传入的WorkspaceId值不正确，或者您还不是该业务空间的成员导致：请确认WorkspaceId值无误且您是该业务空间的成员后，再调用接口。如何被添加为指定业务空间的成员

遇到报错Specified access key is not found or invalid，应该如何处理？

一般是由于您传入的access_key_id或access_key_secret值不正确，或者该access_key_id已被禁用导致。请确认access_key_id值无误且未被禁用后，再调用接口。

计费说明
知识库采用按量付费（后付费），按小时统计下方计费项的用量，并从您的阿里云账户自动扣费。请确保账户余额充足（可前往费用与成本充值），以免因欠费导致服务中断。



计费项

说明

规格费用

标准版 或 旗舰版 知识库的实际运行时长费用，价格详见知识库计费说明。变更配置按变更时间点分段计费。

向量、排序模型调用费用

创建、更新或检索知识库时会调用向量（embedding）、排序（rerank）模型，会产生费用。按输入 Token 用量计费，价格以模型调用计费页为准。

账单查询：账单详情

错误码
如果调用本文中的API失败并收到错误信息，请参见错误中心进行解决。