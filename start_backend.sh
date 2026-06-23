#!/bin/bash

# 单独启动后端

cd backend-rust
echo "编译 Rust 后端..."
cargo build --release 2>/dev/null
echo "启动后端服务在 http://127.0.0.1:8000"
./target/release/backend 8000
#!/bin/bash

# 单独启动后端

cd backend
echo "启动后端服务在 http://127.0.0.1:8000"
python3 -m uvicorn app.main:app --reload --port 8000