"""Small cross-process locking primitives for settings persistence."""
from contextlib import contextmanager
from pathlib import Path
import os
import threading
import time


class SettingsLockTimeout(TimeoutError):
    """Another process is changing this settings store."""


_guard = threading.Lock()
_locks = {}
_local = threading.local()


@contextmanager
def file_lock(path: Path, timeout: float = 5.0):
    """Serialize threads and processes; nested acquisition in one thread is safe."""
    path = Path(path).resolve()
    key = str(path)
    with _guard:
        lock = _locks.setdefault(key, threading.RLock())
    deadline = time.monotonic() + timeout
    if not lock.acquire(timeout=timeout):
        raise SettingsLockTimeout("Settings are busy; retry shortly")
    held = getattr(_local, "held", None)
    if held is None:
        held = _local.held = set()
    handle = None
    try:
        if key in held:
            yield
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        handle = open(path, "a+b")
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        while True:
            try:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except (OSError, BlockingIOError):
                if time.monotonic() >= deadline:
                    raise SettingsLockTimeout("Settings are busy; retry shortly") from None
                time.sleep(min(0.05, max(0, deadline - time.monotonic())))
        held.add(key)
        try:
            yield
        finally:
            held.remove(key)
            handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    finally:
        if handle is not None:
            handle.close()
        lock.release()
