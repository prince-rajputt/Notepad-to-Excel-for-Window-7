"""Shared exception types for document readers."""


class DocumentReadError(Exception):
    """Raised when a source document (.rtf, .docx, ...) cannot be read or parsed."""
