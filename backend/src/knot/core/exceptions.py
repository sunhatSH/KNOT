"""Custom exceptions for KNOT."""


class KnotError(Exception):
    """Base exception for all KNOT errors."""


class WorkflowError(KnotError):
    """Raised when a workflow operation fails."""


class WorkflowNotFoundError(WorkflowError):
    """Raised when a workflow is not found."""


class NodeExecutionError(WorkflowError):
    """Raised when a node execution fails."""


class LLMProviderError(KnotError):
    """Raised when an LLM provider call fails."""


class KnowledgeError(KnotError):
    """Raised when a knowledge retrieval operation fails."""


class ToolExecutionError(KnotError):
    """Raised when a tool execution fails."""


class ConfigurationError(KnotError):
    """Raised when configuration is invalid or missing."""
