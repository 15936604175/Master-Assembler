use std::process::{Child, Command};
use std::sync::Mutex;
use tauri::Manager;

struct BackendState {
    child: Mutex<Option<Child>>,
}

fn start_backend(app: &tauri::AppHandle) -> Option<Child> {
    let resource_dir = app
        .path()
        .resource_dir()
        .ok()?
        .join("binaries");

    // Try multiple possible paths for the backend executable
    let possible_paths = [
        resource_dir.join("backend.exe"),
        resource_dir.join("backend-x86_64-pc-windows-msvc.exe"),
        app.path().resource_dir().ok()?.join("backend.exe"),
    ];

    let backend_path = possible_paths
        .iter()
        .find(|p| p.exists())
        .cloned();

    let path = match backend_path {
        Some(p) => p,
        None => {
            eprintln!("Backend executable not found, searched paths:");
            for p in &possible_paths {
                eprintln!("  {}", p.display());
            }
            return None;
        }
    };

    eprintln!("Starting backend: {}", path.display());

    let child = Command::new(&path)
        .arg("8000")
        .spawn()
        .ok()?;

    // Wait for backend to be ready
    let max_retries = 30;
    for i in 0..max_retries {
        if is_backend_ready() {
            eprintln!("Backend ready after {} tries", i + 1);
            return Some(child);
        }
        std::thread::sleep(std::time::Duration::from_millis(200));
    }

    eprintln!("Backend may not be ready yet, continuing anyway");
    Some(child)
}

fn is_backend_ready() -> bool {
    std::net::TcpStream::connect("127.0.0.1:8000").is_ok()
}

fn stop_backend(child: &mut Option<Child>) {
    if let Some(ref mut c) = child {
        let _ = c.kill();
        let _ = c.wait();
    }
}

#[tauri::command]
fn get_backend_url() -> String {
    "http://127.0.0.1:8000".to_string()
}

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![get_backend_url])
        .setup(|app| {
            let child = start_backend(&app.handle());
            app.manage(BackendState {
                child: Mutex::new(child),
            });
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                if let Some(state) = window.try_state::<BackendState>() {
                    if let Ok(mut guard) = state.child.lock() {
                        stop_backend(&mut *guard);
                    }
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
