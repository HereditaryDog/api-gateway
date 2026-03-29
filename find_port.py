#!/usr/bin/env python3
"""
查找可用端口并启动服务
"""
import socket
import sys

def find_free_port(start=8000, end=9000):
    """查找可用端口"""
    for port in range(start, end):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('localhost', port)) != 0:
                return port
    return None

if __name__ == "__main__":
    free_port = find_free_port()
    if free_port:
        print(f"✅ 找到可用端口: {free_port}")
        print(f"🚀 启动命令: PORT={free_port} python run.py")
        print(f"🌐 访问地址: http://localhost:{free_port}")
    else:
        print("❌ 未找到可用端口 (8000-9000)")
        sys.exit(1)
