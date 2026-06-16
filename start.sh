#!/bin/bash

# Master-Assembler 启动脚本

# 存储后台进程 PID
BACKEND_PID=""
FRONTEND_PID=""

# 清理函数：退出时杀死所有子进程
cleanup() {
    echo ""
    echo "=========================================="
    echo "正在关闭服务..."
    
    if [ -n "$BACKEND_PID" ] && kill -0 "$BACKEND_PID" 2>/dev/null; then
        echo "关闭后端服务 (PID: $BACKEND_PID)..."
        kill "$BACKEND_PID" 2>/dev/null
        wait "$BACKEND_PID" 2>/dev/null
    fi
    
    if [ -n "$FRONTEND_PID" ] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
        echo "关闭前端服务 (PID: $FRONTEND_PID)..."
        kill "$FRONTEND_PID" 2>/dev/null
        wait "$FRONTEND_PID" 2>/dev/null
    fi
    
    # 额外清理：确保端口释放
    sleep 1
    lsof -ti:8000 | xargs kill -9 2>/dev/null
    lsof -ti:5173 | xargs kill -9 2>/dev/null
    
    echo "✓ 所有服务已关闭"
    echo "=========================================="
    exit 0
}

# 捕获退出信号 (Ctrl+C, 终端关闭等)
trap cleanup SIGINT SIGTERM EXIT

echo "=========================================="
echo "装配大师 - 启动脚本"
echo "(按 Ctrl+C 可安全关闭所有服务)"
echo "=========================================="

# 清理可能残留的旧进程
echo "\n清理残留端口..."
lsof -ti:8000 | xargs kill -9 2>/dev/null || true
lsof -ti:5173 | xargs kill -9 2>/dev/null || true

# 检查后端是否已启动
echo "检查后端服务..."
if curl -s http://127.0.0.1:8000/health > /dev/null 2>&1; then
    echo "✓ 后端服务已运行在 http://127.0.0.1:8000"
else
    echo "启动后端服务..."
    cd backend
    python3 -m uvicorn app.main:app --reload --port 8000 &
    BACKEND_PID=$!
    cd ..
    sleep 3
    if kill -0 "$BACKEND_PID" 2>/dev/null; then
        echo "✓ 后端服务已启动 (PID: $BACKEND_PID)"
    else
        echo "✗ 后端服务启动失败"
        exit 1
    fi
fi

# 启动前端
echo "\n启动前端服务..."
cd frontend

# 检查 node_modules 是否存在
if [ ! -d "node_modules" ]; then
    echo "安装前端依赖..."
    npm install --legacy-peer-deps --cache /tmp/npm-cache
fi

# 启动开发服务器（前台运行，Ctrl+C 时触发 cleanup）
echo "启动 Vite 开发服务器..."
npm run dev &
FRONTEND_PID=$!

# 等待前端进程结束（Ctrl+C 或崩溃时退出）
wait "$FRONTEND_PID"

# 如果前端正常退出，也会触发 cleanup trap
