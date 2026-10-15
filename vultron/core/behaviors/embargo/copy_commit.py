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

"""Change the embargo part of a case by entries: decide, trial, commit, apply.

The CASE_MANAGER never edits its case directly (ADR-0124).  An embargo act
and its consequences reach the case file as ledger entries, one per
activity/object pair: the act's own activity, which carries any register
step, then one CASE_MANAGER ``Create`` or ``Update(EmbargoConsent)`` per
consent row the act changes (ADR-0122, CLP-07-013).  The caller **decides**
(guards, lifecycle logic and policy run before this module is reached) and
hands the result here as a list of :class:`PlannedEmbargoEntry`, in commit
order.  :func:`commit_and_apply_embargo_entries` then:

1. **Trial apply** — applies every entry's change to a copy of the case file
   through the one apply function
   (:func:`~vultron.core.models.embargo_apply.apply_embargo_change`).  A
   refusal (the register invariants, the EM check, or a starting-state check)
   raises :class:`~vultron.errors.VultronEntryRefusedError` before anything
   is committed or saved.
2. **Commit** — commits each entry in order.  An entry whose activity is
   already committed (a received act's own entry, intake, ADR-0111) has no
   commit step.
3. **Apply** — saves the case file the trial produced: every change whose
   entry committed, and no other.  When a commit fails, the changes of the
   entries committed before it are saved and the failure is raised, so no
   change is ever made without its entry (CLP-07-013).

The trial is the result: a replica applying the same entries through the same
function reaches the same case file (CM-23-016).  Call it from a BT node's
``update()``, never from a use case's ``execute()`` (CLP-10-020).
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from vultron.core.behaviors.sync.commit_tree import commit_emitted_activity
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.embargo_apply import (
    ConsentRowChange,
    ConsentRowVerb,
    EmbargoCaseFile,
    EmbargoChange,
    apply_embargo_change,
    changed_objects,
)
from vultron.core.models.embargo_consent_event_types import (
    CREATE_EMBARGO_CONSENT_EVENT_TYPE,
    UPDATE_EMBARGO_CONSENT_EVENT_TYPE,
)
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.ports.case_persistence import CasePersistence
from vultron.errors import VultronNotFoundError

if TYPE_CHECKING:
    from vultron.core.ports.sync_activity import SyncActivityPort
    from vultron.core.ports.trigger_activity import TriggerActivityPort


@dataclass(frozen=True)
class PlannedEmbargoEntry:
    """One entry the CASE_MANAGER has decided to commit, and what it changes.

    *change* is what applying the entry writes.  *commit* commits the entry,
    raising when it does not commit (``RuntimeError`` from
    :func:`~vultron.core.behaviors.sync.commit_tree.commit_emitted_activity`,
    or a ``VultronError`` when it cannot be built); ``None`` when the entry is
    already committed, as a received act's own entry is.
    """

    change: EmbargoChange
    commit: Callable[[], Any] | None = None


def read_embargo_case_file(
    datalayer: CasePersistence, case_id: str
) -> EmbargoCaseFile:
    """The case *case_id* and the participant records its roster indexes.

    Raises:
        VultronNotFoundError: *datalayer* holds no such case.
    """
    case = datalayer.read_case(case_id)
    if not isinstance(case, VulnerabilityCase):
        raise VultronNotFoundError("VulnerabilityCase", case_id)
    participants: dict[str, CaseParticipant] = {}
    for actor_id, participant_id in case.actor_participant_index.items():
        record = datalayer.read(participant_id)
        if isinstance(record, CaseParticipant):
            participants[actor_id] = record
    return EmbargoCaseFile(case=case, participants=participants)


def trial_apply(
    case_file: EmbargoCaseFile, changes: Sequence[EmbargoChange]
) -> list[EmbargoCaseFile]:
    """The case file after each of *changes*, applied in order to a copy.

    Raises:
        VultronEntryRefusedError: a change does not apply; nothing is
            written, and *case_file* is left as it was.
    """
    states: list[EmbargoCaseFile] = []
    current = case_file
    for change in changes:
        current = apply_embargo_change(current, change)
        states.append(current)
    return states


def save_case_file(
    datalayer: CasePersistence,
    before: EmbargoCaseFile,
    after: EmbargoCaseFile,
) -> None:
    """Save every object *after* changed from *before*, in one write."""
    objects = changed_objects(before, after)
    if objects:
        datalayer.save_many(list(objects))


def commit_and_apply_embargo_entries(
    datalayer: CasePersistence,
    case_id: str,
    entries: Sequence[PlannedEmbargoEntry],
) -> EmbargoCaseFile:
    """Trial-apply *entries*, commit them in order, then apply them.

    Returns the case file as saved.

    Raises:
        VultronEntryRefusedError: the trial refused an entry; nothing was
            committed or saved.
        VultronNotFoundError: *datalayer* holds no case *case_id*.
        Exception: whatever an entry's commit raised; the changes of the
            entries committed before it are saved first.
    """
    before = read_embargo_case_file(datalayer, case_id)
    states = trial_apply(before, [entry.change for entry in entries])
    applied = before
    try:
        for entry, state in zip(entries, states, strict=True):
            if entry.commit is not None:
                entry.commit()
            applied = state
    finally:
        save_case_file(datalayer, before, applied)
    return applied


def consent_row_entry(
    *,
    datalayer: CaseOutboxPersistence,
    trigger_activity: "TriggerActivityPort",
    actor_id: str,
    case_id: str,
    change: ConsentRowChange,
    cause_id: str,
    sync_port: "SyncActivityPort | None" = None,
) -> PlannedEmbargoEntry:
    """The CASE_MANAGER's own entry for one consent row it creates or changes.

    Its activity is ``Create(EmbargoConsent)`` or ``Update(EmbargoConsent)``
    carrying the row in full, built through *trigger_activity* as *actor_id*
    (the CASE_MANAGER) when the entry commits.  *cause_id* names the act the
    change follows; an ``Update``'s id derives from it and the row, so a
    re-run commits the entry its first run committed (ID-04-004).
    *sync_port*, when given, fans the entry out to the case's participants;
    a node inside a tree that carries one may leave it unset, and the nested
    commit inherits the tree's.
    """

    def _commit() -> dict[str, Any]:
        if change.verb == ConsentRowVerb.CREATE:
            event_type = CREATE_EMBARGO_CONSENT_EVENT_TYPE
            activity_id, blob = (
                trigger_activity.record_embargo_consent_created(
                    row=change.row, case_id=case_id, actor=actor_id
                )
            )
        else:
            event_type = UPDATE_EMBARGO_CONSENT_EVENT_TYPE
            activity_id, blob = (
                trigger_activity.record_embargo_consent_updated(
                    row=change.row,
                    case_id=case_id,
                    actor=actor_id,
                    cause_id=cause_id,
                )
            )
        return commit_emitted_activity(
            datalayer=datalayer,
            actor_id=actor_id,
            case_id=case_id,
            activity_id=activity_id,
            activity_blob=blob,
            event_type=event_type,
            sync_port=sync_port,
        )

    return PlannedEmbargoEntry(change=change, commit=_commit)


__all__ = [
    "PlannedEmbargoEntry",
    "commit_and_apply_embargo_entries",
    "consent_row_entry",
    "read_embargo_case_file",
    "save_case_file",
    "trial_apply",
]
