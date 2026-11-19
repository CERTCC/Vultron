#!/usr/bin/env python

#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

"""Parse-edge refusal of a case reference, case preview or redaction marker
where no act puts one.

Two inline forms stand for a case without carrying it whole, and each has
the slots an act may put it in:

- A ``VulnerabilityCase`` that carries only its ``id`` and ``type`` is the
  typed reference a participant's ``Join``, ``Ignore`` or ``Leave`` of a case,
  or an ownership-transfer ``Offer``, names its case by (AKM-03-004,
  ADR-0165).  Anywhere else a case is carried whole, so a reference there is
  a malformed case: a ``Create(VulnerabilityCase)`` that carried one would
  reach core naming a case with no owner and no position.
- A ``CasePreview`` is what an invitee decides on before it may see
  the case (ADR-0114, ADR-0205), so its one slot
  is the ``preview`` of the typed case reference that is the stub
  ``Invite``'s ``object``, at any depth: the ``Accept`` and ``Reject`` of
  that ``Invite`` carry it inline (MV-10-002).  A preview anywhere else, and
  a previewed case reference anywhere but an ``Invite``'s ``object``, is a
  misplaced preview.

A ``Redacted`` marker stands for a value a preview withholds (ADR-0193), so
its place is inside a preview, at any depth: a preview is read as its sender
sent it (MV-12-001, ADR-0217).  A full object holds no marker, and no activity
slot or free-form field of any object outside a preview (``tag``,
``attachment``, ``inReplyTo``, ...) holds one (MV-12-002).

The walk enters every field of a parsed model and every list item; a
dict-valued field is not entered, because the parser builds every inline
object as a model and keeps no raw mapping in a reference field.

The parser refuses each form where it arrives, as it refused the sparse
case before references existed: an inline object that is not what its slot
admits is never read as a less specific type, and its activity is refused as
malformed (MV-04-003; ADR-0032, validate at the edge).  The rules report
every misplaced slot of every form in one refusal (EH-07-001).
"""

from collections.abc import Callable, Iterator

from pydantic import BaseModel

from vultron.core.models.case_naming import CASE_NAMING_ACTIVITY_TYPES
from vultron.core.models.preview_object import PreviewObject, PreviewValue
from vultron.core.models.redacted import Redacted
from vultron.wire.as2.errors import VultronParseValidationError
from vultron.wire.as2.typed_reference import (
    is_case_reference,
    is_previewed_reference,
)
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.objects.case_preview import as_CasePreview

#: Whether *child*, held in *parent*'s field *field_name*, sits where it may.
#: An admitted child is not walked further.
_SlotPredicate = Callable[[BaseModel, str, object], bool]

#: Whether a value is the form whose slots are checked.
_FormPredicate = Callable[[object], bool]


def _is_case_preview(value: object) -> bool:
    """Whether *value* is a case preview (MV-10-002)."""
    return isinstance(value, as_CasePreview)


#: The object an admitted child holds whose own fields are still walked, or
#: ``None`` to walk nothing below it.
_Inside = Callable[[object], BaseModel | None]


def _nothing_inside(_child: object) -> BaseModel | None:
    return None


def _misplaced(
    value: object,
    path: str,
    is_form: _FormPredicate,
    admits: _SlotPredicate,
    inside: _Inside = _nothing_inside,
) -> Iterator[str]:
    """The paths below *path* that hold the form in a slot *admits* refuses.

    An admitted child is not refused, and the walk does not enter it, except
    for the fields of the object *inside* names in it: an admitted case
    reference's preview may not hold another preview.
    """
    if isinstance(value, list):
        for index, item in enumerate(value):
            yield from _misplaced(
                item, f"{path}[{index}]", is_form, admits, inside
            )
        return
    if is_form(value):
        yield path
        return
    # Inline domain objects are core models, not ``as_Base`` (ARCH-25-004),
    # and a misplaced form inside one is as misplaced as anywhere else.
    if not isinstance(value, BaseModel):
        return
    for field_name, info in type(value).model_fields.items():
        child = getattr(value, field_name, None)
        # The key the sender wrote, so the refusal names the slot it used.
        key = info.serialization_alias or field_name.rstrip("_")
        child_path = f"{path}.{key}" if path else key
        if not admits(value, field_name, child):
            yield from _misplaced(child, child_path, is_form, admits, inside)
            continue
        held = inside(child)
        if held is not None:
            yield from _fields_misplaced(
                held, f"{child_path}.preview", is_form, admits, inside
            )


def _fields_misplaced(
    value: BaseModel,
    path: str,
    is_form: _FormPredicate,
    admits: _SlotPredicate,
    inside: _Inside,
) -> Iterator[str]:
    """The paths in *value*'s fields, not *value* itself, that hold the form
    in a slot *admits* refuses."""
    for field_name, info in type(value).model_fields.items():
        key = info.serialization_alias or field_name.rstrip("_")
        yield from _misplaced(
            getattr(value, field_name, None),
            f"{path}.{key}",
            is_form,
            admits,
            inside,
        )


def _names_case_by_reference(
    parent: BaseModel, field_name: str, child: object
) -> bool:
    """A case reference as the object of a ``Join``, ``Ignore``, ``Leave`` or
    ``Offer`` (AKM-03-004)."""
    return (
        is_case_reference(child)
        and field_name == "object_"
        and isinstance(parent, as_Activity)
        and str(parent.type_) in CASE_NAMING_ACTIVITY_TYPES
    )


def _is_invited_case_preview(parent: BaseModel, field_name: str) -> bool:
    """The ``object`` of an ``Invite``, where a case reference carries the
    case's preview (ADR-0205)."""
    return (
        field_name == "object_"
        and isinstance(parent, as_Activity)
        and str(parent.type_) == "Invite"
    )


def _admits_case_preview(
    parent: BaseModel, field_name: str, child: object
) -> bool:
    """A case preview carried as the preview of a case reference an ``Invite`` names
    in its ``object`` (MV-10-002).  A preview met anywhere else is misplaced:
    the walk does not enter an admitted reference, so it meets a preview only
    outside one."""
    return is_previewed_reference(child) and _is_invited_case_preview(
        parent, field_name
    )


def _is_redaction_marker(value: object) -> bool:
    """Whether *value* is a ``Redacted`` marker (MV-12-003)."""
    return isinstance(value, Redacted)


def _admits_redaction_marker(
    parent: BaseModel, field_name: str, child: object
) -> bool:
    """A preview, which may hold a marker anywhere inside it (MV-12-001).

    The walk does not enter an admitted preview, so it meets a marker only
    outside one.  The loose forms a preview holds its contents in are
    preview forms too; the parse edge builds them only inside a preview.
    """
    return isinstance(child, (PreviewObject, PreviewValue))


def _misplaced_case_reference(activity: as_Activity) -> str | None:
    """The fault of a case reference where a case is carried (AKM-03-004)."""
    misplaced = list(
        _misplaced(
            activity,
            "",
            is_case_reference,
            _names_case_by_reference,
        )
    )
    if not misplaced:
        return None
    return (
        f"a VulnerabilityCase carrying only its id and type at"
        f" {', '.join(misplaced)} names the case; only the object of a Join,"
        " Ignore, Leave or Offer may name a case by reference, and anywhere"
        " else the case is carried whole (AKM-03-004)"
    )


def _preview_of(reference: object) -> BaseModel | None:
    """The case preview an admitted case reference carries."""
    preview = getattr(reference, "preview", None)
    return preview if isinstance(preview, BaseModel) else None


def _misplaced_case_preview(activity: as_Activity) -> str | None:
    """The fault of a case preview outside a stub Invite's object, a preview
    inside a preview included (MV-10-002)."""
    misplaced = list(
        _misplaced(
            activity,
            "",
            _is_case_preview,
            _admits_case_preview,
            _preview_of,
        )
    )
    if not misplaced:
        return None
    return (
        f"a CasePreview at {', '.join(misplaced)}; a case preview is"
        " permitted only as the preview of a case reference that is an"
        " Invite's object, wherever that Invite is carried inline; anywhere"
        " else name the case by its URI (MV-10-002)"
    )


def _misplaced_redaction_marker(activity: as_Activity) -> str | None:
    """The fault of a marker outside a preview (MV-12-002)."""
    misplaced = list(
        _misplaced(
            activity,
            "",
            _is_redaction_marker,
            _admits_redaction_marker,
        )
    )
    if not misplaced:
        return None
    return (
        f"a Redacted marker at {', '.join(misplaced)}; a marker is permitted"
        " only inside a preview, never in a full object or an activity slot"
        " (MV-12-002)"
    )


_PLACEMENT_RULES = (
    _misplaced_case_reference,
    _misplaced_case_preview,
    _misplaced_redaction_marker,
)


def refuse_misplaced_forms(activity: as_Activity) -> None:
    """Refuse *activity* when a case reference, case preview or ``Redacted``
    marker sits where no act puts one.

    Every rule runs, so one refusal names every misplaced slot of every form
    (EH-07-001).

    Raises:
        VultronParseValidationError: Naming the activity, each rule's fault
            and each slot.
    """
    faults = [fault for rule in _PLACEMENT_RULES if (fault := rule(activity))]
    if faults:
        raise VultronParseValidationError(
            f"activity {activity.id_!r}: {'; and '.join(faults)}"
        )


__all__ = ["refuse_misplaced_forms"]
