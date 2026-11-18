"""Field-extraction helpers shared by the extractor's builders.

Read ids, types and timestamps from raw AS2 wire objects as received (an
omitted time stays ``None``, ISSUE-3257), and wrap a bare reference as a
minimal :class:`~vultron.core.models.base.CoreObject`.
"""

from datetime import datetime

from vultron.core.models.base import CoreObject
from vultron.core.models.case_preview import (
    CasePreview,
    PreviewedCaseReference,
)
from vultron.core.models.embargo_termination import EmbargoTermination
from vultron.core.states.embargo_register import (
    termination_reason_from_content,
)
from vultron.wire.as2.errors import (
    VultronParseMissingPublishedError,
    VultronParseValidationError,
)
from vultron.wire.as2.typed_reference import is_previewed_reference
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity


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
    """Convert an AS2 addressing field (one value or many) to a list of IDs."""
    if field is None:
        return None
    if isinstance(field, str):
        return [field] if field else None
    if isinstance(field, (list, tuple)):
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

    A typed reference carrying the case's preview is promoted to a
    :class:`PreviewedCaseReference` instead, so the preview's content reaches
    core with the case the reference names (ADR-0205).
    """
    if as_obj is None:
        return None
    if is_previewed_reference(as_obj) and isinstance(
        as_obj.preview, CasePreview
    ):
        # The preview is one class on both sides (ARCH-25-003), so it
        # reaches core as received.
        return PreviewedCaseReference(
            id_=as_obj.id_,
            type_=str(as_obj.type_),
            published=None,
            updated=None,
            preview=as_obj.preview,
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


def _required_published(obj: object) -> datetime:
    """A received whole object's ``published``, which it must carry.

    ``parse_activity`` refuses a whole object without one (CLP-15-011), so
    only an object that bypassed the parser reaches here without it, and
    this never mints a time to stand in for the missing one.

    Raises:
        VultronParseMissingPublishedError: When *obj* carries no
            ``published``, naming the object.
    """
    published = _get_timestamp(obj, "published")
    if published is None:
        raise VultronParseMissingPublishedError(
            f"{type(obj).__name__} {_get_id(obj)!r} carries no 'published';"
            " the receiver does not supply its own clock (CLP-15-011)"
        )
    return published
