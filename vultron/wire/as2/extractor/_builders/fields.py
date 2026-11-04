"""Field-extraction helpers shared by the extractor's builders.

Read ids, types and timestamps from raw AS2 wire objects as received (an
omitted time stays ``None``, ISSUE-3257), and wrap a bare reference as a
minimal :class:`~vultron.core.models.base.CoreObject`.
"""

from datetime import datetime

from vultron.core.models.base import CoreObject
from vultron.core.models.case_stub import CaseStubReference
from vultron.core.models.embargo_termination import EmbargoTermination
from vultron.core.states.embargo_register import (
    termination_reason_from_content,
)
from vultron.wire.as2.errors import (
    VultronParseValidationError,
)
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCaseStub,
)


def _get_id(field: object) -> str | None:
    """Resolve an AS2 reference field to its id string, or ``None``.

    AS2 permits a reference to be a URI string, an inline object, or an array of
    either, so all three shapes are resolved here.  When no id can be recovered
    the answer is ``None`` — never ``str(field)``.  A Python repr is not a URI,
    and these values reach `payloadSnapshot`, which is hashed into `entry_hash`
    and replicated to every participant: an absent field is recoverable, a
    ``"{'id': ...}"`` string in the chain is not (ARCH-15-001, CLP-07-011).
    """
    if field is None:
        return None
    if isinstance(field, str):
        return field or None
    if isinstance(field, dict):
        raw = field.get("id") or field.get("id_")
        return raw if isinstance(raw, str) and raw else None
    if isinstance(field, (list, tuple)):
        for item in field:
            if (resolved := _get_id(item)) is not None:
                return resolved
        return None
    raw_id = getattr(field, "id_", None)
    return raw_id if isinstance(raw_id, str) and raw_id else None


def _get_id_list(field: object) -> list[str] | None:
    """Convert an AS2 addressing field (Any | None) to a list of ID strings."""
    if field is None:
        return None
    if isinstance(field, str):
        return [field] if field else None
    if isinstance(field, list):
        ids = [_get_id(x) for x in field]
        result = [r for r in ids if r]
        return result or None
    single = _get_id(field)
    return [single] if single else None


def _get_type(field: object) -> str | None:
    if field is None or isinstance(field, str):
        return None
    t = getattr(field, "type_", None)
    return str(t) if t is not None else None


def termination_of(activity: as_Activity) -> EmbargoTermination:
    """Parse the termination a ``Remove(EmbargoEvent)`` carries.

    The what is ``content``, exactly ``END_TIME_REACHED`` or ``EARLY``
    (ADR-0122, EMB-13-004); the why, when the sender names one, is
    ``terminationCause``, which the wire model has already validated
    against the cause kinds (EMB-13-005).  Both are checked here, at the
    parse edge, so core receives a valid termination (ADR-0032): a cause on
    an ``END_TIME_REACHED`` termination is refused.

    Raises:
        VultronParseValidationError: when ``content`` is not a termination
            reason, or the cause does not fit it, naming the activity.
    """
    try:
        return EmbargoTermination.from_reason(
            termination_reason_from_content(
                getattr(activity, "content", None)
            ),
            getattr(activity, "termination_cause", None),
        )
    except ValueError as exc:
        raise VultronParseValidationError(
            f"activity {activity.id_!r}: {exc}"
        ) from exc


def _to_domain_obj(as_obj: object) -> CoreObject | None:
    """Wrap a bare AS2 object reference as a minimal CoreObject.

    A case stub is promoted to a :class:`CaseStubReference` instead, so the
    case it names reaches core in a field of its own and no consumer reads the
    case from the stub's ID (CM-11-003, CM-11-013).
    """
    if as_obj is None:
        return None
    if isinstance(as_obj, as_VulnerabilityCaseStub):
        return CaseStubReference(
            id_=as_obj.id_,
            type_=str(as_obj.type_),
            case_id=as_obj.case_id,
            published=as_obj.published,
            updated=as_obj.updated,
        )
    obj_id = _get_id(as_obj)
    if not obj_id:
        return None
    obj_type = _get_type(as_obj)
    return CoreObject(
        id_=obj_id,
        type_=obj_type,
        published=_get_timestamp(as_obj, "published"),
        updated=_get_timestamp(as_obj, "updated"),
    )


def _get_timestamp(obj: object, field: str) -> datetime | None:
    """Return a wire object's timestamp as received, or ``None``.

    An object's time is carried, never minted: when the sender supplied none,
    core records none.  Substituting the receiver's clock made every omission
    read downstream as the sender's claim (ISSUE-3257).  Callers pass the
    result explicitly, even as ``None``: omitting the keyword would let the
    core ``default_factory`` stamp the receiver's clock in its place.
    """
    val = getattr(obj, field, None)
    return val if isinstance(val, datetime) else None
