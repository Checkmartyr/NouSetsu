"""Standalone backend entry point used by the NouSetsu Tauri desktop app."""

import argparse
import json
import os
import shutil
import sys
from importlib import import_module
from typing import Any
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def _frontend_dist() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS")) / "web" / "dist"
    return Path(__file__).resolve().parents[2] / "web" / "dist"


def _run_scraper_worker(args: list[str]) -> None:
    """Run the Novel-Scraper bundled into this backend sidecar."""
    if not args:
        raise SystemExit("Missing scraper worker operation.")

    app_data_dir = os.environ.get("NOUSETSU_APP_DATA_DIR")
    if not app_data_dir:
        raise RuntimeError("NOUSETSU_APP_DATA_DIR must be set for the bundled scraper worker.")

    scraper_data_dir = Path(app_data_dir).resolve() / "scraper"
    binary_dir = scraper_data_dir / "bin"
    recipes_dir = scraper_data_dir / "recipes"
    logs_dir = scraper_data_dir / "logs"
    output_dir = scraper_data_dir / "novels"
    for directory in (binary_dir, recipes_dir, logs_dir, output_dir):
        directory.mkdir(parents=True, exist_ok=True)

    if getattr(sys, "frozen", False):
        bundled_recipes = Path(getattr(sys, "_MEIPASS")) / "scraper-data" / "recipes"
    else:
        bundled_recipes = Path(__file__).resolve().parents[2] / "modules" / "novel_scraper" / "src" / "recipes"
        sys.path.insert(0, str(bundled_recipes.parent.parent))

    if bundled_recipes.is_dir():
        for recipe in bundled_recipes.glob("*.json"):
            target = recipes_dir / recipe.name
            if not target.exists():
                shutil.copy2(recipe, target)

    scraper_config: Any = import_module("src.config")

    scraper_config.BIN_DIR = binary_dir
    scraper_config.OUTPUT_DIR = output_dir
    scraper_config.LOGS_DIR = logs_dir
    scraper_config.RECIPES_DIR = recipes_dir
    scraper_config.OBSCURA_BIN_PATH = ""

    operation, *operation_args = args
    if operation == "provider-info":
        from src.agent.llm import LLMClient
        from nousetsu.scraper.llm_config import resolve_scraper_llm_settings

        llm_client = LLMClient()
        settings = resolve_scraper_llm_settings()
        print(
            json.dumps(
                {
                    "model": llm_client.model,
                    "provider": settings.provider,
                    "fallback_model": settings.fallback_model,
                    "fallback_provider": settings.fallback_provider,
                    "available": llm_client.is_available,
                }
            )
        )
        return

    if operation == "romanize":
        if len(operation_args) != 1:
            raise SystemExit("Usage: nousetsu-backend --scraper-worker romanize <title>")
        romanize_text: Any = import_module("src.utils.romanizer").romanize_text

        print(romanize_text(operation_args[0]))
        return

    if operation not in {"inspect", "extract"}:
        raise SystemExit(f"Unsupported scraper worker operation: {operation}")

    scraper_main: Any = import_module("src.api_bridge").main

    sys.argv = [sys.argv[0], operation, *operation_args]
    scraper_main()


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "--scraper-worker":
        _run_scraper_worker(sys.argv[2:])
        return

    from nousetsu.utils.logging import setup_backend_file_logging
    setup_backend_file_logging()

    parser = argparse.ArgumentParser(description="NouSetsu desktop API backend")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=15474)
    args = parser.parse_args()

    from nousetsu.cli.web_server import run_web_server

    run_web_server(
        port=args.port,
        host=args.host,
        open_browser=False,
        dist_dir=_frontend_dist(),
    )


if __name__ == "__main__":
    main()
