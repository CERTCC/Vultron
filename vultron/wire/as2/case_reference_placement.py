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

"""Parse-edge refusal of a case reference or case stub where no act puts one.

Two inline forms stand for a case without carrying it whole, and each has
the slots an act may put it in:

- A ``VulnerabilityCase`` that carries only its ``id`` and ``type`` is the
  typed reference a participant's ``Join``, ``Ignore`` or ``Leave`` of a case,
  or an ownership-transfer ``Offer``, names its case by (AKM-03-004,
  ADR-0165).  Anywhere else a case is carried whole, so a reference there is
  a malformed case: a ``Create(VulnerabilityCase)`` that carried one would
  reach core naming a case with no owner and no position.
- A ``VulnerabilityCaseStub`` is what an invitee decides on before it may see
  the case (ADR-0114), so its one slot is the ``target`` of the ``Invite``
  whose ``object`` is the inline actor it invites to the case, at any depth:
  the ``Accept`` and ``Reject`` of that ``Invite`` carry it inline
  (MV-10-002).

The parser refuses either form where it arrives, as it refused the sparse
case before references existed: an inline object that is not what its slot
admits is never read as a less specific type, and its activity is refused as
malformed (MV-04-003; ADR-0032, validate at the edge).  Each rule reports
every misplaced slot at once (EH-07-001).
"""

from collections.abc import Callable, Iterator

from pydantic import BaseModel

from vultron.core.models.actor import CoreActor
from vultron.core.models.case_naming import CASE_NAMING_ACTIVITY_TYPES
from vultron.wire.as2.errors import VultronParseValidationError
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCaseReference,
    as_VulnerabilityCaseStub,
)

#: Whether *parent*'s field *field_name* is a slot the form may sit in.
_SlotPredicate = Callable[[BaseModel, str], bool]


def _misplaced(
    value: object, path: str, form: type, admits: _SlotPredicate
) -> Iterator[str]:
    """The paths below *path* that hold *form* in a slot *admits* refuses."""
    if isinstance(value, list):
        for index, item in enumerate(value):
            yield from _misplaced(item, f"{path}[{index}]", form, admits)
        return
    if isinstance(value, form):
        yield path
        return
    # Inline domain objects are core models, not ``as_Base`` (ARCH-25-004),
    # and a misplaced form inside one is as misplaced as anywhere else.
    if not isinstance(value, BaseModel):
        return
    for field_name, info in type(value).model_fields.items():
        child = getattr(value, field_name, None)
        if isinstance(child, form) and admits(value, field_name):
            continue
        # The key the sender wrote, so the refusal names the slot it used.
        key = info.serialization_alias or field_name.rstrip("_")
        child_path = f"{path}.{key}" if path else key
        yield from _misplaced(child, child_path, form, admits)


def _names_case_by_reference(parent: BaseModel, field_name: str) -> bool:
    """The object of a ``Join``, ``Ignore``, ``Leave`` or ``Offer`` (AKM-03-004)."""
    return (
        field_name == "object_"
        and isinstance(parent, as_Activity)
        and str(parent.type_) in CASE_NAMING_ACTIVITY_TYPES
    )


def _is_case_invitation_target(parent: BaseModel, field_name: str) -> bool:
    """The ``target`` of an ``Invite`` of an actor (MV-10-002).

    The invitee is the ``Invite``'s ``object``, an inline actor: its profile,
    or an actor reference carrying exactly its ``id`` and ``type``
    (AKM-05-017).  An ``Invite`` whose object is anything else is no case
    invitation.  That includes an embargo invitation's ``EmbargoEvent``, and
    a bare URI or ``Link``, which may name the terms of an embargo
    invitation (ADR-0123): rehydration can resolve it to an ``EmbargoEvent``
    after this check has run, so it never makes a stub's place (#5895).
    """
    if field_name != "target" or not isinstance(parent, as_Activity):
        return False
    if str(parent.type_) != "Invite":
        return False
    invitee = getattr(parent, "object_", None)
    return isinstance(invitee, as_Actor | CoreActor)


def refuse_misplaced_case_reference(activity: as_Activity) -> None:
    """Refuse *activity* when a case reference sits where a case is carried.

    Raises:
        VultronParseValidationError: Naming the activity and each slot.
    """
    misplaced = list(
        _misplaced(
            activity,
            "",
            as_VulnerabilityCaseReference,
            _names_case_by_reference,
        )
    )
    if misplaced:
        raise VultronParseValidationError(
            f"activity {activity.id_!r}: a VulnerabilityCase carrying only"
            f" its id and type at {', '.join(misplaced)} names the case;"
            " only the object of a Join, Ignore, Leave or Offer may name a"
            " case by reference, and anywhere else the case is carried whole"
            " (AKM-03-004)"
        )


def refuse_misplaced_case_stub(activity: as_Activity) -> None:
    """Refuse *activity* when a case stub sits outside a case invitation.

    Raises:
        VultronParseValidationError: Naming the activity and each slot.
    """
    misplaced = list(
        _misplaced(
            activity,
            "",
            as_VulnerabilityCaseStub,
            _is_case_invitation_target,
        )
    )
    if misplaced:
        raise VultronParseValidationError(
            f"activity {activity.id_!r}: a VulnerabilityCaseStub at"
            f" {', '.join(misplaced)}; a case stub is permitted only as the"
            " target of an Invite whose object is the inline actor it invites"
            " to the case, or of that Invite carried inline in its Accept or"
            " Reject; anywhere else name the case by its URI (MV-10-002)"
        )


__all__ = ["refuse_misplaced_case_reference", "refuse_misplaced_case_stub"]
