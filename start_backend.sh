#!/bin/bash

# 单独启动后端

cd backend
echo "启动后端服务在 http://127.0.0.1:8000"
python3 -m uvicorn app.main:app --reload --port 8000