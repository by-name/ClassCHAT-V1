@echo off
chcp 65001 >nul
title Class-Chat Server

cd /d "%~dp0"

echo ============================================
echo   Class-Chat Startup
echo ============================================
echo.
[INFO] Class-CHAT版本: V1

REM ========== Python ==========
set "PYTHON="
if exist "python\python.exe" set "PYTHON=python\python.exe"
if exist "python\Scripts\python.exe" set "PYTHON=python\Scripts\python.exe"
if not defined PYTHON (
    echo [ERROR] 未找到 python 目录
    pause & exit /b 1
)
echo [INFO] Python: %PYTHON%
"%PYTHON%" --version

REM ========== websockets ==========
"%PYTHON%" -c "import websockets" 2>nul
if errorlevel 1 (
    echo [INFO] 安装 websockets...
    "%PYTHON%" -m pip install websockets==12.0 --no-deps
)

REM ========== 文件检查 ==========
if not exist "Account.json" (echo [ERROR] 未找到 Account.json & pause & exit /b 1)
if not exist "chat_websocket.py" (echo [ERROR] 未找到 chat_websocket.py & pause & exit /b 1)
if not exist "file" mkdir file


REM ========== 启动 nginx ==========
if exist "nginx\nginx.exe" (
    echo [INFO] 启动 nginx...
    cd nginx
    nginx.exe -s stop 2>nul
    timeout /t 1 >nul
    start "" nginx.exe
    cd ..
    timeout /t 2 >nul
    tasklist | findstr nginx >nul && echo [INFO] nginx OK (port 8080) || echo [WARN] nginx failed
)

REM ========== 启动 WebSocket（独立窗口）==========
echo [INFO] 启动 WebSocket 服务器...
start "Class-Chat WS" cmd /k ""%PYTHON%" chat_websocket.py"

echo.
echo ============================================
echo   All services started!
echo   Browser: http://localhost:8080
echo   WebSocket: ws://localhost:8765
echo   Close WS window or press any key here to stop nginx.
echo ============================================
echo.

pause >nul

echo [INFO] 关闭 nginx...
if exist "nginx\nginx.exe" (
    cd nginx
    nginx.exe -s stop 2>nul
    cd ..
)
echo [INFO] Done.
pause