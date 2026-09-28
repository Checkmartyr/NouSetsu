// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

#[cfg(debug_assertions)]
use std::env;
use std::{
    fs::{File, OpenOptions},
    io::{BufRead, BufReader, Error, ErrorKind, Write},
    net::TcpStream,
    path::{Path, PathBuf},
    process::{Child, Command, Stdio},
    sync::Mutex,
    thread,
    time::{Duration, Instant},
};
use tauri::Manager;

const BACKEND_HOST: &str = "127.0.0.1";
const BACKEND_PORT: u16 = 5174;
#[cfg(not(debug_assertions))]
const BACKEND_URL: &str = "http://127.0.0.1:5174";

#[derive(Default)]
struct BackendProcess(Mutex<Option<Child>>);

impl BackendProcess {
    fn stop(&self) {
        if let Ok(mut process) = self.0.lock() {
            if let Some(mut child) = process.take() {
                let _ = child.kill();
                let _ = child.wait();
            }
        }
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
    if backend_is_ready() {
        return Ok(None);
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
        if backend_is_ready() {
            return Ok(Some(child));
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
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
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
            app_handle.state::<BackendProcess>().stop();
        }
    });
}

#[cfg(test)]
mod tests {
    use super::seed_env_file;
    use std::{
        fs,
        path::PathBuf,
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
}
