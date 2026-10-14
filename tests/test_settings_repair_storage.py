"""Persistence failures must preserve settings and narrative memory."""
import json
import threading
import subprocess
import sys

import pytest

from nousetsu.models.config import ProjectConfig
from nousetsu.storage import repository as storage
from nousetsu.storage.repository import ConfigLoadError, NovelRepository, SettingsRecoveryError
from nousetsu.storage.settings_store import SettingsLockTimeout, file_lock


@pytest.fixture
def repo(tmp_path):
    value = NovelRepository(tmp_path)
    value.save_settings(ProjectConfig(title="Before", source_language="Japanese"))
    return value


def test_strict_writer_never_copies_in_place_or_changes_permissions(tmp_path, monkeypatch):
    path = tmp_path / "settings"
    path.write_text("before")
    def blocked(*args):
        raise PermissionError("blocked")
    monkeypatch.setattr(storage.os, "replace", blocked)
    monkeypatch.setattr(storage.os, "chmod", lambda *args: pytest.fail("chmod called"))
    with pytest.raises(PermissionError):
        storage.atomic_write_file(path, "after", strict=True, max_retries=1)
    assert path.read_text() == "before"
    assert list(tmp_path.glob("*.tmp_*")) == []


def test_save_settings_updates_bible_without_sanitizing(repo, monkeypatch):
    import nousetsu.storage.bible_sanitizer as sanitizer
    monkeypatch.setattr(sanitizer, "sanitize_bible", lambda value: pytest.fail("sanitizer called"))
    config = repo.load_config()
    config.title = "After"
    config.cross_folder_summaries = False
    repo.save_settings(config)
    bible = repo.load_bible(load_summaries=False)
    assert bible.title == "After"
    assert bible.cross_folder_summaries is False
    assert not (repo.novel_dir / "settings-transaction.json").exists()


@pytest.mark.parametrize("failure", ["config", "bible", "commit"])
def test_failed_transaction_rolls_back_both_files(repo, monkeypatch, failure):
    before = {name: path.read_bytes() for name, path in repo._settings_paths().items()}
    write = storage.atomic_write_file
    failed = False
    def fault(path, content, **kwargs):
        nonlocal failed
        target = (failure in repo._settings_paths() and path == repo._settings_paths()[failure])
        target |= failure == "commit" and path.name == "settings-transaction.json" and '"committed"' in content
        if target and not failed:
            failed = True
            raise OSError("injected failure")
        return write(path, content, **kwargs)
    monkeypatch.setattr(storage, "atomic_write_file", fault)
    config = repo.load_config()
    config.title = "After"
    with pytest.raises(OSError):
        repo.save_settings(config)
    assert {name: path.read_bytes() for name, path in repo._settings_paths().items()} == before


def test_prepared_recovery_refuses_external_edit(repo, monkeypatch):
    write = storage.atomic_write_file
    def fault(path, content, **kwargs):
        if path == repo.bible_file_path():
            repo.config_file_path().write_text("title: External\n", encoding="utf-8")
            raise OSError("injected failure")
        return write(path, content, **kwargs)
    monkeypatch.setattr(storage, "atomic_write_file", fault)
    config = repo.load_config()
    config.title = "After"
    with pytest.raises(SettingsRecoveryError):
        repo.save_settings(config)
    assert repo.config_file_path().read_text() == "title: External\n"
    assert (repo.novel_dir / "settings-transaction.json").exists()


def test_committed_recovery_never_rolls_back(repo, monkeypatch):
    unlink = storage.Path.unlink
    def fault(path, *args, **kwargs):
        if path.name == "settings-transaction.json":
            raise PermissionError("injected cleanup failure")
        return unlink(path, *args, **kwargs)
    monkeypatch.setattr(storage.Path, "unlink", fault)
    config = repo.load_config()
    config.title = "After"
    repo.save_settings(config)
    journal = json.loads((repo.novel_dir / "settings-transaction.json").read_text())
    assert journal["state"] == "committed"
    monkeypatch.setattr(storage.Path, "unlink", unlink)
    assert NovelRepository(repo.root_dir).load_config().title == "After"
    assert repo.load_bible().title == "After"


def test_corrupt_config_is_not_replaced_by_defaults(repo):
    repo.config_file_path().write_text("max_review_loops: 999\n", encoding="utf-8")
    with pytest.raises(ConfigLoadError):
        repo.load_config()
    assert "999" in repo.config_file_path().read_text()


def test_missing_config_keeps_bible_metadata_fallback(repo):
    repo.config_file_path().unlink()
    assert repo.load_config().title == "Before"


def test_language_detection_does_not_overwrite_newer_choice(repo):
    config = repo.load_config()
    config.source_language = "Korean"
    repo.save_settings(config)
    repo.set_languages(source_lang="Chinese", expected_source_language="Auto")
    assert repo.load_config().source_language == "Korean"


def test_memory_save_preserves_latest_settings_metadata(repo, monkeypatch):
    import nousetsu.storage.bible_sanitizer as sanitizer
    monkeypatch.setattr(sanitizer, "sanitize_bible", lambda value: value)
    old_bible = repo.load_bible()
    config = repo.load_config()
    config.title = "Newer"
    repo.save_settings(config)
    old_bible.whole_story_summary = "New chapter memory"
    repo.save_bible(old_bible)
    current = repo.load_bible()
    assert current.title == "Newer"
    assert current.whole_story_summary == "New chapter memory"


def test_intentional_bible_editor_changes_commit_metadata_and_memory(repo, monkeypatch):
    import nousetsu.storage.bible_sanitizer as sanitizer
    monkeypatch.setattr(sanitizer, "sanitize_bible", lambda value: value)
    bible = repo.load_bible()
    bible.title = "Edited"
    bible.target_language = "English"
    bible.cross_folder_summaries = False
    bible.whole_story_summary = "Edited memory"
    repo.save_edited_bible(bible)
    assert repo.load_config().title == "Edited"
    assert repo.load_config().target_language == "English"
    assert repo.load_config().cross_folder_summaries is False
    assert repo.load_bible().whole_story_summary == "Edited memory"


def test_lock_is_reentrant_and_other_thread_times_out(tmp_path):
    path = tmp_path / "settings.lock"
    errors = []
    def worker():
        try:
            with file_lock(path, timeout=0.05):
                pytest.fail("other thread acquired lock")
        except SettingsLockTimeout:
            errors.append(True)
    with file_lock(path):
        with file_lock(path):
            thread = threading.Thread(target=worker)
            thread.start()
            thread.join(timeout=2)
            assert not thread.is_alive()
    assert errors == [True]


def test_other_process_cannot_acquire_owned_lock(tmp_path):
    path = tmp_path / "settings.lock"
    script = """import sys
from pathlib import Path
from nousetsu.storage.settings_store import file_lock, SettingsLockTimeout
try:
    with file_lock(Path(sys.argv[1]), timeout=0.1):
        sys.exit(2)
except SettingsLockTimeout:
    sys.exit(0)
"""
    with file_lock(path):
        child = subprocess.run([sys.executable, "-c", script, str(path)], capture_output=True, timeout=10)
    assert child.returncode == 0, child.stderr.decode(errors="replace")


@pytest.mark.parametrize("stage", ["config", "bible", "committed"])
def test_restart_recovers_crash_at_each_transaction_boundary(repo, stage):
    script = """import os, sys
from nousetsu.storage import repository as storage
r = storage.NovelRepository(sys.argv[1])
write = storage.atomic_write_file
stage = sys.argv[2]
def crash(path, content, **kwargs):
    write(path, content, **kwargs)
    if ((stage in r._settings_paths() and path == r._settings_paths()[stage]) or
        (stage == 'committed' and path.name == 'settings-transaction.json' and '\"committed\"' in content)):
        os._exit(17)
storage.atomic_write_file = crash
c = r.load_config()
c.title = 'After'
r.save_settings(c)
"""
    child = subprocess.run([sys.executable, "-c", script, str(repo.root_dir), stage], capture_output=True, timeout=10)
    assert child.returncode == 17, child.stderr.decode(errors="replace")
    reopened = NovelRepository(repo.root_dir)
    expected = "After" if stage == "committed" else "Before"
    assert reopened.load_config().title == expected
    assert reopened.load_bible().title == expected
