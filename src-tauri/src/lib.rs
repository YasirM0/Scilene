// Scilene desktop shell (#152).
//
// UNVERIFIED DRAFT: hand-authored because this environment has no
// Rust/Cargo/Node toolchain to run `npm create tauri-app@latest` or
// `cargo check` against. Written against Tauri v2 APIs from training
// knowledge, not compiled or run. Treat as a starting point to build
// and fix on a real dev machine, not as working code.
//
// Sidecar binary contract this code assumes (does not yet exist --
// see the accompanying report): a single frozen executable named
// `binaries/scilene-server-<target-triple>` (PyInstaller output
// wrapping `uvicorn.run(web.main:app, host="127.0.0.1", port=...)`)
// that:
//   - accepts `--port <N>` on argv
//   - binds 127.0.0.1:<N> only (never 0.0.0.0 -- this is a
//     single-user local sidecar, not a network service)
//   - serves GET /health -> {"status": "ok", "version": "..."}
//     (added to web/main.py in this same change)

use std::net::TcpListener;
use std::sync::Mutex;
use std::time::Duration;

use tauri::{Emitter, Manager};
use tauri_plugin_shell::process::CommandChild;
use tauri_plugin_shell::ShellExt;

/// Holds the sidecar's child-process handle so the window-close
/// handler can kill it. Populated once, right after spawn.
struct SidecarState(Mutex<Option<CommandChild>>);

/// Binds to an OS-assigned port, reads it back, then immediately
/// drops the listener so uvicorn can bind it instead. Small TOCTOU
/// window between drop and uvicorn's own bind, acceptable here since
/// this is a loopback-only port picked and consumed within the same
/// launch sequence, not a value handed to another process's future.
fn pick_free_port() -> u16 {
    let listener = TcpListener::bind("127.0.0.1:0").expect("failed to bind an ephemeral port");
    listener.local_addr().expect("no local_addr on bound listener").port()
}

async fn wait_for_health(port: u16, timeout: Duration, interval: Duration) -> bool {
    let url = format!("http://127.0.0.1:{port}/health");
    let client = reqwest::Client::new();
    let deadline = std::time::Instant::now() + timeout;

    while std::time::Instant::now() < deadline {
        if let Ok(resp) = client.get(&url).timeout(interval).send().await {
            if resp.status().is_success() {
                return true;
            }
        }
        tokio::time::sleep(interval).await;
    }
    false
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(SidecarState(Mutex::new(None)))
        .setup(|app| {
            let handle = app.handle().clone();

            tauri::async_runtime::spawn(async move {
                let port = pick_free_port();

                let sidecar_command = handle
                    .shell()
                    .sidecar("scilene-server")
                    .expect("scilene-server sidecar not found -- run the PyInstaller build first")
                    .args(["--port", &port.to_string()])
                    .env("SCILENE_RUNTIME", "desktop");

                let (mut rx, child) = sidecar_command
                    .spawn()
                    .expect("failed to spawn scilene-server sidecar");

                // Forward sidecar stdout/stderr to Tauri's log target so
                // startup failures (e.g. port already in use, a missing
                // dependency) are visible during development instead of
                // silently hanging at the health check below.
                tauri::async_runtime::spawn(async move {
                    while let Some(event) = rx.recv().await {
                        match event {
                            tauri_plugin_shell::process::CommandEvent::Stdout(line) => {
                                eprintln!("[scilene-server] {}", String::from_utf8_lossy(&line));
                            }
                            tauri_plugin_shell::process::CommandEvent::Stderr(line) => {
                                eprintln!("[scilene-server:err] {}", String::from_utf8_lossy(&line));
                            }
                            _ => {}
                        }
                    }
                });

                *handle.state::<SidecarState>().0.lock().unwrap() = Some(child);

                let ready = wait_for_health(
                    port,
                    Duration::from_secs(10),
                    Duration::from_millis(200),
                )
                .await;

                if !ready {
                    eprintln!(
                        "scilene-server did not become healthy on 127.0.0.1:{port} within 10s"
                    );
                    // TODO(#155-adjacent): surface this to the user via a
                    // native dialog instead of a silent stuck window --
                    // needs tauri-plugin-dialog, not wired up here.
                    return;
                }

                let url = format!("http://127.0.0.1:{port}").parse().unwrap();
                if let Some(window) = handle.get_webview_window("main") {
                    // navigate() wants a raw Url, not the WebviewUrl enum used
                    // when *creating* a webview -- caught by `cargo check`,
                    // not something I'd noticed by inspection alone.
                    let _ = window.navigate(url);
                    let _ = window.show();
                    let _ = handle.emit("scilene://ready", port);
                }
            });

            Ok(())
        })
        .on_window_event(|window, event| {
            // Kill the sidecar the moment the window closes -- otherwise
            // uvicorn keeps running as an orphaned background process
            // after the app appears to have quit.
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                if let Some(child) = window
                    .app_handle()
                    .state::<SidecarState>()
                    .0
                    .lock()
                    .unwrap()
                    .take()
                {
                    let _ = child.kill();
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running the Scilene desktop shell");
}
