"""Custom exception classes for novel translation workflow."""


class BatchStoppedException(Exception):
    """Raised when batch translation is stopped or cancelled by user."""
    pass
