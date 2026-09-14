@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -X utf8 -m wastekg.server
) else if exist "..\..\work\venv\Scripts\python.exe" (
  "..\..\work\venv\Scripts\python.exe" -X utf8 -m wastekg.server
) else (
  py -3 -X utf8 -m wastekg.server
)
if errorlevel 1 (
  echo 启动失败。请安装 Python 3.12，并按照 README.md 完成环境配置。
  pause
)
