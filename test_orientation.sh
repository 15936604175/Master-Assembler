#!/bin/bash

# 测试朝向约束

echo "测试朝向约束 - 高度必须垂直 (forbidden_horizontal_dim='height')"
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
        "id": "box1",
        "length": 800,
        "width": 600,
        "height": 500,
        "weight": 100,
        "quantity": 1,
        "is_fragile": false,
        "batch_number": 0,
        "forbidden_horizontal_dim": "height"
      }
    ]
  }' | python3 -m json.tool

echo "\n\n测试朝向约束 - 宽度必须垂直 (forbidden_horizontal_dim='width')"
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
        "id": "box2",
        "length": 800,
        "width": 600,
        "height": 500,
        "weight": 100,
        "quantity": 1,
        "is_fragile": false,
        "batch_number": 0,
        "forbidden_horizontal_dim": "width"
      }
    ]
  }' | python3 -m json.tool

echo "\n\n测试朝向约束 - 长度必须垂直 (forbidden_horizontal_dim='length')"
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
        "id": "box3",
        "length": 800,
        "width": 600,
        "height": 500,
        "weight": 100,
        "quantity": 1,
        "is_fragile": false,
        "batch_number": 0,
        "forbidden_horizontal_dim": "length"
      }
    ]
  }' | python3 -m json.tool