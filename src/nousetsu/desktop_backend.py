"""Standalone backend entry point used by the NouSetsu Tauri desktop app."""

import argparse
import sys
from pathlib import Path


def _frontend_dist() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS")) / "web" / "dist"
    return Path(__file__).resolve().parents[2] / "web" / "dist"


def main() -> None:
    parser = argparse.ArgumentParser(description="NouSetsu desktop API backend")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5174)
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
