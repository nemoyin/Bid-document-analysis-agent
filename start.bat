@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

title 投标标书智能分析监督系统 (BASS-MVP)

echo ============================================
echo   投标标书智能分析监督系统 - 启动中...
echo ============================================
echo.

set "PROJECT_DIR=%~dp0"
set "BACKEND_DIR=%PROJECT_DIR%backend"
set "FRONTEND_DIR=%PROJECT_DIR%frontend"
set "BACKEND_PORT=8006"
set "FRONTEND_PORT=5173"

:: ==========================================
:: 1. 检查 Python
:: ==========================================
echo [1/5] 检查 Python 环境...
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] 未找到 Python，请先安装 Python 3.10+
    pause
    exit /b 1
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do echo   Python %%v

:: ==========================================
:: 2. 后端环境初始化
:: ==========================================
echo.
echo [2/5] 初始化后端环境...

cd /d "%BACKEND_DIR%"

:: 创建虚拟环境
if not exist "venv\Scripts\python.exe" (
    echo   创建虚拟环境...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo [ERROR] 虚拟环境创建失败
        pause
        exit /b 1
    )
)

:: 安装依赖
echo   检查并安装 Python 依赖...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip -q 2>nul
python -m pip install -r requirements.txt -q
if %errorlevel% neq 0 (
    echo [WARN] 部分依赖安装失败，尝试继续...
)

:: 创建必要目录
if not exist "data" mkdir data
if not exist "data\logs" mkdir data\logs
if not exist "data\uploads" mkdir data\uploads
if not exist "data\reports" mkdir data\reports
if not exist "data\chromadb" mkdir data\chromadb

echo   后端环境就绪

:: ==========================================
:: 3. 前端环境初始化
:: ==========================================
echo.
echo [3/5] 初始化前端环境...

cd /d "%FRONTEND_DIR%"

if not exist "node_modules" (
    echo   安装前端依赖...
    call npm install
    if %errorlevel% neq 0 (
        echo [ERROR] 前端依赖安装失败
        pause
        exit /b 1
    )
)
echo   前端环境就绪

:: ==========================================
:: 4. 启动后端服务 (端口 8006)
:: ==========================================
echo.
echo [4/5] 启动后端服务 (端口 %BACKEND_PORT%)...

cd /d "%BACKEND_DIR%"
call venv\Scripts\activate.bat

start "BASS-Backend" cmd /c "cd /d "%BACKEND_DIR%" && venv\Scripts\activate.bat && uvicorn app.main:app --host 0.0.0.0 --port %BACKEND_PORT% --reload"

:: 等待后端启动
echo   等待后端服务启动...
timeout /t 3 /nobreak >nul

:: ==========================================
:: 5. 启动前端服务 (端口 5173)
:: ==========================================
echo [5/5] 启动前端服务 (端口 %FRONTEND_PORT%)...

cd /d "%FRONTEND_DIR%"

start "BASS-Frontend" cmd /c "cd /d "%FRONTEND_DIR%" && npm run dev"

echo.
echo ============================================
echo   服务启动完成！
echo.
echo   后端 API:  http://localhost:%BACKEND_PORT%
echo   API 文档: http://localhost:%BACKEND_PORT%/api/docs
echo   前端页面: http://localhost:%FRONTEND_PORT%
echo.
echo   按任意键关闭此窗口（服务将继续运行）
echo ============================================
pause
endlocal
