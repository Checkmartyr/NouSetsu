"""Formatting helpers for durations, numbers, and display text."""


def format_duration(seconds: float) -> str:
    """Format duration in seconds into a human-friendly string (compact style).

    Examples:
        0.0 -> "0s"
        0.4 -> "0.4s"
        45.2 -> "45s"
        846.4 -> "14m 6s"
        3665.0 -> "1h 1m 5s"
    """
    if seconds <= 0:
        return "0s"
    if seconds < 1.0:
        return f"{seconds:.1f}s"

    total_seconds = int(round(seconds))
    if total_seconds < 60:
        return f"{total_seconds}s"

    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60

    if hours > 0:
        if secs > 0:
            return f"{hours}h {minutes}m {secs}s"
        elif minutes > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{hours}h"
    else:
        return f"{minutes}m {secs}s"
