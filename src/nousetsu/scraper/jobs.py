"""Persist scrape requests and statuses without storing provider credentials."""
import json
import os
import tempfile
from pathlib import Path


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".job-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def job_path(root: Path, task_id: str):
    if not task_id.isalnum() or len(task_id) > 32:
        raise ValueError("Invalid scraper job identifier")
    return root / ".novel" / "scraper" / "jobs" / f"{task_id}.json"


def read_job(root: Path, task_id: str):
    path = job_path(root, task_id)
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None
