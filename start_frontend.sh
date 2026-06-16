#!/bin/bash

# 单独启动前端

cd frontend

# 检查依赖
if [ ! -d "node_modules" ]; then
    echo "安装前端依赖..."
    npm install --legacy-peer-deps --cache /tmp/npm-cache
fi

echo "启动前端服务..."
npm run dev