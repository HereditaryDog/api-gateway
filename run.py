#!/usr/bin/env python3
"""
启动脚本
"""
import uvicorn
import sys

if __name__ == "__main__":
    import os
    port = int(os.getenv("PORT", "8080"))  # 默认改为 8080
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info"
    )
