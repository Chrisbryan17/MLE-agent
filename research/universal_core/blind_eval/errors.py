class ProtocolError(ValueError):
    """Base error for invalid protocol state."""
class CommitmentError(ProtocolError):
    """Commitment and bound material do not match."""
class SubmissionError(ProtocolError):
    """Submission identity, ordering, or seals are invalid."""
class ScoringError(ProtocolError):
    """Reveal or score cannot be validated."""
class AuditError(ProtocolError):
    """Evidence package failed offline audit."""
