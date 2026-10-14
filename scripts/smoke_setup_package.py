"""Run against an installed wheel, with no Node on PATH and isolated user data."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request


def main():
    python = str(Path(sys.argv[1]).resolve())
    with tempfile.TemporaryDirectory(prefix="nousetsu-package-setup-") as temporary:
        root = Path(temporary)
        env = {key: value for key, value in os.environ.items() if not key.startswith(("NOVEL_", "NOUSETSU_")) and key not in {"GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY", "CUSTOM_API_KEY", "DEFAULT_MODEL", "SOURCE_LANG", "TARGET_LANG"}}
        env.update(PATH="", PYTHONPATH="", APPDATA=str(root / "app-data"), XDG_CONFIG_HOME=str(root / "config"), NOVEL_REGISTRY_DIR=str(root / "registry"))
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        base = f"http://127.0.0.1:{port}"
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        process = subprocess.Popen([python, "-m", "nousetsu.cli.app", "setup", "--no-open-browser", "--port", str(port)], cwd=root, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=flags)
        try:
            for _ in range(100):
                try:
                    with urllib.request.urlopen(base + "/api/setup", timeout=1) as response:
                        state, etag = json.load(response), response.headers["ETag"]
                    break
                except OSError:
                    if process.poll() is not None:
                        raise RuntimeError(process.communicate()[1].decode(errors="replace"))
                    time.sleep(.2)
            else:
                raise RuntimeError("Installed wheel did not start setup")
            assert not state["completed"] and state["readiness"] == "not_connected"
            assert "site-packages" not in state["environment"]["env_file_path"]
            assert str(root) in state["environment"]["env_file_path"]
            with urllib.request.urlopen(base + "/setup") as response:
                assert b'<div id="root"' in response.read()
            request = urllib.request.Request(base + "/api/setup/complete", data=json.dumps({"skip_ai": True, "locale": "th", "values": {"SOURCE_LANG": "auto", "TARGET_LANG": "Thai", "NOVEL_PROJECTS_DIR": str(root / "novels")}}).encode(), headers={"Content-Type": "application/json", "If-Match": etag}, method="POST")
            with urllib.request.urlopen(request) as response:
                assert json.load(response)["success"]
            assert Path(state["environment"]["env_file_path"]).is_file()
        finally:
            process.terminate()
            process.communicate(timeout=15)
        terminal = subprocess.run([python, "-m", "nousetsu.cli.app", "setup", "--terminal"], input=f"en\nn\nauto\nEnglish\n{root / 'novels'}\nn\ny\n", text=True, encoding="utf-8", capture_output=True, cwd=root, env=env, timeout=30, creationflags=flags)
        assert terminal.returncode == 0, terminal.stderr
        assert "Setup complete" in terminal.stdout, terminal.stdout
        print("Installed wheel: browser + terminal setup passed with no Node.js and isolated user storage")


if __name__ == "__main__":
    main()
