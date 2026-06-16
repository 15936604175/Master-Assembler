import requests
import json

def test_orientation_constraint():
    base_url = "http://127.0.0.1:8000"
    
    container = {
        "length": 5898,
        "width": 2352,
        "height": 2395,
        "max_weight": 28000
    }
    
    # 测试1: 高度必须垂直
    print("=" * 60)
    print("测试1: forbidden_horizontal_dim='height' (高度必须垂直)")
    print("原始尺寸: L=800, W=600, H=500")
    print("期望: orientation='height_vertical', 旋转后尺寸=(800, 500, 600)")
    print("=" * 60)
    
    response = requests.post(f"{base_url}/api/optimize", json={
        "container": container,
        "items": [{
            "id": "box1",
            "length": 800,
            "width": 600,
            "height": 500,
            "weight": 100,
            "quantity": 1,
            "is_fragile": False,
            "batch_number": 0,
            "forbidden_horizontal_dim": "height"
        }]
    })
    
    result = response.json()
    if result['success'] and result['placements']:
        p = result['placements'][0]
        print(f"✓ 放置成功")
        print(f"  位置: ({p['x']}, {p['y']}, {p['z']})")
        print(f"  旋转后尺寸: L={p['length']}, H={p['height']}, W={p['width']}")
        print(f"  rotation: {p['rotation']}")
        print(f"  orientation: {p['orientation']}")
        
        # 验证
        if p['orientation'] == 'height_vertical':
            print("✓ 朝向正确: height_vertical")
        else:
            print(f"✗ 朝向错误: 期望 height_vertical, 实际 {p['orientation']}")
        
        # 验证尺寸
        if p['length'] == 800 and p['height'] == 500 and p['width'] == 600:
            print("✓ 尺寸正确: (800, 500, 600)")
        else:
            print(f"✗ 尺寸错误: 期望 (800, 500, 600), 实际 ({p['length']}, {p['height']}, {p['width']})")
    else:
        print("✗ 放置失败")
    
    # 测试2: 宽度必须垂直
    print("\n" + "=" * 60)
    print("测试2: forbidden_horizontal_dim='width' (宽度必须垂直)")
    print("原始尺寸: L=800, W=600, H=500")
    print("期望: orientation='width_vertical', 旋转后尺寸=(800, 600, 500)")
    print("=" * 60)
    
    response = requests.post(f"{base_url}/api/optimize", json={
        "container": container,
        "items": [{
            "id": "box2",
            "length": 800,
            "width": 600,
            "height": 500,
            "weight": 100,
            "quantity": 1,
            "is_fragile": False,
            "batch_number": 0,
            "forbidden_horizontal_dim": "width"
        }]
    })
    
    result = response.json()
    if result['success'] and result['placements']:
        p = result['placements'][0]
        print(f"✓ 放置成功")
        print(f"  位置: ({p['x']}, {p['y']}, {p['z']})")
        print(f"  旋转后尺寸: L={p['length']}, H={p['height']}, W={p['width']}")
        print(f"  rotation: {p['rotation']}")
        print(f"  orientation: {p['orientation']}")
        
        # 验证
        if p['orientation'] == 'width_vertical':
            print("✓ 朝向正确: width_vertical")
        else:
            print(f"✗ 朝向错误: 期望 width_vertical, 实际 {p['orientation']}")
        
        # 验证尺寸
        if p['length'] == 800 and p['height'] == 600 and p['width'] == 500:
            print("✓ 尺寸正确: (800, 600, 500)")
        else:
            print(f"✗ 尺寸错误: 期望 (800, 600, 500), 实际 ({p['length']}, {p['height']}, {p['width']})")
    else:
        print("✗ 放置失败")
    
    # 测试3: 长度必须垂直
    print("\n" + "=" * 60)
    print("测试3: forbidden_horizontal_dim='length' (长度必须垂直)")
    print("原始尺寸: L=800, W=600, H=500")
    print("期望: orientation='length_vertical', 旋转后尺寸=(600, 800, 500)")
    print("=" * 60)
    
    response = requests.post(f"{base_url}/api/optimize", json={
        "container": container,
        "items": [{
            "id": "box3",
            "length": 800,
            "width": 600,
            "height": 500,
            "weight": 100,
            "quantity": 1,
            "is_fragile": False,
            "batch_number": 0,
            "forbidden_horizontal_dim": "length"
        }]
    })
    
    result = response.json()
    if result['success'] and result['placements']:
        p = result['placements'][0]
        print(f"✓ 放置成功")
        print(f"  位置: ({p['x']}, {p['y']}, {p['z']})")
        print(f"  旋转后尺寸: L={p['length']}, H={p['height']}, W={p['width']}")
        print(f"  rotation: {p['rotation']}")
        print(f"  orientation: {p['orientation']}")
        
        # 验证
        if p['orientation'] == 'length_vertical':
            print("✓ 朝向正确: length_vertical")
        else:
            print(f"✗ 朝向错误: 期望 length_vertical, 实际 {p['orientation']}")
        
        # 验证尺寸
        if p['length'] == 600 and p['height'] == 800 and p['width'] == 500:
            print("✓ 尺寸正确: (600, 800, 500)")
        else:
            print(f"✗ 尺寸错误: 期望 (600, 800, 500), 实际 ({p['length']}, {p['height']}, {p['width']})")
    else:
        print("✗ 放置失败")

if __name__ == "__main__":
    test_orientation_constraint()