@echo off
chcp 65001 >nul
title API Gateway
echo ===================================
echo    API Gateway 启动器
echo ===================================
echo.

:: 检查端口是否被占用
netstat -ano | findstr :8080 >nul
if %errorlevel% equ 0 (
    echo [WARNING] 端口 8080 已被占用，尝试使用 8081...
    set PORT=8081
) else (
    set PORT=8080
)

echo [INFO] 启动服务...
echo [INFO] 访问地址: http://localhost:%PORT%
echo.

:: 检查管理员账号
echo [INFO] 检查管理员账号...
python init_admin.py >nul 2>&1

:: 启动服务
python run.py
