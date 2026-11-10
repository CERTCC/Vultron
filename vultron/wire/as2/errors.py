"""AS2 wire layer errors for the Vultron Protocol."""

from vultron.errors import VultronProofVerificationError
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


class VultronProofError(VultronWireError):
    """Raised when an object integrity proof cannot be made or checked."""


class VultronProofInvalidError(
    VultronProofError, VultronProofVerificationError
):
    """Raised when a document's proof is missing, malformed or does not verify.

    A receiver refuses the document (SIG-03-002).  It is the wire form of the
    core category :exc:`~vultron.errors.VultronProofVerificationError`
    (EH-03-005), so ``translate_domain_errors`` maps it to 422.
    """


class VultronUnsignableJsonError(VultronProofError, ValueError):
    """Raised when JSON is refused rather than signed or verified.

    Duplicate object keys, non-finite numbers and integers outside
    ±(2^53 - 1) are read differently by different parsers, so a signer and a
    verifier could canonicalize different values from one body.
    """


class VultronJsonSyntaxError(VultronUnsignableJsonError):
    """Raised when text is not JSON at all, by RFC 8259's grammar.

    Text that does not decode, bytes that are not UTF-8, and the ``NaN`` and
    ``Infinity`` literals Python's parser accepts but RFC 8259 does not.  A
    receiver answers it as a malformed request, 400 (IE-07-001, HTTP-03-004).
    """


class VultronRefusedJsonError(VultronUnsignableJsonError):
    """Raised when well-formed JSON is refused rather than signed or verified.

    A duplicate object key, an integer outside ±(2^53 - 1), a number too
    large for a double, nesting too deep to read, or a value that is not an
    object where an activity must be one.  Parsers read these differently,
    or the receiver cannot read them at all (I-JSON, RFC 7493), so the
    syntax is fine and the content is refused: a receiver answers it 422.
    """


class VultronForeignAuthorError(VultronProofError):
    """Raised when an outbox is asked to sign an activity another actor wrote.

    An actor holds only its own private key, so it signs only its own
    messages (SIG-05-004).  The activity's ``actor`` must be the actor whose
    store and outbox are sealing it; any other author is refused before
    anything is signed or stored.  Not a ``ValueError``: it is a wiring
    defect, not a malformed body, so no validation handler absorbs it.
    """


class VultronMultikeyError(VultronProofError, ValueError):
    """Raised when a ``Multikey`` value is not a base58btc Ed25519 key."""
