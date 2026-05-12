"""
Custom exceptions for ANTS.
"""


class ANTSError(Exception):
    """Base exception for all ANTS errors."""
    pass


class NotFoundError(ANTSError):
    """Resource not found."""
    pass


class DuplicateError(ANTSError):
    """Duplicate resource."""
    pass


class ValidationError(ANTSError):
    """Validation failed."""
    pass


class AnalysisError(ANTSError):
    """Analysis processing failed."""
    pass


class VectorStoreError(ANTSError):
    """Vector store operation failed."""
    pass