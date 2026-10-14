"""Writable user storage and packaged frontend discovery."""
import os
import sys
from pathlib import Path


def user_config_dir() -> Path:
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming")) / "com.nousetsu.app"
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support/com.nousetsu.app"
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "nousetsu"


def documents_dir() -> Path:
    if sys.platform == "win32":
        import ctypes
        import uuid
        folder_id = (ctypes.c_byte * 16).from_buffer_copy(uuid.UUID("FDD39AD0-238F-46AF-ADB4-6C85480369C7").bytes_le)
        result = ctypes.c_wchar_p()
        if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(folder_id), 0, None, ctypes.byref(result)) == 0:
            try:
                return Path(result.value)
            finally:
                ctypes.windll.ole32.CoTaskMemFree(result)
    return Path.home() / "Documents"


def frontend_dist() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "web/dist"
    packaged = Path(__file__).resolve().parents[1] / "data/web"
    if (packaged / "index.html").is_file():
        return packaged
    return Path(__file__).resolve().parents[3] / "web/dist"
