class AppError(Exception):
    """Base exception for the application."""


class GovernanceError(AppError):
    """Base governance-related exception."""


class StateCorruptedError(GovernanceError):
    """Raised when the state machine is corrupted or invalid."""


class StateNotFoundError(StateCorruptedError):
    """.specs/state.json does not exist (project not initialised)."""


class UnauthorizedFileAccessError(GovernanceError):
    """Raised when an agent attempts to edit a file outside unlocked_paths."""


class GateCheckFailedError(GovernanceError):
    """Raised when a gate check fails (e.g. missing pair deliverables or unapproved reviews)."""


class TraceabilityMismatchError(GovernanceError):
    """Raised when bidirectional traceability constraints are violated."""
