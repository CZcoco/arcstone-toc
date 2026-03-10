"""
Arcstone-econ API 启动脚本
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import uvicorn

API_PORT = int(os.environ.get("ARCSTONE_ECON_API_PORT", "18081"))

if __name__ == "__main__":
    uvicorn.run(
        "src.api.app:app",
        host="127.0.0.1",
        port=API_PORT,
        reload=False,
    )
