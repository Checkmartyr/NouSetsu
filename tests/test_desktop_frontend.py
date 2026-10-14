"""The frozen sidecar must serve the frontend produced by this build."""

import importlib.util
import io
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit

import pytest


@pytest.mark.parametrize("fault", [None, "html", "javascript", "stylesheet", "cache_policy", "missing_asset"])
def test_frozen_frontend_smoke_check(tmp_path, monkeypatch, fault):
    spec = importlib.util.spec_from_file_location(
        "build_sidecar", Path(__file__).resolve().parents[1] / "src-tauri" / "build_sidecar.py"
    )
    build = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build)
    monkeypatch.setattr(build, "FRONTEND_DIST", tmp_path)
    html = b'<script type="module" src="/assets/new.js"></script><link rel="stylesheet" href="/assets/new.css">'
    bodies = {"/index.html": html, "/assets/new.js": b"new javascript", "/assets/new.css": b"new stylesheet"}
    for name, content in bodies.items():
        target = tmp_path / name.lstrip("/")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    if fault in {"html", "javascript", "stylesheet"}:
        target = {"html": "/index.html", "javascript": "/assets/new.js", "stylesheet": "/assets/new.css"}[fault]
        bodies[target] = b"stale build"
    requests = []

    def fetch(url, timeout):
        path = urlsplit(url).path
        requests.append(path)
        if fault == "missing_asset" and path == "/assets/new.js":
            raise HTTPError(url, 404, "Not found", {}, None)
        response = io.BytesIO(bodies.get(path, bodies["/index.html"]))
        response.headers = {"Cache-Control": "no-store"} if fault != "cache_policy" else {}
        return response

    monkeypatch.setattr(build.urllib.request, "urlopen", fetch)
    if fault:
        with pytest.raises(RuntimeError, match="[Ff]rontend"):
            build._smoke_test_frontend("http://127.0.0.1:15474")
    else:
        build._smoke_test_frontend("http://127.0.0.1:15474")
        assert requests == ["/", "/reader", "/assets/new.js", "/assets/new.css"]
