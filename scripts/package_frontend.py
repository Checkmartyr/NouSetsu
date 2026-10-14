"""Ship the production UI in distributions; users never need Node.js."""
from pathlib import Path
import os
import shutil
import subprocess
from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version, build_data):
        if version == "editable":
            return
        root = Path(self.root)
        dist = root / "src/nousetsu/data/web"
        if (dist / "index.html").is_file():
            # An sdist already contains these package files; forcing them duplicates entries.
            return
        else:
            dist = root / "web/dist"
            npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
            if not npm:
                raise RuntimeError("Building from a checkout requires Node.js/npm. Install a released wheel to run without Node.js.")
            subprocess.run([npm, "run", "build"], cwd=root / "web", check=True)
        if not (dist / "index.html").is_file():
            raise RuntimeError("The production frontend is missing")
        destination = "nousetsu/data/web" if self.target_name == "wheel" else "src/nousetsu/data/web"
        build_data.setdefault("force_include", {})[str(dist)] = destination
