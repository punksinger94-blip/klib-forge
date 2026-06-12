use std::{
    net::{SocketAddr, TcpListener, TcpStream},
    path::PathBuf,
    sync::Mutex,
    time::{Duration, Instant},
};

use serde::Serialize;
use tauri::{Manager, RunEvent, State};
use tauri_plugin_shell::{
    process::{CommandChild, CommandEvent},
    ShellExt,
};

#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
struct RuntimeInfo {
    base_url: String,
    managed: bool,
    backend_pid: Option<u32>,
    startup_error: Option<String>,
}

struct RuntimeState {
    info: Mutex<RuntimeInfo>,
    child: Mutex<Option<CommandChild>>,
}

impl RuntimeState {
    fn new() -> Self {
        Self {
            info: Mutex::new(RuntimeInfo {
                base_url: "http://127.0.0.1:8000".to_string(),
                managed: false,
                backend_pid: None,
                startup_error: None,
            }),
            child: Mutex::new(None),
        }
    }
}

#[tauri::command]
fn runtime_info(state: State<'_, RuntimeState>) -> RuntimeInfo {
    state
        .info
        .lock()
        .expect("runtime info lock poisoned")
        .clone()
}

fn reserve_local_port() -> Result<u16, std::io::Error> {
    let listener = TcpListener::bind(("127.0.0.1", 0))?;
    Ok(listener.local_addr()?.port())
}

fn wait_for_runtime(port: u16, timeout: Duration) -> bool {
    let address = SocketAddr::from(([127, 0, 0, 1], port));
    let started = Instant::now();
    while started.elapsed() < timeout {
        if TcpStream::connect_timeout(&address, Duration::from_millis(150)).is_ok() {
            return true;
        }
        std::thread::sleep(Duration::from_millis(100));
    }
    false
}

fn runtime_home(app: &tauri::App) -> Result<PathBuf, tauri::Error> {
    Ok(app.path().app_local_data_dir()?.join("runtime"))
}

fn start_runtime(app: &tauri::App) -> Result<(), Box<dyn std::error::Error>> {
    let port = reserve_local_port()?;
    let base_url = format!("http://127.0.0.1:{port}");
    let home = runtime_home(app)?;
    std::fs::create_dir_all(&home)?;

    let (mut receiver, child) = app
        .shell()
        .sidecar("klib-api")?
        .env("KLIB_API_HOST", "127.0.0.1")
        .env("KLIB_API_PORT", port.to_string())
        .env("KLIB_API_LOG_LEVEL", "warning")
        .env("KLIB_HOME", home)
        .env("KLIB_PARENT_PID", std::process::id().to_string())
        .spawn()?;
    let backend_pid = child.pid();

    let state = app.state::<RuntimeState>();
    *state.child.lock().expect("runtime child lock poisoned") = Some(child);
    *state.info.lock().expect("runtime info lock poisoned") = RuntimeInfo {
        base_url,
        managed: true,
        backend_pid: Some(backend_pid),
        startup_error: None,
    };

    let handle = app.handle().clone();
    tauri::async_runtime::spawn(async move {
        while let Some(event) = receiver.recv().await {
            match event {
                CommandEvent::Stdout(bytes) => {
                    eprintln!("klib-api: {}", String::from_utf8_lossy(&bytes));
                }
                CommandEvent::Stderr(bytes) => {
                    eprintln!("klib-api error: {}", String::from_utf8_lossy(&bytes));
                }
                CommandEvent::Error(message) => {
                    let state = handle.state::<RuntimeState>();
                    state
                        .info
                        .lock()
                        .expect("runtime info lock poisoned")
                        .startup_error = Some(message);
                }
                CommandEvent::Terminated(payload) => {
                    let state = handle.state::<RuntimeState>();
                    let mut info = state.info.lock().expect("runtime info lock poisoned");
                    info.managed = false;
                    info.backend_pid = None;
                    if payload.code != Some(0) {
                        info.startup_error =
                            Some(format!("K-LIB API exited with code {:?}", payload.code));
                    }
                    break;
                }
                _ => {}
            }
        }
    });

    if !wait_for_runtime(port, Duration::from_secs(12)) {
        return Err("K-LIB API did not become ready within 12 seconds".into());
    }

    Ok(())
}

fn record_startup_error(app: &tauri::App, error: &dyn std::fmt::Display) {
    app.state::<RuntimeState>()
        .info
        .lock()
        .expect("runtime info lock poisoned")
        .startup_error = Some(error.to_string());
}

#[cfg(target_os = "windows")]
fn stop_process_tree(pid: u32) {
    use std::{os::windows::process::CommandExt, process::Command};

    const CREATE_NO_WINDOW: u32 = 0x08000000;
    let _ = Command::new("taskkill")
        .args(["/PID", &pid.to_string(), "/T", "/F"])
        .creation_flags(CREATE_NO_WINDOW)
        .status();
}

#[cfg(not(target_os = "windows"))]
fn stop_process_tree(_pid: u32) {}

fn stop_runtime(handle: &tauri::AppHandle) {
    let state = handle.state::<RuntimeState>();
    let child = state
        .child
        .lock()
        .expect("runtime child lock poisoned")
        .take();
    if let Some(child) = child {
        stop_process_tree(child.pid());
        let _ = child.kill();
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let app = tauri::Builder::default()
        .manage(RuntimeState::new())
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![runtime_info])
        .setup(|app| {
            if let Err(error) = start_runtime(app) {
                record_startup_error(app, error.as_ref());
            }
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building K-LIB Forge");

    app.run(|handle, event| {
        if matches!(event, RunEvent::Exit | RunEvent::ExitRequested { .. }) {
            stop_runtime(handle);
        }
    });
}
