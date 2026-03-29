#!/usr/bin/env python3
"""
诊断脚本 - 检查服务启动问题
"""
import subprocess
import sys
import os
import socket

def check_port(port):
    """检查端口是否被占用"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

def main():
    print("🔍 API Gateway 诊断工具")
    print("=" * 50)
    
    # 1. 检查 Python 版本
    print(f"\n1. Python 版本: {sys.version}")
    if sys.version_info < (3, 11):
        print("   ⚠️ 警告: 建议 Python 3.11+")
    else:
        print("   ✅ Python 版本正常")
    
    # 2. 检查依赖
    print("\n2. 检查依赖包...")
    required = ['fastapi', 'uvicorn', 'sqlalchemy', 'httpx', 'cryptography']
    missing = []
    for pkg in required:
        try:
            __import__(pkg)
            print(f"   ✅ {pkg}")
        except ImportError:
            print(f"   ❌ {pkg} - 未安装")
            missing.append(pkg)
    
    if missing:
        print(f"\n   请运行: pip install {' '.join(missing)}")
        return
    
    # 3. 检查端口
    print("\n3. 检查端口...")
    port = int(os.getenv('PORT', '8080'))
    if check_port(port):
        print(f"   ⚠️ 端口 {port} 已被占用")
        # 找新端口
        for p in range(8080, 9000):
            if not check_port(p):
                print(f"   💡 建议使用端口: {p}")
                break
    else:
        print(f"   ✅ 端口 {port} 可用")
    
    # 4. 测试启动
    print("\n4. 测试导入...")
    try:
        from app.main import app
        print("   ✅ 应用导入成功")
    except Exception as e:
        print(f"   ❌ 导入失败: {e}")
        return
    
    # 5. 检查数据库
    print("\n5. 检查数据库...")
    try:
        import asyncio
        from app.core.database import init_db
        asyncio.run(init_db())
        print("   ✅ 数据库初始化成功")
    except Exception as e:
        print(f"   ⚠️ 数据库警告: {e}")
    
    print("\n" + "=" * 50)
    print("✅ 诊断完成，尝试启动服务...")
    print(f"\n启动命令: python run.py")
    print(f"访问地址: http://localhost:{port}")

if __name__ == "__main__":
    main()
