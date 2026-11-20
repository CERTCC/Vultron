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

"""Parse-edge refusal of a stub Invite whose preview lacks a shown item.

A stub Invite's preview is what an invitee decides on before it may see the
case, so the protocol requires it to show some things (CM-17-010): its
``summary``, the Case Owner, and, while an embargo is in force, the
embargo's terms and the case's EM state (CM-17-002, CM-17-013).  It carries
no open embargo proposal (CM-17-014).  Every other field is the sender's
choice, so this check reads nothing else (MV-12-006).

The check runs where the preview is recognized, by its position, not in the
preview's type: the one place a case preview may sit is the ``preview`` of
the case reference an ``Invite`` names in its ``object``, wherever that
``Invite`` is carried inline (MV-10-002), and
:func:`~vultron.wire.as2.case_reference_placement.refuse_misplaced_forms`
has refused every other place first.  A later profile, such as a transfer
offer's preview, may share the type and show other things.
"""

from collections.abc import Iterator

from pydantic import BaseModel

from vultron.core.models.case_preview import invitation_preview_faults
from vultron.core.models.preview_object import PreviewObject, PreviewValue
from vultron.wire.as2.case_reference_placement import fields_at
from vultron.wire.as2.errors import VultronParseValidationError
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.objects.case_preview import as_CasePreview


def _case_previews(
    value: object, path: str
) -> Iterator[tuple[str, as_CasePreview]]:
    """Each case preview at or below *value*, with its path.

    The walk does not enter a preview: a preview holds no other preview
    (MV-10-002), and its contents are the sender's to show.
    """
    if isinstance(value, list):
        for index, item in enumerate(value):
            yield from _case_previews(item, f"{path}[{index}]")
        return
    if isinstance(value, as_CasePreview):
        yield path, value
        return
    if isinstance(value, (PreviewObject, PreviewValue)):
        return
    if not isinstance(value, BaseModel):
        return
    for _, child, child_path in fields_at(value, path):
        yield from _case_previews(child, child_path)


def refuse_unenveloped_invitation_previews(activity: as_Activity) -> None:
    """Refuse *activity* when a stub Invite's preview in it lacks, or marks,
    an item the protocol requires it to show (MV-10-007).

    Every preview is checked, so one refusal names every fault of every
    preview (EH-07-001).

    Raises:
        VultronParseValidationError: Naming the activity, each preview's
            position and each fault.
    """
    faults = [
        f"the invitation preview at {path} {fault}"
        for path, preview in _case_previews(activity, "")
        for fault in invitation_preview_faults(preview)
    ]
    if faults:
        raise VultronParseValidationError(
            f"activity {activity.id_!r}: {'; and '.join(faults)}; a stub"
            " Invite's preview shows its summary and Case Owner, and while"
            " an embargo is in force its terms and EM state, with no open"
            " proposal (CM-17-010, MV-10-007)"
        )


__all__ = ["refuse_unenveloped_invitation_previews"]
