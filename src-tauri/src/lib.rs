// Backend modules
mod api;
mod models;
mod rotation;
mod extreme_point;
mod validator;
mod feasibility;
mod block_optimizer;
mod advanced_block_optimizer;

use std::sync::{Arc, Mutex};
use tauri::Manager;

struct BackendPort(Arc<Mutex<u16>>);

/// Candidate ports to try, in order.
const CANDIDATE_PORTS: &[u16] = &[8000, 8001, 8002, 8003, 8004, 8005, 8006, 8007, 8008, 8009];

fn start_backend_server(port_holder: Arc<Mutex<u16>>) {
    std::thread::spawn(move || {
        let rt = match tokio::runtime::Runtime::new() {
            Ok(rt) => rt,
            Err(e) => {
                eprintln!("FATAL: Failed to create tokio runtime: {}", e);
                return;
            }
        };
        rt.block_on(async move {
            let app = api::create_router();

            // Try each candidate port, then OS-assigned (0)
            let mut ports_to_try: Vec<u16> = CANDIDATE_PORTS.to_vec();
            ports_to_try.push(0);

            for port in ports_to_try {
                let addr = std::net::SocketAddr::from(([127, 0, 0, 1], port));
                match tokio::net::TcpListener::bind(addr).await {
                    Ok(listener) => {
                        let actual_port = listener.local_addr().unwrap().port();
                        eprintln!("Backend server listening on 127.0.0.1:{}", actual_port);
                        // Store the actual port for the frontend to query
                        *port_holder.lock().unwrap() = actual_port;
                        axum::serve(listener, app).await.ok();
                        return;
                    }
                    Err(e) => {
                        if port == 0 {
                            eprintln!("FATAL: Could not bind to any port: {}", e);
                            return;
                        }
                        eprintln!("Port {} unavailable ({}), trying next...", port, e);
                    }
                }
            }
        });
    });
}

#[tauri::command]
fn get_backend_url(state: tauri::State<BackendPort>) -> String {
    let port = *state.0.lock().unwrap();
    if port == 0 {
        // Backend hasn't bound yet, return a placeholder
        "http://127.0.0.1:0".to_string()
    } else {
        format!("http://127.0.0.1:{}", port)
    }
}

pub fn run() {
    let port_holder: Arc<Mutex<u16>> = Arc::new(Mutex::new(0));

    // Start embedded backend server
    start_backend_server(port_holder.clone());

    // Wait for backend to bind to a port (up to 10 seconds)
    let mut bound_port: u16 = 0;
    for i in 0..50 {
        let p = *port_holder.lock().unwrap();
        if p != 0 {
            bound_port = p;
            eprintln!("Backend ready on port {} (after {} checks)", p, i);
            break;
        }
        std::thread::sleep(std::time::Duration::from_millis(200));
    }

    if bound_port == 0 {
        eprintln!("WARNING: Backend server may not be ready, UI might not work");
    }

    tauri::Builder::default()
        .manage(BackendPort(port_holder))
        .invoke_handler(tauri::generate_handler![get_backend_url])
        .setup(|_app| Ok(()))
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
