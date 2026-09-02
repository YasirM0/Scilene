// Scilene desktop shell (#152, #151).
//
// Verified against the real Tauri v2 crate source in a distrobox
// container with Node/Rust/webkit2gtk installed (this sandbox has
// none of those) -- `cargo build` passes. The Menu/notification APIs
// below (#151) were cross-checked against the actual installed crate
// source and doc-comment examples before writing this, not guessed
// from training knowledge alone (a past mistake in this same file:
// capabilities/default.json originally had fabricated permission
// syntax that only surfaced once a real build ran). What ISN'T
// verified: actual runtime behavior -- this sandbox has no display
// server, so the window, menu clicks, and notifications have never
// actually been seen or clicked. Only compilation is confirmed.
//
// Sidecar binary contract this code assumes: a single frozen
// executable named `binaries/scilene-server-<target-triple>`
// (PyInstaller output wrapping `uvicorn.run(web.main:app, ...)`) that:
//   - accepts `--port <N>` on argv
//   - binds 127.0.0.1:<N> only (never 0.0.0.0 -- this is a
//     single-user local sidecar, not a network service)
//   - serves GET /health -> {"status": "ok", "version": "..."}
//   - serves GET /api/window-title -> {"title", "rtl", "language"} (#151)
//   - serves GET /settings/update-status -> {"update_available",
//     "pending_version", "current_version", "auto_update"} (#153/#155)

use std::net::TcpListener;
use std::sync::Mutex;
use std::time::Duration;

use serde::Deserialize;
use tauri::menu::{Menu, MenuBuilder, SubmenuBuilder};
use tauri::{AppHandle, Emitter, Manager, Wry};
use tauri_plugin_notification::{NotificationExt, PermissionState};
use tauri_plugin_shell::process::CommandChild;
use tauri_plugin_shell::ShellExt;

/// Holds the sidecar's child-process handle so the window-close
/// handler can kill it. Populated once, right after spawn.
struct SidecarState(Mutex<Option<CommandChild>>);

/// The sidecar's port, shared with the menu-event handler (#151) so
/// File > Settings / Help > About Scilene can navigate the webview --
/// `on_menu_event`'s closure has no access to the async setup block's
/// local `port` variable otherwise.
struct PortState(Mutex<Option<u16>>);

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

fn default_language() -> String {
    "en".to_string()
}

#[derive(Deserialize)]
struct WindowTitleResponse {
    title: String,
    // Not read directly -- Tauri's set_title() renders whatever string
    // it's given as-is, and OS title bars already handle Unicode bidi
    // correctly without extra configuration (#151's own premise).
    // Kept in the struct only so serde doesn't reject the field.
    #[allow(dead_code)]
    #[serde(default)]
    rtl: bool,
    #[serde(default = "default_language")]
    language: String,
}

#[derive(Deserialize)]
struct UpdateStatus {
    update_available: bool,
    pending_version: Option<String>,
    #[allow(dead_code)]
    current_version: String,
    auto_update: bool,
}

struct MenuLabels {
    file: &'static str,
    settings: &'static str,
    quit: &'static str,
    help: &'static str,
    about: &'static str,
}

/// #151 -- menu labels can't go through web/i18n.py's t() the way page
/// content does: Tauri menus are built once in Rust from
/// GET /api/window-title's language field, not re-rendered per
/// request. Falls back to English for anything unrecognized (matches
/// the same fallback GET /api/window-title itself already applies).
fn menu_labels(language: &str) -> MenuLabels {
    match language {
        "ar" => MenuLabels {
            file: "ملف",
            settings: "إعدادات",
            quit: "خروج",
            help: "مساعدة",
            about: "حول سيلين",
        },
        "id" => MenuLabels {
            file: "Berkas",
            settings: "Pengaturan",
            quit: "Keluar",
            help: "Bantuan",
            about: "Tentang Scilene",
        },
        _ => MenuLabels {
            file: "File",
            settings: "Settings",
            quit: "Quit",
            help: "Help",
            about: "About Scilene",
        },
    }
}

/// (title, body template with a literal "{version}" placeholder) for
/// the dataset-update notification (#151/#153/#155's auto_update=False
/// path).
fn notification_strings(language: &str) -> (&'static str, &'static str) {
    match language {
        "ar" => (
            "تحديث Scilene متاح",
            "الإصدار {version} من قاعدة البيانات جاهز للتثبيت. افتح الإعدادات للتطبيق.",
        ),
        "id" => (
            "Pembaruan Scilene Tersedia",
            "Versi kumpulan data {version} siap dipasang. Buka Pengaturan untuk menerapkan.",
        ),
        _ => (
            "Scilene Update Available",
            "Dataset version {version} is ready to install. Open Settings to apply.",
        ),
    }
}

/// Built fresh from the language GET /api/window-title just returned --
/// called once at startup, not on every language change (the settings
/// page's language radio takes effect for the WEBVIEW's content
/// immediately via the normal page-render path; the native menu only
/// picks up a language change on the next launch, a known, accepted
/// limit given menus are otherwise built once at process start).
fn build_menu(handle: &AppHandle, language: &str) -> tauri::Result<Menu<Wry>> {
    let labels = menu_labels(language);

    let file_menu = SubmenuBuilder::new(handle, labels.file)
        .text("settings", labels.settings)
        .separator()
        .text("quit", labels.quit)
        .build()?;

    let help_menu = SubmenuBuilder::new(handle, labels.help)
        .text("about", labels.about)
        .build()?;

    // Only reassigned inside the #[cfg(target_os = "macos")] block
    // below -- on every other target that block is compiled out
    // entirely, which is what makes `mut` genuinely unused there.
    #[cfg_attr(not(target_os = "macos"), allow(unused_mut))]
    let mut builder = MenuBuilder::new(handle);

    #[cfg(target_os = "macos")]
    {
        // macOS convention: the menubar's FIRST submenu becomes the
        // special "app menu" (shown under the app name, not a literal
        // "Scilene" label the way this reads in source -- macOS
        // substitutes the real app name at render time). Not built on
        // other platforms, matching #151's own "Application menu (Mac
        // only...)" scoping -- Windows/Linux only get File/Help below.
        let app_menu = SubmenuBuilder::new(handle, "Scilene")
            .text("about", labels.about)
            .separator()
            .text("quit", labels.quit)
            .build()?;
        builder = builder.item(&app_menu);
    }

    builder.item(&file_menu).item(&help_menu).build()
}

fn kill_sidecar(app: &AppHandle) {
    if let Some(child) = app.state::<SidecarState>().0.lock().unwrap().take() {
        let _ = child.kill();
    }
}

fn navigate_to(app: &AppHandle, path: &str) {
    let port = *app.state::<PortState>().0.lock().unwrap();
    if let (Some(port), Some(window)) = (port, app.get_webview_window("main")) {
        if let Ok(url) = format!("http://127.0.0.1:{port}{path}").parse() {
            let _ = window.navigate(url);
        }
    }
}

/// #151's own explicit contract: never block anything waiting on
/// notification permission, and skip silently (just a log line) if
/// it isn't granted -- no request_permission() prompt forced here,
/// only a check of whatever the OS already reports.
fn send_update_notification(handle: &AppHandle, language: &str, version: &str) {
    let notification = handle.notification();

    match notification.permission_state() {
        Ok(PermissionState::Granted) => {
            let (title, body_template) = notification_strings(language);
            let body = body_template.replace("{version}", version);
            if let Err(e) = notification.builder().title(title).body(body).show() {
                eprintln!("[scilene] failed to show update notification: {e}");
            }
        }
        Ok(state) => {
            eprintln!(
                "[scilene] notification permission not granted ({state:?}) -- skipping update notification"
            );
        }
        Err(e) => {
            eprintln!("[scilene] failed to check notification permission: {e}");
        }
    }
}

/// #151's dataset-update notification -- polls GET /settings/update-status
/// (#153/#155) rather than being pushed to: Rust and the Python
/// sidecar only ever talk over this same loopback HTTP API, there's no
/// other channel for the sidecar's background update-check thread
/// (web/main.py) to tell Rust anything happened. 5 minutes is a plain
/// background-polling interval, not tied to any particular update
/// cadence; already_notified avoids re-notifying every 5 minutes for
/// the same still-pending update, and resets once update_available
/// goes false again (applied, or a newer version superseded it).
async fn poll_for_dataset_updates(handle: AppHandle, port: u16, language: String) {
    let client = reqwest::Client::new();
    let url = format!("http://127.0.0.1:{port}/settings/update-status");
    let mut already_notified = false;

    loop {
        let status: Option<UpdateStatus> = match client.get(&url).send().await {
            Ok(resp) => resp.json().await.ok(),
            Err(_) => None,
        };

        if let Some(status) = status {
            if status.update_available && !status.auto_update {
                if !already_notified {
                    already_notified = true;
                    if let Some(version) = &status.pending_version {
                        send_update_notification(&handle, &language, version);
                    }
                }
            } else {
                already_notified = false;
            }
        }

        tokio::time::sleep(Duration::from_secs(300)).await;
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_shell::init())
        .manage(SidecarState(Mutex::new(None)))
        .manage(PortState(Mutex::new(None)))
        .setup(|app| {
            let handle = app.handle().clone();

            tauri::async_runtime::spawn(async move {
                let port = pick_free_port();
                *handle.state::<PortState>().0.lock().unwrap() = Some(port);

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

                // #151 -- native chrome, once there's a real webview
                // showing real content to title/menu. window-title fetch
                // failing (network hiccup against our own loopback
                // sidecar, essentially impossible but not provably so)
                // falls back to English rather than leaving the window
                // untitled or panicking the setup task.
                let client = reqwest::Client::new();
                let language = match client
                    .get(format!("http://127.0.0.1:{port}/api/window-title"))
                    .timeout(Duration::from_secs(5))
                    .send()
                    .await
                {
                    Ok(resp) => match resp.json::<WindowTitleResponse>().await {
                        Ok(info) => {
                            if let Some(window) = handle.get_webview_window("main") {
                                let _ = window.set_title(&info.title);
                            }
                            info.language
                        }
                        Err(_) => default_language(),
                    },
                    Err(_) => default_language(),
                };

                match build_menu(&handle, &language) {
                    Ok(menu) => {
                        let _ = handle.set_menu(menu);
                    }
                    Err(e) => eprintln!("[scilene] failed to build native menu: {e}"),
                }

                tauri::async_runtime::spawn(poll_for_dataset_updates(handle.clone(), port, language));
            });

            Ok(())
        })
        .on_menu_event(|app, event| {
            if event.id() == "settings" {
                navigate_to(app, "/settings");
            } else if event.id() == "about" {
                navigate_to(app, "/about");
            } else if event.id() == "quit" {
                // Same cleanup as a normal window close (below) --
                // PredefinedMenuItem::quit() was considered instead of a
                // plain custom item here, but its exact interaction with
                // WindowEvent::CloseRequested (does it fire that event
                // before exiting, on every platform, before this app's
                // own kill_sidecar() would run?) isn't something this
                // sandbox can verify by actually clicking it -- an
                // explicit handler that's guaranteed to run kill_sidecar()
                // itself, rather than depending on that, is the safer
                // choice against ending up with an orphaned uvicorn
                // process, which #152 already spent real effort avoiding.
                kill_sidecar(app);
                app.exit(0);
            }
        })
        .on_window_event(|window, event| {
            // Kill the sidecar the moment the window closes -- otherwise
            // uvicorn keeps running as an orphaned background process
            // after the app appears to have quit.
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                kill_sidecar(window.app_handle());
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running the Scilene desktop shell");
}
