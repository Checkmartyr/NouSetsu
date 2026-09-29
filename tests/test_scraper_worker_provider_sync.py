"""Integration coverage for provider setup in the desktop scraper worker."""

import json
import os
from pathlib import Path
import subprocess
import sys


def test_desktop_scraper_worker_keeps_src_namespace_and_loads_routing(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[1]
    backend_entry = repo_root / "src" / "nousetsu" / "desktop_backend.py"
    scraper_root = repo_root / "modules" / "novel_scraper"
    environment = os.environ.copy()
    environment.update(
        {
            "NOUSETSU_APP_DATA_DIR": str(tmp_path / "app-data"),
            "NOUSETSU_ENV_FILE": str(tmp_path / "settings.env"),
            "PYTHON_DOTENV_DISABLED": "1",
            "NOVEL_SCRAPER_MODEL": "openrouter:worker-test-model",
            "NOVEL_FALLBACK_MODEL": "openai:worker-fallback-model",
            "PYTHONPATH": os.pathsep.join(
                [str(repo_root / "src"), str(scraper_root), environment.get("PYTHONPATH", "")]
            ),
        }
    )
    for key in (
        "DEFAULT_MODEL",
        "NOVEL_MODEL",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "OPENAI_API_KEY",
        "OPENROUTER_API_KEY",
    ):
        environment.pop(key, None)

    process = subprocess.run(
        [sys.executable, str(backend_entry), "--scraper-worker", "provider-info"],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout) == {
        "model": "openrouter:worker-test-model",
        "provider": "Unconfigured",
        "fallback_model": "openai:worker-fallback-model",
        "fallback_provider": "Unconfigured",
        "available": False,
    }
