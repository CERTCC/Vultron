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

"""Apply one embargo entry to an :class:`EmbargoCaseFile` (ADR-0124).

:func:`apply_embargo_change` is the one apply function the CASE_MANAGER and
every replica share (EMB-18-006).
"""

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from types import MappingProxyType

from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.embargo_apply.changes import (
    ConsentRowChange,
    ConsentRowVerb,
    EmbargoChange,
    RegisterStep,
)
from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.states.embargo_register import (
    FINAL_REGISTER_STATUSES,
)
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
    PEC_Trigger,
    consent_after,
    consent_trigger_is_legal,
)
from vultron.errors import (
    VultronEntryRefusedError,
    VultronInvalidStateTransitionError,
)


def _frozen_participants(
    participants: Mapping[str, CaseParticipant],
) -> Mapping[str, CaseParticipant]:
    return MappingProxyType(dict(participants))


@dataclass(frozen=True)
class EmbargoCaseFile:
    """The part of the case file embargo entries change (ADR-0124).

    *case* holds the embargo register; *participants* holds the participant
    records, keyed by the actor id each is attributed to, that hold the
    consent rows.  Only these are read: the apply function reads no store.
    Applying an entry returns a new case file and never changes this one.
    """

    case: VulnerabilityCase
    participants: Mapping[str, CaseParticipant] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "participants", _frozen_participants(self.participants)
        )


def _apply_register_step(
    case_file: EmbargoCaseFile, step: RegisterStep
) -> EmbargoCaseFile:
    case = case_file.case.model_copy(deep=True)
    try:
        case.apply_embargo_register_step(
            step.changes(case), threat_signal=step.threat_signal
        )
    except VultronEntryRefusedError:
        raise
    except (VultronInvalidStateTransitionError, ValueError) as exc:
        # ValueError: the register assignment's own validation (a pydantic
        # ValidationError) refused the result, which is a refusal too.
        raise VultronEntryRefusedError(
            f"{step.kind} of embargo '{step.embargo_id}' does not apply to"
            f" case '{case.id_}': {exc}"
        ) from exc
    return replace(case_file, case=case)


def _participant_for(
    case_file: EmbargoCaseFile, change: ConsentRowChange
) -> CaseParticipant:
    case = case_file.case
    participant = case_file.participants.get(change.actor_id)
    held_id = case.actor_participant_index.get(change.actor_id)
    if participant is None or held_id != participant.id_:
        raise VultronEntryRefusedError(
            f"case '{case.id_}' holds no participant record for"
            f" '{change.actor_id}', so its consent row for embargo"
            f" '{change.row.embargo_id}' cannot be written"
        )
    return participant


def _require_open_entry(case: VulnerabilityCase, embargo_id: str) -> None:
    """Refuse a row change for an embargo the register lacks or has closed."""
    entry = case.embargo_register_entry(embargo_id)
    if entry is None:
        raise VultronEntryRefusedError(
            f"case '{case.id_}' holds no register entry for embargo"
            f" '{embargo_id}', so no consent row for it can be written"
        )
    if entry.status in FINAL_REGISTER_STATUSES:
        raise VultronEntryRefusedError(
            f"embargo '{embargo_id}' is {entry.status} on case '{case.id_}',"
            " so its consent rows accept no change (ADR-0122)"
        )


def _one_move(held: EmbargoConsentState, carried: EmbargoConsentState) -> bool:
    """True when one consent trigger moves *held* to *carried* (CM-18-003)."""
    return any(
        consent_trigger_is_legal(held, trigger)
        and consent_after(held, trigger) == carried
        for trigger in PEC_Trigger
    )


def _row_problem(
    held: EmbargoConsent | None, change: ConsentRowChange
) -> str | None:
    """Why *change* does not start from *held*, or ``None`` when it does."""
    carried = change.row
    if change.verb == ConsentRowVerb.CREATE:
        if held is not None:
            return "the participant already holds a row for it"
        if carried.state != EmbargoConsentState.UNINVITED and not _one_move(
            EmbargoConsentState.UNINVITED, carried.state
        ):
            return f"a new row cannot start {carried.state}"
        return None
    if held is None:
        return "the participant holds no row for it to update"
    if (held.state, held.rsvp_deadline) == (
        carried.state,
        carried.rsvp_deadline,
    ):
        return "the carried row changes nothing"
    if held.state == carried.state:
        # A fresh invitation's deadline on a row still waiting (CM-28-013).
        return (
            None
            if carried.state == EmbargoConsentState.INVITED
            else f"only an INVITED row's deadline changes in place, not a"
            f" {carried.state} row's"
        )
    if not _one_move(held.state, carried.state):
        return f"no consent transition moves {held.state} to {carried.state}"
    return None


def _apply_consent_row(
    case_file: EmbargoCaseFile, change: ConsentRowChange
) -> EmbargoCaseFile:
    participant = _participant_for(case_file, change)
    embargo_id = change.row.embargo_id
    _require_open_entry(case_file.case, embargo_id)
    held = participant.held_row(embargo_id)
    problem = _row_problem(held, change)
    if problem is not None:
        raise VultronEntryRefusedError(
            f"{change.verb} of '{change.actor_id}''s consent row for embargo"
            f" '{embargo_id}' does not apply: {problem}"
        )
    copied = participant.model_copy(deep=True)
    copied.copy_consent_row(change.row)
    return replace(
        case_file,
        participants={**case_file.participants, change.actor_id: copied},
    )


def apply_embargo_change(
    case_file: EmbargoCaseFile, change: EmbargoChange
) -> EmbargoCaseFile:
    """Apply one embargo entry's *change* to *case_file*; return the result.

    The one apply function for the embargo register and consent rows,
    shared by the CASE_MANAGER's trial apply and apply and by every replica
    (ADR-0124, CM-23-016, EMB-18-006).  A :class:`RegisterStep` performs the
    step the act's activity names, through
    :meth:`VulnerabilityCase.apply_embargo_register_step`, so the register
    invariants and the EM transition check hold after the entry.  A
    :class:`ConsentRowChange` writes the row it carries, after checking that
    the participant is on the case, the embargo is in the register and not
    final, and the row starts where the entry implies: a ``Create`` needs no
    row yet, an ``Update`` a held row that one consent transition (or a
    fresh deadline on an ``INVITED`` row) moves to the carried one.

    Reads only *case_file*; mints no id, reads no clock and runs no
    lifecycle logic.  *case_file* is left as it was.

    Raises:
        VultronEntryRefusedError: the entry does not apply to *case_file*.
    """
    if isinstance(change, RegisterStep):
        return _apply_register_step(case_file, change)
    return _apply_consent_row(case_file, change)
