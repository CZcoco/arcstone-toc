"""
Arcstone-econ API 启动脚本
"""
import sys
import os
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
