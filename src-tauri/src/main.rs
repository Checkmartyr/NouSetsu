// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

#[cfg(debug_assertions)]
use std::env;
use std::{
    fs::{File, OpenOptions},
    io::{BufRead, BufReader, Error, ErrorKind, Read, Write},
    net::{SocketAddr, TcpStream},
    path::{Path, PathBuf},
    process::{Child, Command, Stdio},
    sync::Mutex,
    thread,
    time::{Duration, Instant},
};
use tauri::Manager;

const BACKEND_HOST: &str = "127.0.0.1";
const BACKEND_PORT: u16 = 15474;
#[cfg(not(debug_assertions))]
const BACKEND_URL: &str = "http://127.0.0.1:15474";

#[derive(Default)]
struct BackendProcess(Mutex<Option<Child>>);

impl BackendProcess {
    fn stop(&self) -> Result<(), Error> {
        let mut process = self
            .0
            .lock()
            .map_err(|_| Error::other("Backend process state was poisoned"))?;
        let Some(child) = process.as_mut() else {
            return Err(Error::other(
                "The NouSetsu backend is not managed by this desktop app. Close the existing backend and restart NouSetsu before updating.",
            ));
        };
        if child.try_wait()?.is_none() {
            child.kill()?;
            child.wait()?;
        }
        *process = None;
        drop(process);
        if backend_is_ready() {
            return Err(Error::other(
                "A NouSetsu backend is still responding after shutdown. Close it before installing updates.",
            ));
        }
        Ok(())
    }
}

#[tauri::command]
fn stop_backend_before_update(backend: tauri::State<'_, BackendProcess>) -> Result<(), String> {
    backend
        .stop()
        .map_err(|error| format!("Could not stop the NouSetsu backend before updating: {error}"))
}

#[derive(Clone)]
struct DesktopLogsDir(PathBuf);

#[tauri::command]
fn open_logs_directory(logs_dir: tauri::State<'_, DesktopLogsDir>) -> Result<(), String> {
    let path = &logs_dir.0;
    if !path.exists() {
        let _ = std::fs::create_dir_all(path);
    }
    #[cfg(windows)]
    {
        Command::new("explorer")
            .arg(path)
            .spawn()
            .map_err(|e| e.to_string())?;
        Ok(())
    }
    #[cfg(target_os = "macos")]
    {
        Command::new("open")
            .arg(path)
            .spawn()
            .map_err(|e| e.to_string())?;
        Ok(())
    }
    #[cfg(all(not(windows), not(target_os = "macos")))]
    {
        Command::new("xdg-open")
            .arg(path)
            .spawn()
            .map_err(|e| e.to_string())?;
        Ok(())
    }
}

#[cfg(debug_assertions)]
fn project_root() -> Result<PathBuf, Error> {
    let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let root = env::var_os("NOUSETSU_PROJECT_DIR")
        .map(PathBuf::from)
        .unwrap_or_else(|| {
            manifest_dir
                .parent()
                .unwrap_or(manifest_dir.as_path())
                .to_path_buf()
        });

    if !root.join("src/nousetsu/cli/app.py").is_file() {
        return Err(Error::new(
            ErrorKind::NotFound,
            format!(
                "NouSetsu backend source was not found at {}. Set NOUSETSU_PROJECT_DIR to the repository root.",
                root.display()
            ),
        ));
    }

    Ok(root)
}

#[derive(Debug, PartialEq, Eq)]
enum BackendProbe {
    Ready,
    Starting,
    Incompatible(String),
}

fn probe_legacy_sync_state(address: &SocketAddr) -> bool {
    let Ok(mut stream) = TcpStream::connect_timeout(address, Duration::from_millis(500)) else {
        return false;
    };
    let _ = stream.set_read_timeout(Some(Duration::from_millis(1500)));
    let request =
        format!("GET /api/sync-state HTTP/1.1\r\nHost: {address}\r\nConnection: close\r\n\r\n");
    if stream.write_all(request.as_bytes()).is_err() {
        return false;
    }

    let mut response = String::new();
    BufReader::new(stream).read_line(&mut response).is_ok()
        && response.split_whitespace().nth(1) == Some("200")
}

fn probe_backend_status(address: &SocketAddr, expected_version: &str) -> BackendProbe {
    let Ok(mut stream) = TcpStream::connect_timeout(address, Duration::from_millis(500)) else {
        return BackendProbe::Starting;
    };
    let _ = stream.set_read_timeout(Some(Duration::from_millis(2000)));
    let request =
        format!("GET /api/desktop-info HTTP/1.1\r\nHost: {address}\r\nConnection: close\r\n\r\n");
    if stream.write_all(request.as_bytes()).is_err() {
        return BackendProbe::Starting;
    }

    let mut response = Vec::new();
    let mut reader = BufReader::new(stream);
    let mut buf = [0u8; 1024];
    loop {
        match reader.read(&mut buf) {
            Ok(0) => break,
            Ok(n) => {
                response.extend_from_slice(&buf[..n]);
                if response.len() > 16384 {
                    break;
                }
            }
            Err(ref e) if e.kind() == ErrorKind::TimedOut || e.kind() == ErrorKind::WouldBlock => {
                return BackendProbe::Starting;
            }
            Err(_) => return BackendProbe::Starting,
        }
    }

    let Ok(response_str) = std::str::from_utf8(&response) else {
        return BackendProbe::Incompatible("Non-UTF8 response from port".to_string());
    };

    let Some((headers, body)) = response_str.split_once("\r\n\r\n") else {
        return BackendProbe::Starting;
    };

    let status_code = headers
        .lines()
        .next()
        .and_then(|status| status.split_whitespace().nth(1));

    match status_code {
        Some("200") => {
            if let Ok(payload) = serde_json::from_str::<serde_json::Value>(body.trim()) {
                if let Some(version) = payload.get("version").and_then(|v| v.as_str()) {
                    if version == expected_version {
                        BackendProbe::Ready
                    } else {
                        BackendProbe::Incompatible(format!(
                            "Version mismatch: found '{version}', expected '{expected_version}'"
                        ))
                    }
                } else {
                    BackendProbe::Incompatible(
                        "Missing 'version' key in /api/desktop-info payload".to_string(),
                    )
                }
            } else {
                BackendProbe::Incompatible("Invalid JSON body from /api/desktop-info".to_string())
            }
        }
        Some("404") => {
            if probe_legacy_sync_state(address) {
                BackendProbe::Incompatible(
                    "Legacy NouSetsu backend detected without /api/desktop-info (pre-0.5.1)"
                        .to_string(),
                )
            } else {
                BackendProbe::Incompatible(
                    "Received 404 from unknown service running on backend port".to_string(),
                )
            }
        }
        Some("500") | Some("502") | Some("503") => BackendProbe::Starting,
        _ => BackendProbe::Starting,
    }
}

fn backend_version_matches(address: &SocketAddr, expected_version: &str) -> bool {
    matches!(
        probe_backend_status(address, expected_version),
        BackendProbe::Ready
    )
}

fn backend_is_ready() -> bool {
    let backend_address = SocketAddr::from(([127, 0, 0, 1], BACKEND_PORT));
    !matches!(
        probe_backend_status(&backend_address, env!("CARGO_PKG_VERSION")),
        BackendProbe::Starting
    )
}

#[cfg_attr(debug_assertions, allow(dead_code))]
fn seed_env_file(template: &Path, local_env: &Path) -> Result<(), Error> {
    if local_env.exists() {
        return Ok(());
    }

    let mut source = File::open(template).map_err(|error| {
        Error::new(
            error.kind(),
            format!(
                "Could not open bundled environment template {}: {error}",
                template.display()
            ),
        )
    })?;
    if let Some(parent) = local_env.parent() {
        std::fs::create_dir_all(parent)?;
    }
    let mut destination = match OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(local_env)
    {
        Ok(file) => file,
        Err(error) if error.kind() == ErrorKind::AlreadyExists => return Ok(()),
        Err(error) => {
            return Err(Error::new(
                error.kind(),
                format!(
                    "Could not create local environment file {}: {error}",
                    local_env.display()
                ),
            ));
        }
    };

    let copy_result = std::io::copy(&mut source, &mut destination)
        .and_then(|_| destination.flush())
        .and_then(|_| destination.sync_all());
    if let Err(error) = copy_result {
        drop(destination);
        let _ = std::fs::remove_file(local_env);
        return Err(Error::new(
            error.kind(),
            format!(
                "Could not seed local environment file {}: {error}",
                local_env.display()
            ),
        ));
    }

    Ok(())
}

#[cfg(not(debug_assertions))]
fn prepare_projects_dir(
    install_dir: &std::path::Path,
    app_data_dir: &std::path::Path,
) -> Result<PathBuf, Error> {
    let install_projects = install_dir.join("project");
    if std::fs::create_dir_all(&install_projects).is_ok() {
        let probe_path =
            install_projects.join(format!(".nousetsu-write-test-{}", std::process::id()));
        if let Ok(probe) = std::fs::OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(&probe_path)
        {
            drop(probe);
            let _ = std::fs::remove_file(probe_path);
            return Ok(install_projects);
        }
    }

    let app_data_projects = app_data_dir.join("project");
    std::fs::create_dir_all(&app_data_projects)?;
    Ok(app_data_projects)
}

#[cfg_attr(debug_assertions, allow(dead_code))]
fn prepare_logs_dir(
    install_dir: &std::path::Path,
    app_data_dir: &std::path::Path,
) -> Result<PathBuf, Error> {
    let install_logs = install_dir.join("logs");
    if std::fs::create_dir_all(&install_logs).is_ok() {
        let probe_path =
            install_logs.join(format!(".nousetsu-log-probe-{}", std::process::id()));
        if let Ok(probe) = std::fs::OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(&probe_path)
        {
            drop(probe);
            let _ = std::fs::remove_file(probe_path);
            return Ok(install_logs);
        }
    }

    let app_data_logs = app_data_dir.join("logs");
    std::fs::create_dir_all(&app_data_logs)?;
    Ok(app_data_logs)
}

fn current_utc_timestamp() -> String {
    use std::time::{SystemTime, UNIX_EPOCH};
    let secs = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs();
    let sec = secs % 60;
    let min = (secs / 60) % 60;
    let hour = (secs / 3600) % 24;
    let mut days = secs / 86400;

    let mut year = 1970;
    loop {
        let leap = (year % 4 == 0 && year % 100 != 0) || (year % 400 == 0);
        let days_in_year = if leap { 366 } else { 365 };
        if days < days_in_year {
            break;
        }
        days -= days_in_year;
        year += 1;
    }
    let leap = (year % 4 == 0 && year % 100 != 0) || (year % 400 == 0);
    let days_in_months = [
        31,
        if leap { 29 } else { 28 },
        31, 30, 31, 30, 31, 31, 30, 31, 30, 31,
    ];
    let mut month = 1;
    for &dim in &days_in_months {
        if days < dim {
            break;
        }
        days -= dim;
        month += 1;
    }
    let day = days + 1;
    format!("{year:04}-{month:02}-{day:02} {hour:02}:{min:02}:{sec:02}")
}

fn write_desktop_log(logs_dir: &Path, level: &str, message: &str) {
    let log_path = logs_dir.join("desktop.log");
    let ts = current_utc_timestamp();
    let line = format!("[{ts} UTC] [{level}] {message}\n");
    if let Ok(mut file) = OpenOptions::new().create(true).append(true).open(log_path) {
        let _ = file.write_all(line.as_bytes());
    }
}

fn start_backend(_app: &tauri::App) -> Result<(Option<Child>, PathBuf), Error> {
    let backend_address = SocketAddr::from(([127, 0, 0, 1], BACKEND_PORT));
    let expected_version = env!("CARGO_PKG_VERSION");
    let port = BACKEND_PORT.to_string();
    let mut command;
    let working_dir;
    let default_projects_dir: Option<PathBuf>;
    let logs_dir: PathBuf;

    #[cfg(debug_assertions)]
    {
        let root = project_root()?;
        let venv_python = if cfg!(windows) {
            root.join(".venv/Scripts/python.exe")
        } else {
            root.join(".venv/bin/python")
        };
        let python = env::var_os("NOUSETSU_PYTHON")
            .map(PathBuf::from)
            .filter(|path| path.is_file())
            .or_else(|| venv_python.is_file().then_some(venv_python));

        command = if let Some(python) = python {
            Command::new(python)
        } else if cfg!(windows) {
            Command::new("python")
        } else {
            Command::new("python3")
        };
        command.args([
            "-c",
            "from nousetsu.cli.app import main; main()",
            "web",
            "--host",
            BACKEND_HOST,
            "--port",
            port.as_str(),
            "--no-open-browser",
        ]);

        let existing_python_path = env::var_os("PYTHONPATH").unwrap_or_default();
        let python_paths =
            std::iter::once(root.join("src")).chain(env::split_paths(&existing_python_path));
        if let Ok(joined_paths) = env::join_paths(python_paths) {
            command.env("PYTHONPATH", joined_paths);
        }
        command.env("NOUSETSU_INSTALL_DIR", &root);
        working_dir = root;
        default_projects_dir = None;
        logs_dir = working_dir.join("logs");
        let _ = std::fs::create_dir_all(&logs_dir);
    }

    #[cfg(not(debug_assertions))]
    {
        let resource_dir = _app
            .path()
            .resource_dir()
            .map_err(|error| Error::other(format!("Could not locate app resources: {error}")))?;
        let backend_name = if cfg!(windows) {
            "nousetsu-backend.exe"
        } else {
            "nousetsu-backend"
        };
        let backend_path = resource_dir
            .join("binaries")
            .join("nousetsu-backend")
            .join(backend_name);
        if !backend_path.is_file() {
            return Err(Error::new(
                ErrorKind::NotFound,
                format!(
                    "Bundled Python backend is missing: {}",
                    backend_path.display()
                ),
            ));
        }

        command = Command::new(backend_path);
        command.args(["--host", BACKEND_HOST, "--port", port.as_str()]);
        working_dir = _app.path().app_data_dir().map_err(|error| {
            Error::other(format!("Could not locate app data directory: {error}"))
        })?;
        std::fs::create_dir_all(&working_dir)?;
        seed_env_file(
            &resource_dir.join("defaults").join(".env.example"),
            &working_dir.join(".env"),
        )?;
        let install_dir = std::env::current_exe()?
            .parent()
            .map(PathBuf::from)
            .ok_or_else(|| Error::other("Could not determine the application install directory"))?;
        default_projects_dir = Some(prepare_projects_dir(&install_dir, &working_dir)?);
        logs_dir = prepare_logs_dir(&install_dir, &working_dir)?;
        command.env("NOUSETSU_INSTALL_DIR", &install_dir);
    }

    write_desktop_log(
        &logs_dir,
        "INFO",
        &format!("NouSetsu desktop v{expected_version} initializing"),
    );
    write_desktop_log(
        &logs_dir,
        "INFO",
        &format!("Logs directory: {}", logs_dir.display()),
    );

    match probe_backend_status(&backend_address, expected_version) {
        BackendProbe::Ready => {
            write_desktop_log(
                &logs_dir,
                "INFO",
                &format!("Reusing existing compatible backend on {backend_address}"),
            );
            return Ok((None, logs_dir));
        }
        BackendProbe::Incompatible(reason) => {
            write_desktop_log(
                &logs_dir,
                "ERROR",
                &format!("Incompatible backend detected on {backend_address}: {reason}"),
            );
            return Err(Error::other(format!(
                "An incompatible NouSetsu backend is already running at {backend_address}: {reason}. Close existing NouSetsu Web Studio or desktop processes and restart the desktop app."
            )));
        }
        BackendProbe::Starting => {
            // Port is free or not yet responding; proceed to spawn backend child process.
        }
    }

    let backend_log_path = logs_dir.join("backend.log");
    let stdout_file = OpenOptions::new()
        .create(true)
        .append(true)
        .open(&backend_log_path);
    let stderr_file = OpenOptions::new()
        .create(true)
        .append(true)
        .open(&backend_log_path);

    if let (Ok(out), Ok(err)) = (stdout_file, stderr_file) {
        command.stdout(Stdio::from(out));
        command.stderr(Stdio::from(err));
    } else {
        command.stdout(Stdio::null());
        command.stderr(Stdio::null());
    }

    command
        .current_dir(&working_dir)
        .env("HOST", BACKEND_HOST)
        .env("NOUSETSU_ENV_FILE", working_dir.join(".env"))
        .env("NOUSETSU_APP_DATA_DIR", &working_dir)
        .env("NOUSETSU_LOGS_DIR", &logs_dir)
        .env("NOUSETSU_DESKTOP_VERSION", env!("CARGO_PKG_VERSION"));
    if let Some(projects_dir) = default_projects_dir {
        command.env("NOUSETSU_DEFAULT_PROJECTS_DIR", projects_dir);
    }

    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        command.creation_flags(0x08000000);
    }

    let mut child = command.spawn().map_err(|error| {
        write_desktop_log(
            &logs_dir,
            "ERROR",
            &format!("Could not start the NouSetsu backend: {error}"),
        );
        Error::new(
            error.kind(),
            format!("Could not start the NouSetsu backend: {error}"),
        )
    })?;

    write_desktop_log(
        &logs_dir,
        "INFO",
        &format!("Backend child process spawned with PID {}", child.id()),
    );

    let deadline = Instant::now() + Duration::from_secs(90);
    while Instant::now() < deadline {
        match probe_backend_status(&backend_address, expected_version) {
            BackendProbe::Ready => {
                write_desktop_log(
                    &logs_dir,
                    "INFO",
                    "Backend became ready and verified successfully.",
                );
                return Ok((Some(child), logs_dir));
            }
            BackendProbe::Incompatible(reason) => {
                let _ = child.kill();
                let _ = child.wait();
                write_desktop_log(
                    &logs_dir,
                    "ERROR",
                    &format!("Incompatible backend responded during startup wait loop: {reason}"),
                );
                return Err(Error::other(format!(
                    "An incompatible NouSetsu backend responded at {backend_address}: {reason}. Close it and restart the desktop app."
                )));
            }
            BackendProbe::Starting => {
                // Backend is still initializing or connection timed out; continue waiting.
            }
        }

        if let Some(status) = child.try_wait()? {
            write_desktop_log(
                &logs_dir,
                "ERROR",
                &format!("The NouSetsu backend exited before becoming ready ({status})."),
            );
            return Err(Error::other(format!(
                "The NouSetsu backend exited before becoming ready ({status})."
            )));
        }
        thread::sleep(Duration::from_millis(200));
    }

    let _ = child.kill();
    let _ = child.wait();
    write_desktop_log(
        &logs_dir,
        "ERROR",
        "The NouSetsu backend did not become ready within 90 seconds.",
    );
    Err(Error::new(
        ErrorKind::TimedOut,
        "The NouSetsu backend did not become ready within 90 seconds.",
    ))
}

fn main() {
    let app = tauri::Builder::default()
        .manage(BackendProcess::default())
        .invoke_handler(tauri::generate_handler![
            stop_backend_before_update,
            open_logs_directory
        ])
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_process::init())
        .setup(|app| {
            let (process, logs_dir) = start_backend(app)?;
            app.manage(DesktopLogsDir(logs_dir));
            *app.state::<BackendProcess>()
                .0
                .lock()
                .map_err(|_| Error::other("Backend process state was poisoned"))? = process;

            #[cfg(not(debug_assertions))]
            if let Some(window) = app.get_webview_window("main") {
                window.navigate(BACKEND_URL.parse()?)?;
            }

            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building Nousetsu application");

    app.run(|app_handle, event| {
        if matches!(event, tauri::RunEvent::Exit) {
            if let Some(logs_state) = app_handle.try_state::<DesktopLogsDir>() {
                write_desktop_log(&logs_state.0, "INFO", "Desktop application exiting.");
            }
            let _ = app_handle.state::<BackendProcess>().stop();
        }
    });
}

#[cfg(test)]
mod tests {
    use super::{backend_version_matches, probe_backend_status, seed_env_file, BackendProbe};
    use std::{
        fs,
        io::{BufRead, BufReader, Write},
        net::{SocketAddr, TcpListener},
        path::PathBuf,
        thread,
        time::{SystemTime, UNIX_EPOCH},
    };

    fn temporary_directory() -> PathBuf {
        let nonce = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("system clock should be after the Unix epoch")
            .as_nanos();
        let path =
            std::env::temp_dir().join(format!("nousetsu-env-seed-{}-{nonce}", std::process::id()));
        fs::create_dir_all(&path).expect("temporary directory should be created");
        path
    }

    #[test]
    fn seeds_missing_env_and_preserves_existing_env() {
        let directory = temporary_directory();
        let template = directory.join(".env.example");
        let local_env = directory.join("user").join(".env");
        fs::write(&template, "DEFAULT_MODEL=example-model\n").expect("template should be written");

        seed_env_file(&template, &local_env).expect("missing local env should be seeded");
        assert_eq!(
            fs::read_to_string(&local_env).expect("seeded env should be readable"),
            "DEFAULT_MODEL=example-model\n"
        );

        fs::write(&local_env, "DEFAULT_MODEL=user-model\n").expect("local env should be updated");
        seed_env_file(&template, &local_env).expect("existing local env should be preserved");
        assert_eq!(
            fs::read_to_string(&local_env).expect("local env should be readable"),
            "DEFAULT_MODEL=user-model\n"
        );

        fs::remove_dir_all(directory).expect("temporary directory should be removed");
    }

    #[test]
    fn does_not_reuse_backend_from_an_older_desktop_release() {
        let listener = TcpListener::bind(("127.0.0.1", 0)).expect("test listener should bind");
        let address: SocketAddr = listener.local_addr().expect("address should be available");
        let server = thread::spawn(move || {
            let (mut stream, _) = listener.accept().expect("request should connect");
            let mut request_line = String::new();
            BufReader::new(&stream)
                .read_line(&mut request_line)
                .expect("request should be readable");
            assert!(request_line.starts_with("GET /api/desktop-info "));
            let body = r#"{"version":"0.4.9"}"#;
            write!(
                stream,
                "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{}",
                body.len(),
                body
            )
            .expect("version response should be written");
        });

        assert!(!backend_version_matches(&address, "0.5.1"));
        server.join().expect("test server should finish");
    }

    #[test]
    fn probe_status_matches_compatible_backend() {
        let listener = TcpListener::bind(("127.0.0.1", 0)).expect("test listener should bind");
        let address: SocketAddr = listener.local_addr().expect("address should be available");
        let server = thread::spawn(move || {
            let (mut stream, _) = listener.accept().expect("request should connect");
            let mut request_line = String::new();
            BufReader::new(&stream)
                .read_line(&mut request_line)
                .expect("request should be readable");
            assert!(request_line.starts_with("GET /api/desktop-info "));
            let body = r#"{"version":"0.5.1"}"#;
            write!(
                stream,
                "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{}",
                body.len(),
                body
            )
            .expect("version response should be written");
        });

        assert_eq!(
            probe_backend_status(&address, "0.5.1"),
            BackendProbe::Ready
        );
        server.join().expect("test server should finish");
    }

    #[test]
    fn probe_status_rejects_version_mismatch() {
        let listener = TcpListener::bind(("127.0.0.1", 0)).expect("test listener should bind");
        let address: SocketAddr = listener.local_addr().expect("address should be available");
        let server = thread::spawn(move || {
            let (mut stream, _) = listener.accept().expect("request should connect");
            let mut request_line = String::new();
            BufReader::new(&stream)
                .read_line(&mut request_line)
                .expect("request should be readable");
            assert!(request_line.starts_with("GET /api/desktop-info "));
            let body = r#"{"version":"0.4.9"}"#;
            write!(
                stream,
                "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{}",
                body.len(),
                body
            )
            .expect("version response should be written");
        });

        let status = probe_backend_status(&address, "0.5.1");
        assert!(
            matches!(status, BackendProbe::Incompatible(ref msg) if msg.contains("Version mismatch")),
            "Expected Incompatible with version mismatch, got {:?}",
            status
        );
        server.join().expect("test server should finish");
    }

    #[test]
    fn probe_status_detects_legacy_backend_via_sync_state() {
        let listener = TcpListener::bind(("127.0.0.1", 0)).expect("test listener should bind");
        let address: SocketAddr = listener.local_addr().expect("address should be available");
        let server = thread::spawn(move || {
            // First probe: GET /api/desktop-info returns 404
            let (mut stream1, _) = listener.accept().expect("first request should connect");
            let mut request_line1 = String::new();
            BufReader::new(&stream1)
                .read_line(&mut request_line1)
                .expect("first request line should be readable");
            assert!(request_line1.starts_with("GET /api/desktop-info "));
            write!(
                stream1,
                "HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
            )
            .expect("404 response should be written");
            drop(stream1);

            // Second probe (fallback check): GET /api/sync-state returns 200
            let (mut stream2, _) = listener.accept().expect("second request should connect");
            let mut request_line2 = String::new();
            BufReader::new(&stream2)
                .read_line(&mut request_line2)
                .expect("second request line should be readable");
            assert!(request_line2.starts_with("GET /api/sync-state "));
            write!(
                stream2,
                "HTTP/1.1 200 OK\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
            )
            .expect("200 sync-state response should be written");
        });

        let status = probe_backend_status(&address, "0.5.1");
        assert!(
            matches!(status, BackendProbe::Incompatible(ref msg) if msg.contains("Legacy NouSetsu backend")),
            "Expected legacy backend detection, got {:?}",
            status
        );
        server.join().expect("test server should finish");
    }

    #[test]
    fn probe_status_returns_starting_on_closed_port() {
        let listener = TcpListener::bind(("127.0.0.1", 0)).expect("test listener should bind");
        let address: SocketAddr = listener.local_addr().expect("address should be available");
        drop(listener);

        assert_eq!(
            probe_backend_status(&address, "0.5.1"),
            BackendProbe::Starting
        );
    }
}
