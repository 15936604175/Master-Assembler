# Master-Assembler 启动指南

## 快速启动

### 方式1：使用启动脚本（推荐）

```bash
# 同时启动前后端
./start.sh
```

### 方式2：分别启动

**启动后端：**
```bash
./start_backend.sh
# 或手动启动
cd backend
python3 -m uvicorn app.main:app --reload --port 8000
```

**启动前端：**
```bash
./start_frontend.sh
# 或手动启动
cd frontend
npm install --legacy-peer-deps --cache /tmp/npm-cache
npm run dev
```

## 服务地址

- **后端 API**: http://127.0.0.1:8000
- **前端界面**: http://localhost:5173 (默认)
- **API 文档**: http://127.0.0.1:8000/docs (FastAPI 自动生成)

## 测试 API

```bash
# 健康检查
curl http://127.0.0.1:8000/health

# 测试 Phase 1 贪心算法
bash test_api.sh
```

## 常见问题

### 1. npm 缓存权限错误

如果遇到 npm 缓存权限错误，使用临时缓存目录：

```bash
cd frontend
npm install --legacy-peer-deps --cache /tmp/npm-cache
```

### 2. Python 依赖缺失

```bash
cd backend
python3 -m pip install -r requirements.txt
```

### 3. 端口占用

如果 8000 或 5173 端口被占用，可以修改端口：

```bash
# 后端使用其他端口
cd backend
python3 -m uvicorn app.main:app --reload --port 8001

# 前端修改 vite.config.ts 中的 port 配置
```

## 性能优化说明

Phase 2 智能优化已优化参数配置：
- **遗传算法**: 20种群 × 30代 = 600次评估
- **局部搜索**: 100次迭代
- **帕累托优化**: 20种群 × 25代 = 500次评估
- **总耗时**: 3个商品约 0.5秒，20个商品约 30-60秒

## 使用建议

1. **少量商品（<10）**: 使用 Phase 2 智能优化，快速获得多个方案
2. **中等数量（10-30）**: Phase 2 预计 30-60秒完成
3. **大量商品（>50）**: 建议先使用 Phase 1 贪心算法快速验证，或调整超时参数

## 开发模式

后端使用 `--reload` 参数，代码修改会自动重启服务。
前端 Vite 支持热更新，修改代码后自动刷新页面。