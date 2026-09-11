"""Unit tests for formatting helpers."""
from nousetsu.utils.formatting import format_duration


def test_format_duration_zero_and_negative():
    assert format_duration(0.0) == "0s"
    assert format_duration(-5.0) == "0s"


def test_format_duration_sub_second():
    assert format_duration(0.4) == "0.4s"
    assert format_duration(0.01) == "0.0s"
    assert format_duration(0.8) == "0.8s"


def test_format_duration_seconds():
    assert format_duration(1.0) == "1s"
    assert format_duration(5.2) == "5s"
    assert format_duration(45.2) == "45s"
    assert format_duration(59.4) == "59s"


def test_format_duration_minutes():
    assert format_duration(60.0) == "1m 0s"
    assert format_duration(75.0) == "1m 15s"
    assert format_duration(846.4) == "14m 6s"
    assert format_duration(3599.0) == "59m 59s"


def test_format_duration_hours():
    assert format_duration(3600.0) == "1h"
    assert format_duration(3660.0) == "1h 1m"
    assert format_duration(3665.0) == "1h 1m 5s"
    assert format_duration(7205.0) == "2h 0m 5s"
