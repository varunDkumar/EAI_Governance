use std::fs;
use std::net::TcpStream;
use std::io::{Read, Write};
use std::path::PathBuf;
use std::process::{Child, Command};
use std::sync::Mutex;
use std::thread;
use std::time::{Duration, Instant};
use tauri::Manager;
use tauri_plugin_shell::process::CommandChild;
use tauri_plugin_shell::ShellExt;

// This build is tied to this specific checkout on this machine — the real
// data (SQLite + Chroma + imported corpus) and moodle-bak corpus live at
// fixed paths here, not inside the app bundle. See README "Known limitations".
const REPO_ROOT: &str = "/Users/dvss/Desktop/EYP_Demo";

enum BackendHandle {
    Sidecar(CommandChild),
    DevProcess(Child),
    AlreadyRunning,
}

struct BackendState(Mutex<Option<BackendHandle>>);

/// The sidecar's own working directory (somewhere inside the .app bundle)
/// has no path back to the real project's `.env`, so `find_dotenv` in the
/// Python backend can't locate it there. Read it here instead and pass each
/// key explicitly — same reasoning as ATF_DATA_DIR/ATF_CORPUS_ROOT below.
fn read_dotenv_pairs() -> Vec<(String, String)> {
    let path = PathBuf::from(REPO_ROOT).join(".env");
    let Ok(contents) = fs::read_to_string(&path) else {
        eprintln!("No .env found at {:?} — LLM provider will use its default.", path);
        return Vec::new();
    };
    contents
        .lines()
        .filter_map(|line| {
            let line = line.trim();
            if line.is_empty() || line.starts_with('#') {
                return None;
            }
            let (key, value) = line.split_once('=')?;
            Some((key.trim().to_string(), value.trim().to_string()))
        })
        .collect()
}

fn backend_already_running() -> bool {
    let Ok(mut stream) = TcpStream::connect_timeout(
        &"127.0.0.1:8756".parse().unwrap(),
        Duration::from_millis(200),
    ) else { return false };
    let _ = stream.set_read_timeout(Some(Duration::from_millis(500)));
    if stream.write_all(b"GET /simulator/registry HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n").is_err() { return false; }
    let mut response = String::new();
    stream.read_to_string(&mut response).is_ok() && response.starts_with("HTTP/1.1 200")
}

fn wait_for_backend(timeout: Duration) -> bool {
    let deadline = Instant::now() + timeout;
    while Instant::now() < deadline {
        if backend_already_running() { return true; }
        thread::sleep(Duration::from_millis(250));
    }
    false
}

/// Dev-mode fallback: spawn the backend from the project's own Python venv.
/// Used when `src-tauri/binaries/atf-backend-<target-triple>` hasn't been
/// built (e.g. plain `tauri dev` without running the PyInstaller build first).
fn spawn_dev_backend() -> Option<Child> {
    let dir = PathBuf::from(REPO_ROOT).join("backend");
    let python = dir.join(".venv/bin/python");
    if !python.exists() {
        eprintln!("Backend venv not found at {:?} — start it manually.", python);
        return None;
    }
    Command::new(python)
        .args(["-m", "uvicorn", "main:app", "--port", "8756"])
        .current_dir(&dir)
        .spawn()
        .map_err(|e| eprintln!("Failed to start dev backend: {e}"))
        .ok()
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_opener::init())
        .setup(|app| {
            let handle = if backend_already_running() {
                BackendHandle::AlreadyRunning
            } else {
                let data_dir = format!("{REPO_ROOT}/backend/data");
                let corpus_root = format!("{REPO_ROOT}/moodle-bak");
                let dotenv_pairs = read_dotenv_pairs();

                match app.shell().sidecar("atf-backend").map(|cmd| {
                    let mut cmd = cmd.env("ATF_DATA_DIR", &data_dir).env("ATF_CORPUS_ROOT", &corpus_root);
                    for (key, value) in &dotenv_pairs {
                        cmd = cmd.env(key, value);
                    }
                    cmd
                })
                {
                    Ok(cmd) => match cmd.spawn() {
                        Ok((_rx, mut child)) => {
                            if wait_for_backend(Duration::from_secs(45)) {
                                BackendHandle::Sidecar(child)
                            } else {
                                eprintln!("Bundled backend did not become ready; trying the local Python environment.");
                                let _ = child.kill();
                                match spawn_dev_backend() {
                                    Some(mut dev) if wait_for_backend(Duration::from_secs(20)) => BackendHandle::DevProcess(dev),
                                    Some(mut dev) => { let _ = dev.kill(); let _ = dev.wait(); BackendHandle::AlreadyRunning },
                                    None => BackendHandle::AlreadyRunning,
                                }
                            }
                        }
                        Err(e) => {
                            eprintln!("Sidecar spawn failed ({e}); falling back to dev venv.");
                            match spawn_dev_backend() {
                                Some(child) => BackendHandle::DevProcess(child),
                                None => BackendHandle::AlreadyRunning, // nothing we can do; UI will show "offline"
                            }
                        }
                    },
                    Err(e) => {
                        eprintln!("Sidecar binary not found ({e}); falling back to dev venv.");
                        match spawn_dev_backend() {
                            Some(child) => BackendHandle::DevProcess(child),
                            None => BackendHandle::AlreadyRunning,
                        }
                    }
                }
            };
            app.manage(BackendState(Mutex::new(Some(handle))));
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app_handle, event| {
            if let tauri::RunEvent::ExitRequested { .. } | tauri::RunEvent::Exit = event {
                if let Some(state) = app_handle.try_state::<BackendState>() {
                    if let Ok(mut guard) = state.0.lock() {
                        match guard.take() {
                            Some(BackendHandle::Sidecar(child)) => {
                                let _ = child.kill();
                            }
                            Some(BackendHandle::DevProcess(mut child)) => {
                                let _ = child.kill();
                                let _ = child.wait();
                            }
                            _ => {}
                        }
                    }
                }
            }
        });
}
