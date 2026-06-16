#!/bin/bash

# 测试朝向约束

echo "测试朝向约束 - 立着放 (forbidden_horizontal_dims=['height'], H竖直)"
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
        "forbidden_horizontal_dims": ["height"]
      }
    ]
  }' | python3 -m json.tool

echo "\n\n测试朝向约束 - 躺着放 (forbidden_horizontal_dims=['width'], W竖直)"
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
        "forbidden_horizontal_dims": ["width"]
      }
    ]
  }' | python3 -m json.tool

echo "\n\n测试朝向约束 - 平着放 (forbidden_horizontal_dims=['length'], L竖直)"
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
        "forbidden_horizontal_dims": ["length"]
      }
    ]
  }' | python3 -m json.tool
