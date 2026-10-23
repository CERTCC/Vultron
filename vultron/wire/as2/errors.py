"""AS2 wire layer errors for the Vultron Protocol."""

from vultron.wire.errors import VultronWireError


class VultronParseError(VultronWireError):
    """Raised when AS2 activity parsing fails."""


class VultronParseMissingTypeError(VultronParseError):
    """Raised when the 'type' field is missing from an AS2 activity body."""


class VultronParseUnknownTypeError(VultronParseError):
    """Raised when the activity type is not found in the AS2 vocabulary."""


class VultronParseValidationError(VultronParseError):
    """Raised when an AS2 activity fails Pydantic schema validation."""


class VultronParseMissingPublishedError(VultronParseError):
    """Raised when an inbound AS2 activity carries no ``published`` timestamp.

    ``as_Base`` declares ``published`` with ``default_factory=now_utc`` because
    the same classes are used to *author* outbound activities, where stamping
    the local clock is correct.  On the inbound path it is not: a defaulted
    ``published`` is the receiver's clock masquerading as the sender's claim,
    and every downstream check that reads it then compares that clock against
    itself (CLP-14-007, CLP-14-008, CLP-15-003).

    Absence is therefore a message-validity failure, caught at the parse
    threshold rather than corrected downstream (ADR-0032: validate at the edge).
    """
