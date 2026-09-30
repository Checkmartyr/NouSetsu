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

fn backend_is_ready() -> bool {
    let address = format!("{BACKEND_HOST}:{BACKEND_PORT}");
    let Ok(mut stream) = TcpStream::connect_timeout(
        &address.parse().expect("valid backend socket address"),
        Duration::from_millis(250),
    ) else {
        return false;
    };
    let _ = stream.set_read_timeout(Some(Duration::from_millis(500)));
    let request =
        format!("GET /api/sync-state HTTP/1.1\r\nHost: {address}\r\nConnection: close\r\n\r\n");
    if stream.write_all(request.as_bytes()).is_err() {
        return false;
    }

    let mut response = String::new();
    BufReader::new(stream).read_line(&mut response).is_ok()
        && response.split_whitespace().nth(1) == Some("200")
}

fn backend_version_matches(address: &SocketAddr, expected_version: &str) -> bool {
    let Ok(mut stream) = TcpStream::connect_timeout(address, Duration::from_millis(250)) else {
        return false;
    };
    let _ = stream.set_read_timeout(Some(Duration::from_millis(500)));
    let request =
        format!("GET /api/desktop-info HTTP/1.1\r\nHost: {address}\r\nConnection: close\r\n\r\n");
    if stream.write_all(request.as_bytes()).is_err() {
        return false;
    }

    let mut response = String::new();
    if BufReader::new(stream)
        .read_to_string(&mut response)
        .is_err()
    {
        return false;
    }
    let Some((headers, body)) = response.split_once("\r\n\r\n") else {
        return false;
    };
    let is_success = headers
        .lines()
        .next()
        .and_then(|status| status.split_whitespace().nth(1))
        == Some("200");
    if !is_success {
        return false;
    }

    serde_json::from_str::<serde_json::Value>(body)
        .ok()
        .and_then(|payload| payload.get("version")?.as_str().map(str::to_owned))
        .as_deref()
        == Some(expected_version)
}

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

fn start_backend(_app: &tauri::App) -> Result<Option<Child>, Error> {
    let backend_address = SocketAddr::from(([127, 0, 0, 1], BACKEND_PORT));
    let expected_version = env!("CARGO_PKG_VERSION");
    if backend_version_matches(&backend_address, expected_version) {
        return Ok(None);
    }
    if backend_is_ready() {
        return Err(Error::other(format!(
            "An incompatible NouSetsu backend is already running at {backend_address}. Close existing NouSetsu Web Studio or desktop processes and restart the desktop app."
        )));
    }

    let port = BACKEND_PORT.to_string();
    let mut command;
    let working_dir;
    let default_projects_dir: Option<PathBuf>;

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
        working_dir = root;
        default_projects_dir = None;
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
    }

    command
        .current_dir(&working_dir)
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .env("HOST", BACKEND_HOST)
        .env("NOUSETSU_ENV_FILE", working_dir.join(".env"))
        .env("NOUSETSU_APP_DATA_DIR", &working_dir)
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
        Error::new(
            error.kind(),
            format!("Could not start the NouSetsu backend: {error}"),
        )
    })?;

    let deadline = Instant::now() + Duration::from_secs(90);
    while Instant::now() < deadline {
        if backend_version_matches(&backend_address, expected_version) {
            return Ok(Some(child));
        }
        if backend_is_ready() {
            let _ = child.kill();
            let _ = child.wait();
            return Err(Error::other(format!(
                "An incompatible NouSetsu backend is responding at {backend_address}. Close it and restart the desktop app."
            )));
        }
        if let Some(status) = child.try_wait()? {
            return Err(Error::other(format!(
                "The NouSetsu backend exited before becoming ready ({status})."
            )));
        }
        thread::sleep(Duration::from_millis(100));
    }

    let _ = child.kill();
    let _ = child.wait();
    Err(Error::new(
        ErrorKind::TimedOut,
        "The NouSetsu backend did not become ready within 90 seconds.",
    ))
}

fn main() {
    let app = tauri::Builder::default()
        .manage(BackendProcess::default())
        .invoke_handler(tauri::generate_handler![stop_backend_before_update])
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_process::init())
        .setup(|app| {
            let process = start_backend(app)?;
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
            let _ = app_handle.state::<BackendProcess>().stop();
        }
    });
}

#[cfg(test)]
mod tests {
    use super::{backend_version_matches, seed_env_file};
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
}
