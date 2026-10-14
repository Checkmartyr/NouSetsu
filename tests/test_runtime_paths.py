from pathlib import Path
import nousetsu.utils.env as environment
import nousetsu.utils.runtime_paths as paths


def test_installed_package_uses_user_storage_and_preserves_explicit_env(tmp_path, monkeypatch):
    monkeypatch.setattr(environment, "__file__", str(tmp_path / "site-packages/nousetsu/utils/env.py"))
    monkeypatch.setattr(paths, "user_config_dir", lambda: tmp_path / "user-config")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("NOUSETSU_ENV_FILE")
    assert environment.resolve_env_file() == tmp_path / "user-config/.env"
    explicit = tmp_path / "explicit.env"
    monkeypatch.setenv("NOUSETSU_ENV_FILE", str(explicit))
    assert environment.resolve_env_file() == explicit
    monkeypatch.delenv("NOUSETSU_ENV_FILE")
    (tmp_path / ".env").write_text("TARGET_LANG=Thai\n")
    assert environment.resolve_env_file() == tmp_path / ".env"


def test_packaged_frontend_is_found_without_checkout_or_node(tmp_path, monkeypatch):
    module = tmp_path / "nousetsu/utils/runtime_paths.py"
    module.parent.mkdir(parents=True)
    monkeypatch.setattr(paths, "__file__", str(module))
    target = tmp_path / "nousetsu/data/web"
    target.mkdir(parents=True)
    (target / "index.html").write_text("setup")
    assert paths.frontend_dist() == target


def test_setup_uses_redirected_documents_location(tmp_path, monkeypatch):
    import nousetsu.setup as setup
    from nousetsu.utils.env import ENV_CONFIG_KEYS, ENV_SECRET_KEYS
    for key in (*ENV_CONFIG_KEYS, *ENV_SECRET_KEYS):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(setup, "documents_dir", lambda: tmp_path / "OneDrive/เอกสาร")
    assert Path(setup.get_setup()["values"]["NOVEL_PROJECTS_DIR"]) == tmp_path / "OneDrive/เอกสาร/NouSetsu"
