from typing import Any, Dict, Optional


class ArchaeologAIException(Exception):
    """Base exception class for ArchaeologAI."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class RepositoryNotFoundError(ArchaeologAIException):
    """Exception raised when a repository is not found."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=404, details=details)


class IngestionError(ArchaeologAIException):
    """Exception raised during github repository ingestion."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=500, details=details)


class RetrievalError(ArchaeologAIException):
    """Exception raised during hybrid retrieval."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=500, details=details)


class LLMError(ArchaeologAIException):
    """Exception raised when LLM generation fails."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=502, details=details)


class GraphError(ArchaeologAIException):
    """Exception raised during Neo4j graph operations."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=500, details=details)
