"""
Arcstone-econ API 启动脚本
"""
import sys
import os

# 清理代理环境变量，避免 Clash TUN 模式等干扰本地连接
# TUN 模式会强制代理所有流量（包括 127.0.0.1），导致前后端通信失败
os.environ.pop("HTTP_PROXY", None)
os.environ.pop("HTTPS_PROXY", None)
os.environ.pop("http_proxy", None)
os.environ.pop("https_proxy", None)
# 保留 NO_PROXY 作为后备
os.environ["NO_PROXY"] = "127.0.0.1,localhost,127.0.0.1:18081,localhost:18081"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import socket
import uvicorn

API_PORT = int(os.environ.get("ARCSTONE_ECON_API_PORT", "18081"))

if __name__ == "__main__":
    if API_PORT == 0:
        # 让 OS 分配空闲端口
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        actual_port = sock.getsockname()[1]
        sock.close()
    else:
        actual_port = API_PORT

    # Electron 解析这行拿到实际端口
    print(f"ARCSTONE_PORT={actual_port}", flush=True)

    uvicorn.run(
        "src.api.app:app",
        host="127.0.0.1",
        port=actual_port,
        reload=False,
    )
