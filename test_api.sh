#!/bin/bash

# 测试 Phase 2 API

echo "测试后端健康检查..."
curl http://127.0.0.1:8000/health

echo "\n\n测试 Phase 1 贪心算法..."
curl -X POST http://127.0.0.1:8000/api/optimize \
  -H "Content-Type: application/json" \
  -d '{
    "container": {
      "length": 5898,
      "width": 2352,
      "height": 2395,
      "max_weight": 28000
    },
    "items": [
      {
        "id": "item1",
        "length": 600,
        "width": 400,
        "height": 300,
        "weight": 50,
        "quantity": 2,
        "is_fragile": false,
        "batch_number": 0
      },
      {
        "id": "item2",
        "length": 800,
        "width": 600,
        "height": 500,
        "weight": 100,
        "quantity": 1,
        "is_fragile": false,
        "batch_number": 0
      },
      {
        "id": "item3",
        "length": 1000,
        "width": 800,
        "height": 600,
        "weight": 150,
        "quantity": 1,
        "is_fragile": false,
        "batch_number": 0
      }
    ]
  }'

echo "\n\n测试 Phase 2 智能优化（超时60秒）..."
curl -X POST "http://127.0.0.1:8000/api/optimize-phase2?timeout_seconds=60" \
  -H "Content-Type: application/json" \
  -d '{
    "container": {
      "length": 5898,
      "width": 2352,
      "height": 2395,
      "max_weight": 28000
    },
    "items": [
      {
        "id": "item1",
        "length": 600,
        "width": 400,
        "height": 300,
        "weight": 50,
        "quantity": 2,
        "is_fragile": false,
        "batch_number": 0
      },
      {
        "id": "item2",
        "length": 800,
        "width": 600,
        "height": 500,
        "weight": 100,
        "quantity": 1,
        "is_fragile": false,
        "batch_number": 0
      },
      {
        "id": "item3",
        "length": 1000,
        "width": 800,
        "height": 600,
        "weight": 150,
        "quantity": 1,
        "is_fragile": false,
        "batch_number": 0
      }
    ]
  }'