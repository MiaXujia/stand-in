@echo off
rem stand-in：双击启动（首次会自动建库/生成 .env，前端没构建会先构建）
setlocal
cd /d "%~dp0"

if not exist ".env" (
  echo 首次运行，初始化...
  call uv run python -m app.bootstrap
)

if not exist "web\dist\index.html" (
  echo 构建前端...
  call pnpm -C web install
  call pnpm -C web build
)

call uv run python -m app.serve
if errorlevel 1 pause
