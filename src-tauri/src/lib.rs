use std::process::{Child, Command};
use std::sync::Mutex;
use tauri::Manager;

struct BackendState {
    child: Mutex<Option<Child>>,
}

fn start_backend(app: &tauri::AppHandle) -> Option<Child> {
    let backend_dir = app
        .path()
        .resource_dir()
        .ok()?
        .join("binaries");

    let backend_path = backend_dir.join("backend.exe");

    if !backend_path.exists() {
        eprintln!("Backend not found at: {}", backend_path.display());
        eprintln!("Searched dir contents:");
        if let Ok(entries) = std::fs::read_dir(&backend_dir) {
            for e in entries.flatten() {
                eprintln!("  {}", e.path().display());
            }
        }
        return None;
    }

    eprintln!("Starting backend: {}", backend_path.display());

    let child = Command::new(&backend_path)
        .arg("8000")
        .current_dir(&backend_dir)
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
