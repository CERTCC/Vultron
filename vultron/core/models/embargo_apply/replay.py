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

"""Replica replay reads over an :class:`EmbargoCaseFile` (CM-23-016).

Whether a refused entry is already in place or already passed, and which
stored objects an applied entry changed.
"""

from collections.abc import Callable, Iterable, Mapping
from types import MappingProxyType

from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.embargo_apply.apply import EmbargoCaseFile
from vultron.core.models.embargo_apply.changes import (
    ConsentRowVerb,
    EmbargoChange,
    RegisterStep,
    RegisterStepKind,
)
from vultron.core.states.embargo_register import (
    FINAL_REGISTER_STATUSES,
    EmbargoRegisterStatus,
    RegisterTrigger,
    register_status_after,
    register_trigger_is_legal,
)
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
    PEC_Trigger,
    consent_after,
    consent_trigger_is_legal,
)

#: The status a register step leaves the entry it names in.
_STEP_RESULT: Mapping[RegisterStepKind, EmbargoRegisterStatus] = (
    MappingProxyType(
        {
            RegisterStepKind.PROPOSE: EmbargoRegisterStatus.PROPOSED,
            RegisterStepKind.ACTIVATE: EmbargoRegisterStatus.ACTIVE,
            RegisterStepKind.REJECT: EmbargoRegisterStatus.REJECTED,
            RegisterStepKind.TERMINATE: EmbargoRegisterStatus.TERMINATED,
            RegisterStepKind.CANCEL: EmbargoRegisterStatus.CANCELLED,
        }
    )
)


def change_is_in_place(
    case_file: EmbargoCaseFile, change: EmbargoChange
) -> bool:
    """True when *case_file* already holds what applying *change* writes.

    For a replica re-applying an entry it had applied but not yet stored
    (its case saved, the process stopped before the entry was persisted):
    the entry is then an idempotent no-op, not a refusal, as every other
    replica slot treats a re-delivered entry.  A register step is in place
    when the entry it names holds the status the step leaves it in (the
    step's other moves were saved with it); a consent row is in place when
    the participant holds exactly the carried row.  Reads only *case_file*.

    The CASE_MANAGER does not use this: its trial apply refuses an entry
    that would change nothing, so it never commits one.
    """
    case = case_file.case
    if isinstance(change, RegisterStep):
        entry = case.embargo_register_entry(change.embargo_id)
        return (
            entry is not None
            and entry.status == _STEP_RESULT[change.kind]
            and entry.termination == change.termination
        )
    participant = case_file.participants.get(change.actor_id)
    if participant is None or (
        case.actor_participant_index.get(change.actor_id) != participant.id_
    ):
        return False
    return participant.held_row(change.row.embargo_id) == change.row


def _reachable[S, T](
    start: S,
    triggers: Iterable[T],
    is_legal: Callable[[S, T], bool],
    after: Callable[[S, T], S],
) -> frozenset[S]:
    """Every state *start* reaches in one legal move or more."""
    moves = tuple(triggers)
    reached: set[S] = set()
    frontier = [start]
    while frontier:
        current = frontier.pop()
        for trigger in moves:
            if is_legal(current, trigger):
                following = after(current, trigger)
                if following not in reached:
                    reached.add(following)
                    frontier.append(following)
    return frozenset(reached)


def _register_successors(
    status: EmbargoRegisterStatus,
) -> frozenset[EmbargoRegisterStatus]:
    """Every status a register entry at *status* can reach, *status* excluded."""
    return _reachable(
        status,
        RegisterTrigger,
        register_trigger_is_legal,
        register_status_after,
    )


def _consent_successors(
    state: EmbargoConsentState,
) -> frozenset[EmbargoConsentState]:
    """Every state a consent row at *state* reaches in one move or more."""
    return _reachable(
        state, PEC_Trigger, consent_trigger_is_legal, consent_after
    )


def case_file_is_past(
    case_file: EmbargoCaseFile, change: EmbargoChange
) -> bool:
    """True when *case_file* has already moved on from what *change* writes.

    For a replica whose seed was taken after the entry (CM-23-016: the
    replica is its seed plus the entries since).  A replica seeded with the
    case still replays the ledger from genesis over that seed, so each
    effect moves forward only (ADR-0114): an entry the seed is already past
    is an idempotent no-op, not a refusal.  The caller asks only once
    :func:`apply_embargo_change` has refused the entry, so a legal move is
    always applied.

    A register step is past when the entry it names holds a status the
    step's result leads to (the register is acyclic).  A consent row is past
    when the participant already holds a row for the embargo and either the
    embargo's register entry is final (its rows were frozen after every
    change committed to them, ADR-0122), the entry is a ``Create`` (a row is
    created once), or the held state is one the carried state leads to.
    Anything else, such as a missing participant, register entry or row, is
    a real gap and stays refused.  Reads only *case_file*.
    """
    case = case_file.case
    embargo_id = (
        change.embargo_id
        if isinstance(change, RegisterStep)
        else change.row.embargo_id
    )
    entry = case.embargo_register_entry(embargo_id)
    if entry is None:
        return False
    if isinstance(change, RegisterStep):
        return entry.status in _register_successors(_STEP_RESULT[change.kind])
    participant = case_file.participants.get(change.actor_id)
    if participant is None or (
        case.actor_participant_index.get(change.actor_id) != participant.id_
    ):
        return False
    held = participant.held_row(embargo_id)
    if held is None:
        return False
    return (
        entry.status in FINAL_REGISTER_STATUSES
        or change.verb == ConsentRowVerb.CREATE
        or held.state in _consent_successors(change.row.state)
    )


def changed_objects(
    before: EmbargoCaseFile, after: EmbargoCaseFile
) -> list[VulnerabilityCase | CaseParticipant]:
    """The stored objects *after* holds that differ from *before*.

    The case first, then participant records in actor order: what a caller
    persists once the entries that made the changes have committed.
    """
    objects: list[VulnerabilityCase | CaseParticipant] = []
    if after.case is not before.case:
        objects.append(after.case)
    objects.extend(
        record
        for actor_id, record in sorted(after.participants.items())
        if before.participants.get(actor_id) is not record
    )
    return objects
