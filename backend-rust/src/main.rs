mod api;
mod models;
mod rotation;
mod extreme_point;
mod validator;
mod feasibility;
mod block_optimizer;
mod advanced_block_optimizer;

use std::net::SocketAddr;

#[tokio::main]
async fn main() {
    let args: Vec<String> = std::env::args().collect();
    let port: u16 = if args.len() > 1 {
        args[1].parse().unwrap_or(8000)
    } else {
        8000
    };

    let app = api::create_router();
    let addr = SocketAddr::from(([127, 0, 0, 1], port));
    eprintln!("Rust backend starting on {}", addr);
    let listener = tokio::net::TcpListener::bind(addr).await.unwrap();
    axum::serve(listener, app).await.unwrap();
}
