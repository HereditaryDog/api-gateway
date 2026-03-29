@echo off
chcp 65001 >nul
echo ===================================
echo   推送到 GitHub 脚本
echo ===================================
echo.

set REPO_NAME=api-gateway
set USERNAME=HereditaryDog

cd /d "%~dp0"

echo [1/6] 初始化 Git...
git init

echo [2/6] 添加文件...
git add .

echo [3/6] 提交更改...
git commit -m "Initial commit: API Gateway - LLM API聚合转发平台"

echo [4/6] 创建 GitHub 仓库...
echo 请先在浏览器中创建仓库: https://github.com/new
echo 仓库名: %REPO_NAME%
echo.
pause

echo [5/6] 关联远程仓库...
git remote add origin https://github.com/%USERNAME%/%REPO_NAME%.git

echo [6/6] 推送到 GitHub...
git branch -M main
git push -u origin main

echo.
echo ===================================
echo 推送完成!
echo 访问: https://github.com/%USERNAME%/%REPO_NAME%
echo ===================================
pause
