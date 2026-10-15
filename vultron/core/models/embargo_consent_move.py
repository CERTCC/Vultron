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

"""The consent row a trigger leaves, as a row change an entry can carry.

The CASE_MANAGER decides each consent-row change before it commits it
(ADR-0124): :func:`consent_row_move` names the row one ``PEC_Trigger`` leaves,
as the :class:`~vultron.core.models.embargo_apply.ConsentRowChange` that the
CASE_MANAGER's ``Update(EmbargoConsent)`` entry carries, or that applies what
an actor's own activity states (CLP-07-013).  It writes nothing: the change
is applied through
:func:`~vultron.core.models.embargo_apply.apply_embargo_change`.

Two activities state an agreement themselves, so the same rule runs on the
CASE_MANAGER and on every replica, on the same case file at the same ledger
position, and both write the same row (CM-23-016):

- :func:`owner_agreement` — the case owner's
  ``Accept(EmbargoEvent, target=Case)`` is its agreement to the embargo it
  activates; a ``DECLINED`` row moves too, since activating is the owner
  changing its answer (MSM-07-008).
- :func:`joiner_agreement` — an invitee's ``Accept`` of the stub Invite
  agrees to the embargo in force; a ``DECLINED`` row is left as it is, as
  seeding never overrides an answer the participant gave (CM-10-001).

Reads only the case file: no id is minted beyond the row's derived one, no
clock is read and no store is read.
"""

from vultron.core.models._helpers import _as_id
from vultron.core.models.embargo_apply import (
    ConsentRowChange,
    ConsentRowVerb,
    EmbargoCaseFile,
)
from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.states.embargo_register import FINAL_REGISTER_STATUSES
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
    PEC_Trigger,
    consent_after,
    consent_trigger_is_legal,
)


def consent_row_move(
    case_file: EmbargoCaseFile,
    actor_id: str,
    embargo_id: str,
    trigger: PEC_Trigger,
) -> ConsentRowChange | None:
    """The ``Update`` *trigger* makes to *actor_id*'s row for *embargo_id*.

    ``None`` when the move is not made: the case file holds no participant
    record for *actor_id*, or no row for *embargo_id*; the register holds no
    entry for it, or a final one (ADR-0122); or *trigger* is not legal from
    the row's state (CM-18-003).  A move out of ``INVITED`` drops the
    invitation's deadline (CM-28-013).
    """
    participant = case_file.participants.get(actor_id)
    if participant is None:
        return None
    held = participant.held_row(embargo_id)
    entry = case_file.case.embargo_register_entry(embargo_id)
    if (
        held is None
        or entry is None
        or entry.status in FINAL_REGISTER_STATUSES
        or not consent_trigger_is_legal(held.state, trigger)
    ):
        return None
    return ConsentRowChange(
        verb=ConsentRowVerb.UPDATE,
        row=EmbargoConsent(
            embargo_id=embargo_id,
            state=consent_after(held.state, trigger),
            attributed_to=actor_id,
        ),
    )


def owner_agreement(
    case_file: EmbargoCaseFile, embargo_id: str
) -> ConsentRowChange | None:
    """The case owner's ``AGREED`` row its activation of *embargo_id* states.

    *case_file* is the case as the ``ACTIVATE`` step leaves it.  ``None``
    when the owner's row already reads ``AGREED``, or the case file holds no
    record of the owner (ADR-0087).
    """
    owner_id = _as_id(case_file.case.attributed_to)
    if owner_id is None:
        return None
    return consent_row_move(case_file, owner_id, embargo_id, PEC_Trigger.AGREE)


def joiner_agreement(
    case_file: EmbargoCaseFile, actor_id: str
) -> ConsentRowChange | None:
    """The ``AGREED`` row an invitee's ``Accept`` of the stub Invite states.

    Its agreement to the embargo in force (CM-10-001).  ``None`` with no
    embargo in force, when the row already reads ``AGREED``, or when it
    reads ``DECLINED``: only the participant's own answer to the embargo
    changes a decline (CM-18-003).
    """
    case = case_file.case
    embargo_id = case.active_embargo_id
    if embargo_id is None:
        return None
    participant = case_file.participants.get(actor_id)
    held = participant.held_row(embargo_id) if participant else None
    if held is not None and held.state == EmbargoConsentState.DECLINED:
        return None
    return consent_row_move(case_file, actor_id, embargo_id, PEC_Trigger.AGREE)


__all__ = ["consent_row_move", "joiner_agreement", "owner_agreement"]
