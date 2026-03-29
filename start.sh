#!/bin/bash

# API Gateway 快速启动脚本

echo "🚀 启动 API Gateway..."

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 未安装"
    exit 1
fi

# 创建虚拟环境
if [ ! -d "venv" ]; then
    echo "📦 创建虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
echo "📥 安装依赖..."
pip install -q -r requirements.txt

# 检查 .env 文件
if [ ! -f ".env" ]; then
    echo "⚙️  创建默认配置文件..."
    cp .env.example .env
fi

# 初始化数据库
echo "🗄️  初始化数据库..."
python -c "import asyncio; from app.core.database import init_db; asyncio.run(init_db())"

# 创建管理员账号
echo "👤 创建管理员账号..."
python init_admin.py

echo ""
echo "✅ 启动完成！"
echo "🌐 访问地址: http://localhost:8000"
echo "📖 接口文档: http://localhost:8000/docs"
echo ""

# 启动服务
export PORT=${PORT:-8080}
uvicorn app.main:app --host 0.0.0.0 --port $PORT --reload
