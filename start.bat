@echo off
chcp 65001 >nul
echo 🚀 启动 API Gateway...

:: 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python 未安装或未添加到 PATH
    exit /b 1
)

:: 创建虚拟环境
if not exist "venv" (
    echo 📦 创建虚拟环境...
    python -m venv venv
)

:: 激活虚拟环境
call venv\Scripts\activate.bat

:: 安装依赖
echo 📥 安装依赖...
pip install -q -r requirements.txt

:: 检查 .env 文件
if not exist ".env" (
    echo ⚙️  创建默认配置文件...
    copy .env.example .env
)

:: 初始化数据库
echo 🗄️  初始化数据库...
python -c "import asyncio; from app.core.database import init_db; asyncio.run(init_db())"

:: 创建管理员账号
echo 👤 创建管理员账号...
python init_admin.py

echo.
echo ✅ 启动完成！
echo 🌐 访问地址: http://localhost:8000
echo 📖 接口文档: http://localhost:8000/docs
echo.

:: 启动服务
set PORT=8080
uvicorn app.main:app --host 0.0.0.0 --port %PORT% --reload
