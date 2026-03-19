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
