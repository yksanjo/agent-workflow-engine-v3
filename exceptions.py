"""Exception classes for the Hierarchical Agent Coordinator."""


class CoordinationException(Exception):
    """Base exception for coordination errors."""
    pass


class DelegationException(CoordinationException):
    """Raised when task delegation fails."""
    pass


class WorkerException(CoordinationException):
    """Raised when a worker encounters an error."""
    pass


class HierarchyViolation(CoordinationException):
    """Raised when hierarchical constraints are violated."""
    pass


class ResultAggregationException(CoordinationException):
    """Raised when result aggregation fails."""
    pass


class AuditException(CoordinationException):
    """Raised when audit operations fail."""
    pass


class HumanConfirmationRequired(CoordinationException):
    """Raised when high-risk decisions require human confirmation."""
    def __init__(self, message, context=None):
        super().__init__(message)
        self.context = context or {}
