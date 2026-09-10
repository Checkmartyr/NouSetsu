"""Unit tests for invoke_with_retry and is_transient_error."""
import pytest
from src.agents.llm import invoke_with_retry, is_transient_error


def test_is_transient_error():
    assert is_transient_error(Exception("500 INTERNAL error encountered"))
    assert is_transient_error(Exception("503 Service Unavailable"))
    assert is_transient_error(Exception("429 Resource Exhausted (rate limit)"))
    assert is_transient_error(Exception("Connection timed out"))
    assert not is_transient_error(ValueError("Invalid syntax"))
    assert not is_transient_error(KeyError("Missing key"))


def test_invoke_with_retry_success_after_transient():
    attempts = 0
    notifications = []

    def flakey_call():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise ConnectionError("500 INTERNAL: Google backend temporary failure")
        return "success!"

    result = invoke_with_retry(
        flakey_call,
        max_retries=4,
        initial_delay=0.01,
        backoff_factor=1.5,
        notify_callback=lambda msg: notifications.append(msg)
    )

    assert result == "success!"
    assert attempts == 3
    assert len(notifications) == 2
    assert "Attempt 1/4" in notifications[0]
    assert "Attempt 2/4" in notifications[1]


def test_invoke_with_retry_non_transient_fails_immediately():
    attempts = 0

    def bad_code():
        nonlocal attempts
        attempts += 1
        raise TypeError("Fatal type mismatch")

    with pytest.raises(TypeError, match="Fatal type mismatch"):
        invoke_with_retry(bad_code, max_retries=4, initial_delay=0.01)

    assert attempts == 1


def test_invoke_with_retry_max_retries_exhausted():
    attempts = 0

    def always_500():
        nonlocal attempts
        attempts += 1
        raise ConnectionError("503 UNAVAILABLE")

    with pytest.raises(ConnectionError, match="503 UNAVAILABLE"):
        invoke_with_retry(always_500, max_retries=3, initial_delay=0.01, backoff_factor=1.0)

    assert attempts == 3
