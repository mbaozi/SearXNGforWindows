@echo off
title SearXNG for Windows
echo Starting SearXNG for Windows...

:: 检查是否存在 python.exe 和 webapp.py
if not exist ".\python\python.exe" (
    echo Error: python.exe not found in the current directory.
    pause
    exit /b
)

if not exist ".\searx\webapp.py" (
    echo Error: webapp.py not found in the specified path.
    pause
    exit /b
)

:: 启动 Searx
.\python\python.exe .\searx\webapp.py

pause