"""Global pytest configuration and hermetic test environment fixtures."""
import pytest


@pytest.fixture(autouse=True)
def isolate_test_environment(monkeypatch, tmp_path_factory):
    """Ensure tests run in an isolated, offline mock environment with isolated registry."""
    reg_tmp = tmp_path_factory.mktemp("registry")
    monkeypatch.setenv("NOVEL_REGISTRY_DIR", str(reg_tmp))
    monkeypatch.setenv("NOVEL_MODEL", "mock-model")
    monkeypatch.setenv("NOVEL_FALLBACK_MODEL", "mock-model")
    monkeypatch.setenv("NOVEL_EXTRACTOR_MODEL", "mock-model")
    monkeypatch.setenv("NOVEL_DRAFTER_MODEL", "mock-model")
    monkeypatch.setenv("NOVEL_CRITIC_MODEL", "mock-model")
    monkeypatch.setenv("NOVEL_POLISHER_MODEL", "mock-model")
    monkeypatch.setenv("NOVEL_CHRONICLER_MODEL", "mock-model")
    monkeypatch.setenv("NOVEL_USE_INTERACTIONS", "0")
