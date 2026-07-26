"""Project-owned exceptions for search request validation."""

from __future__ import annotations


class SearchValidationError(ValueError):
    """Raised when raw search inputs cannot become a valid search request.

    Parameters
    ----------
    message : str
        Human-readable validation message suitable for API and CLI boundaries.

    Attributes
    ----------
    message : str
        Stored validation message without framework-specific response details.
    """

    def __init__(self, message: str) -> None:
        """Store the validation message for boundary-layer error mapping."""
        super().__init__(message)
        self.message = message
