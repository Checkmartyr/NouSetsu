"""Unit tests for atomic_write_file retry and fallback behavior."""
import os
import time
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from nousetsu.storage.repository import atomic_write_file


def test_atomic_write_creates_file(tmp_path):
    """Basic write creates the target file with correct content."""
    target = tmp_path / "test_output.txt"
    atomic_write_file(target, "hello world")
    assert target.read_text(encoding="utf-8") == "hello world"


def test_atomic_write_overwrites_existing(tmp_path):
    """Writing to an existing file replaces its content."""
    target = tmp_path / "existing.txt"
    target.write_text("old content", encoding="utf-8")
    atomic_write_file(target, "new content")
    assert target.read_text(encoding="utf-8") == "new content"


def test_atomic_write_creates_parent_dirs(tmp_path):
    """Writing to a nested path creates parent directories automatically."""
    target = tmp_path / "deep" / "nested" / "dir" / "file.yaml"
    atomic_write_file(target, "content: value")
    assert target.exists()
    assert target.read_text(encoding="utf-8") == "content: value"


def test_atomic_write_retries_on_permission_error(tmp_path):
    """PermissionError triggers retry backoff, succeeding on later attempt."""
    target = tmp_path / "retried.txt"
    call_count = 0

    original_replace = os.replace
    def mock_replace(src, dst):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise PermissionError("[WinError 5] Access is denied")
        return original_replace(src, dst)

    with patch("nousetsu.storage.repository.os.replace", side_effect=mock_replace):
        with patch("nousetsu.storage.repository.time.sleep") as mock_sleep:
            atomic_write_file(target, "retry success", initial_delay=0.001)

    assert target.read_text(encoding="utf-8") == "retry success"
    assert mock_sleep.call_count == 2  # Slept before attempt 2 and 3
    assert call_count == 3


def test_atomic_write_fallback_on_persistent_permission_error(tmp_path):
    """When all retries exhausted, falls back to in-place write."""
    target = tmp_path / "fallback.txt"
    target.write_text("initial", encoding="utf-8")

    def always_fail(src, dst):
        raise PermissionError("[WinError 5] Access is denied")

    with patch("nousetsu.storage.repository.os.replace", side_effect=always_fail):
        with patch("nousetsu.storage.repository.time.sleep"):
            atomic_write_file(target, "fallback content", max_retries=3, initial_delay=0.001)

    assert target.read_text(encoding="utf-8") == "fallback content"


def test_atomic_write_cleanup_tmp_on_success(tmp_path):
    """Temporary file is cleaned up after successful write."""
    target = tmp_path / "clean.txt"
    atomic_write_file(target, "clean")

    # No .tmp_ files should remain
    tmp_files = list(tmp_path.glob("*.tmp_*"))
    assert len(tmp_files) == 0
