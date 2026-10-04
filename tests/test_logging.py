"""Unit tests for NouSetsu persistent local file logging across backend, frontend, and desktop."""
import json
import logging
from pathlib import Path
import tempfile
from unittest.mock import patch

import pytest
from starlette.testclient import TestClient

from nousetsu.cli.web_server import create_app
from nousetsu.utils.logging import (
    append_frontend_log,
    get_logs_dir,
    get_logs_info,
    open_logs_folder,
    setup_backend_file_logging,
    _format_size,
)


def test_format_size():
    assert _format_size(500) == "500 B"
    assert _format_size(1024) == "1.0 KB"
    assert _format_size(2500) == "2.4 KB"
    assert _format_size(1024 * 1024 * 3) == "3.0 MB"


def test_get_logs_dir_respects_env(monkeypatch, tmp_path):
    custom_logs = tmp_path / "custom_logs"
    monkeypatch.setenv("NOUSETSU_LOGS_DIR", str(custom_logs))
    resolved = get_logs_dir()
    assert resolved == custom_logs
    assert resolved.exists()


def test_get_logs_dir_respects_install_dir(monkeypatch, tmp_path):
    monkeypatch.delenv("NOUSETSU_LOGS_DIR", raising=False)
    install_dir = tmp_path / "app_install"
    install_dir.mkdir(parents=True)
    monkeypatch.setenv("NOUSETSU_INSTALL_DIR", str(install_dir))

    resolved = get_logs_dir()
    assert resolved == install_dir / "logs"
    assert resolved.exists()


def test_setup_backend_file_logging_and_write(tmp_path):
    logs_dir = tmp_path / "test_logs"
    setup_backend_file_logging(logs_dir=logs_dir, log_level=logging.INFO)

    test_logger = logging.getLogger("test_module")
    test_logger.info("Hello backend persistent log!")

    log_file = logs_dir / "backend.log"
    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")
    assert "Hello backend persistent log!" in content
    assert "[INFO]" in content


def test_append_frontend_log(tmp_path):
    logs_dir = tmp_path / "test_frontend_logs"
    append_frontend_log(
        {
            "timestamp": "2026-10-04 12:00:00",
            "level": "ERROR",
            "source": "window.error",
            "message": "Uncaught TypeError: test error",
            "stack": "Error: test error\n    at index.js:1:1",
        },
        logs_dir=logs_dir,
    )

    frontend_log = logs_dir / "frontend.log"
    assert frontend_log.exists()
    content = frontend_log.read_text(encoding="utf-8")
    assert "[2026-10-04 12:00:00]" in content
    assert "[ERROR]" in content
    assert "[window.error]" in content
    assert "Uncaught TypeError: test error" in content
    assert "Stack: Error: test error" in content


def test_get_logs_info(tmp_path):
    logs_dir = tmp_path / "test_info_logs"
    logs_dir.mkdir(parents=True)

    info_before = get_logs_info(logs_dir=logs_dir)
    assert info_before["files"]["backend.log"]["exists"] is False
    assert info_before["files"]["frontend.log"]["exists"] is False
    assert info_before["files"]["desktop.log"]["exists"] is False

    (logs_dir / "backend.log").write_text("backend data" * 100, encoding="utf-8")
    (logs_dir / "desktop.log").write_text("desktop startup", encoding="utf-8")

    info_after = get_logs_info(logs_dir=logs_dir)
    assert info_after["files"]["backend.log"]["exists"] is True
    assert info_after["files"]["backend.log"]["size_bytes"] > 0
    assert info_after["files"]["desktop.log"]["exists"] is True
    assert info_after["files"]["frontend.log"]["exists"] is False


def test_open_logs_folder(tmp_path):
    logs_dir = tmp_path / "open_dir_test"
    with patch("os.startfile", create=True) as mock_startfile:
        res = open_logs_folder(logs_dir=logs_dir)
        assert res is True
        assert logs_dir.exists()


def test_fastapi_logging_endpoints(monkeypatch, tmp_path):
    logs_dir = tmp_path / "api_logs"
    monkeypatch.setenv("NOUSETSU_LOGS_DIR", str(logs_dir))

    app = create_app()
    client = TestClient(app)

    # 1. Post batch frontend logs
    post_res = client.post(
        "/api/logs/frontend",
        json={
            "logs": [
                {
                    "timestamp": "2026-10-04 12:30:00",
                    "level": "WARN",
                    "source": "console.warn",
                    "message": "Warning from test client",
                },
                {
                    "timestamp": "2026-10-04 12:30:01",
                    "level": "ERROR",
                    "source": "unhandledrejection",
                    "message": "Rejection from test client",
                },
            ]
        },
    )
    assert post_res.status_code == 200
    assert post_res.json()["status"] == "ok"
    assert post_res.json()["count"] == 2

    frontend_file = logs_dir / "frontend.log"
    assert frontend_file.exists()
    f_content = frontend_file.read_text(encoding="utf-8")
    assert "Warning from test client" in f_content
    assert "Rejection from test client" in f_content

    # 2. Get logs info
    info_res = client.get("/api/logs/info")
    assert info_res.status_code == 200
    info_data = info_res.json()
    assert info_data["logs_dir"] == str(logs_dir.resolve())
    assert info_data["files"]["frontend.log"]["exists"] is True

    # 3. Open logs folder
    with patch("nousetsu.utils.logging.open_logs_folder", return_value=True):
        open_res = client.post("/api/logs/open-folder")
        assert open_res.status_code == 200
        assert open_res.json()["success"] is True
