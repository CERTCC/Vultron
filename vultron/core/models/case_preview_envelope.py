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

"""What a stub Invite's case preview shows of the embargo and status, and
what it lacks of the envelope (CM-17-010, ADR-0217).

The readers find the current status and the in-force register entry a
preview shows; :func:`invitation_preview_faults` names each item an
invitation preview must show and does not.  The sender's cut
(:meth:`~vultron.core.models.case_preview.CasePreview.from_case`) and the
receiver's parse edge both run it, so one envelope is judged on both sides.
"""

from typing import TYPE_CHECKING

from vultron.core.models.preview_object import PreviewObject
from vultron.core.models.redacted import Redacted
from vultron.core.models.wire_keys import wire_key
from vultron.core.states.em import EM, is_em_embargo_active
from vultron.core.states.embargo_register import EmbargoRegisterStatus

if TYPE_CHECKING:
    from vultron.core.models.case_preview import CasePreview


def preview_current_status(preview: CasePreview) -> PreviewObject | None:
    """The current status *preview* shows, the last of its ``caseStatuses``.

    ``None`` when the preview shows no status, marks the list or the status,
    or names it by id.
    """
    statuses = preview.case_statuses
    if not isinstance(statuses, list) or not statuses:
        return None
    current = statuses[-1]
    return current if isinstance(current, PreviewObject) else None


def preview_em_state(preview: CasePreview) -> EM | None:
    """The case's EM state *preview*'s current status carries (CM-17-013).

    ``None`` when the preview carries no current status, gives it by id, or
    withholds the status or its EM state with a marker.

    A module function, not a property: a replica slot's reach is checked by
    attribute name (``test_participant_replica_slots_copy.py``), and a
    property named for the status would read as the case's own.
    """
    status = preview_current_status(preview)
    state = getattr(getattr(status, "em", None), "state", None)
    return state if isinstance(state, EM) else None


def _shown_register(preview: CasePreview) -> list[object]:
    """The registered embargoes *preview* shows; none when it marks the list."""
    register = preview.embargo_register
    return list(register) if isinstance(register, list) else []


def _entry_status(embargo: object) -> object:
    """The status *embargo* shows, or ``None`` when it shows none."""
    return getattr(embargo, "status", None)


def preview_in_force_embargo(preview: CasePreview) -> PreviewObject | None:
    """The in-force embargo *preview* shows (CM-17-002).

    The registered embargo whose status is ``ACTIVE`` (ADR-0202).  ``None``
    when the preview shows no register, marks it, or shows no ``ACTIVE``
    embargo.
    """
    return next(
        (
            embargo
            for embargo in _shown_register(preview)
            if isinstance(embargo, PreviewObject)
            and _entry_status(embargo) == EmbargoRegisterStatus.ACTIVE
        ),
        None,
    )


def invitation_preview_faults(preview: CasePreview) -> list[str]:
    """What *preview*, as a stub Invite's preview, lacks or shows wrongly.

    An invitation preview shows its ``summary`` and the Case Owner, never as
    a marker (CM-17-010).  While an embargo is in force it also shows the
    embargo's terms, as an ``ACTIVE`` embargo in ``embargoRegister``, and the
    EM state of its current status (CM-17-002,
    CM-17-013).  The embargo is in force when the current status's EM state
    is ``ACTIVE`` or ``REVISE``, or when the register shows an ``ACTIVE``
    embargo.  The register carries no open proposal (CM-17-014), and the
    preview carries no ledger position or ledger entry (CM-17-025): the two
    preview fields only a projection fills (ADR-0219).

    Each fault names its position under the preview, so a receiver can name
    where it is (MV-10-007).  The type already refuses a marked
    ``summary``.  Every other field is the sender's choice, so a fault is
    never about it (MV-12-006).

    Returns:
        One phrase per fault, in field order; empty when there is none.
    """
    faults: list[str] = []
    if preview.summary is None:
        faults.append("lacks 'summary'")
    owner = preview.attributed_to
    if owner is None:
        faults.append("lacks the Case Owner at 'attributedTo'")
    elif isinstance(owner, Redacted):
        faults.append("marks the Case Owner at 'attributedTo' Redacted")
    em_state = preview_em_state(preview)
    embargo = preview_in_force_embargo(preview)
    if (em_state is not None and is_em_embargo_active(em_state)) or (
        embargo is not None
    ):
        faults.extend(_in_force_faults(preview, em_state, embargo))
    for index, shown in enumerate(_shown_register(preview)):
        if _entry_status(shown) == EmbargoRegisterStatus.PROPOSED:
            faults.append(
                f"carries an open embargo proposal at"
                f" 'embargoRegister[{index}]' (CM-17-014)"
            )
    for field, value in (
        ("ledger_position", preview.ledger_position),
        ("ledger_entries", preview.ledger_entries),
    ):
        if value is not None:
            key = wire_key(field)
            faults.append(
                f"carries the case's bookkeeping at {key!r} (CM-17-025)"
            )
    return faults


def _in_force_faults(
    preview: CasePreview, em_state: EM | None, embargo: PreviewObject | None
) -> list[str]:
    """What *preview* lacks of an embargo in force (CM-17-002, CM-17-013)."""
    faults: list[str] = []
    if em_state is None:
        faults.append(
            "shows an embargo in force but lacks or marks the EM state at"
            " 'caseStatuses[-1].em'"
        )
    if isinstance(preview.embargo_register, Redacted):
        faults.append(
            "marks 'embargoRegister' Redacted while an embargo is in force"
        )
    elif embargo is None:
        faults.append(
            "lacks the in-force entry in 'embargoRegister' while an embargo"
            " is in force"
        )
    return faults


__all__ = [
    "invitation_preview_faults",
    "preview_current_status",
    "preview_em_state",
    "preview_in_force_embargo",
]
