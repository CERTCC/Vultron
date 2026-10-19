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
2. **Store the plan** — when the act commits entries after its own, stores
   the entries it owes, each record activity built and sealed, as case
   bookkeeping (``PendingEmbargoEntries``, CLP-07-014).
3. **Commit** — commits each entry in order.  An entry whose activity is
   already committed (a received act's own entry, intake, ADR-0111) has no
   commit step.
4. **Apply** — saves the case file the trial produced: every change whose
   entry committed, and no other.  When a commit fails, the changes of the
   entries committed before it are saved and the failure is raised, so no
   change is ever made without its entry (CLP-07-013).  The plan is removed
   once every entry has committed and the case file is saved.

A failed commit leaves the plan stored.  The next CASE_MANAGER embargo run
on the case finishes it before any guard reads a consent row
(``owed_entries.finish_owed_embargo_entries``, from
``FinishOwedEmbargoEntriesNode``): when the act's own entry is in the
ledger it commits the owed entries unchanged and in order, and applies
them; when it is not, it discards the plan (CLP-07-015, ADR-0146).

The trial is the result: a replica applying the same entries through the same
function reaches the same case file (CM-23-016).

A **received** act's own entry is committed by intake before this helper runs
(ADR-0111), so its trial must also run earlier, as a guard: call
:func:`trial_apply` on :func:`read_embargo_case_file`'s result in the guard
phase, before the guarded commit, so a refused step refuses the act and no
entry is committed for it.  The helper then repeats the trial, which passes
unless the case changed in between, and commits the consequence entries.  Call it from a BT node's
``update()``, never from a use case's ``execute()`` (CLP-10-020).
"""

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

# The case-file read and save live outside this package so the replica copy
# frame (sync/nodes/embargo_copy_effect.py) can import them without loading
# the embargo package, whose nodes import that frame; re-exported here.
from vultron.core.behaviors.embargo_case_file import (
    read_embargo_case_file,
    save_case_file,
)
from vultron.core.behaviors.sync.commit_tree import commit_emitted_activity
from vultron.core.models.embargo_apply import (
    ConsentRowChange,
    ConsentRowVerb,
    EmbargoCaseFile,
    EmbargoChange,
    apply_embargo_change,
)
from vultron.core.models.embargo_consent_event_types import (
    CREATE_EMBARGO_CONSENT_EVENT_TYPE,
    UPDATE_EMBARGO_CONSENT_EVENT_TYPE,
)
from vultron.core.models.pending_embargo_entries import (
    PendingEmbargoEntries,
    PlannedEmbargoEntryRecord,
    RecordedEntryActivity,
)
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.sync_helpers import recorded_entries_for_case
from vultron.errors import VultronBTInternalError

if TYPE_CHECKING:
    from vultron.core.ports.sync_activity import SyncActivityPort
    from vultron.core.ports.trigger_activity import TriggerActivityPort

logger = logging.getLogger(__name__)

#: Storage table of the stored plans (:class:`PendingEmbargoEntries`).
PLAN_TYPE = "PendingEmbargoEntries"


@dataclass(frozen=True)
class RecordedActivity:
    """The CASE_MANAGER's own record activity for one entry, built and sealed.

    *blob* is the sealed body the entry's snapshot is, verbatim; committing
    it again lands on the same entry (ID-04-004).
    """

    activity_id: str
    event_type: str
    actor_id: str
    blob: str

    def planned(
        self, change: EmbargoChange | None
    ) -> PlannedEmbargoEntryRecord:
        """This activity as the stored plan's entry carrying *change*."""
        return PlannedEmbargoEntryRecord(
            change=change,
            recorded=RecordedEntryActivity(
                activity_id=self.activity_id,
                event_type=self.event_type,
                activity_json=self.blob,
            ),
        )


@dataclass(frozen=True)
class PlannedEmbargoEntry:
    """One entry the CASE_MANAGER has decided to commit, and what it changes.

    *change* is what applying the entry writes; ``None`` for an act whose own
    activity changes no embargo object, such as an ``Accept`` of an embargo
    Invite, whose consent row follows as its own entry.  *commit* commits the entry,
    raising when it does not commit (``RuntimeError`` from
    :func:`~vultron.core.behaviors.sync.commit_tree.commit_emitted_activity`,
    or a ``VultronError`` when it cannot be built); ``None`` when the entry is
    already committed, as a received act's own entry is, or when the act's
    own entry carries the change.

    *record* builds the CASE_MANAGER's own record activity for the entry
    (:func:`recorded_entry`): with it, a later run can commit the entry
    unchanged when this run's commit fails (CLP-07-015).  An entry with a
    *commit* and no *record* (an act's own entry, which may also be sent)
    cannot be finished by a later run, so it may only be the act's own
    entry.  *entry_id* is the ``log_object_id`` the act's entry commits,
    and *event_type* its ``event_type`` when that object may also be the
    object of other entries; both name the act in the stored plan.
    """

    change: EmbargoChange | None
    commit: Callable[[], Any] | None = None
    record: Callable[[], RecordedActivity] | None = None
    entry_id: str | None = None
    event_type: str | None = None


def trial_apply(
    case_file: EmbargoCaseFile, changes: Sequence[EmbargoChange | None]
) -> list[EmbargoCaseFile]:
    """The case file after each of *changes*, applied in order to a copy.

    A ``None`` change (an entry that changes no embargo object) leaves the
    case file as the change before it left it.

    Raises:
        VultronEntryRefusedError: a change does not apply; nothing is
            written, and *case_file* is left as it was.
    """
    states: list[EmbargoCaseFile] = []
    current = case_file
    for change in changes:
        if change is not None:
            current = apply_embargo_change(current, change)
        states.append(current)
    return states


@dataclass(frozen=True)
class _Act:
    """The act's own entry, as a plan names it, and the entries after it."""

    entry_id: str | None
    event_type: str | None
    change: EmbargoChange | None
    owed: Sequence[PlannedEmbargoEntry]


def _act_and_owed(
    entries: Sequence[PlannedEmbargoEntry], committed_act: str | None
) -> _Act:
    """The act's entry (``log_object_id``, ``event_type``) and the entries after it.

    With *committed_act* the act's entry is already in the ledger, so every
    planned entry follows it.  Otherwise the act's entry is the first planned
    entry with a commit.
    """
    if committed_act is not None:
        return _Act(committed_act, None, None, entries)
    index = next(
        (i for i, entry in enumerate(entries) if entry.commit is not None),
        None,
    )
    if index is None:
        return _Act(None, None, None, [])
    act = entries[index]
    owed = entries[index + 1 :]
    if act.entry_id is not None:
        return _Act(act.entry_id, act.event_type, act.change, owed)
    if act.record is not None and any(e.commit is not None for e in owed):
        built = act.record()
        return _Act(built.activity_id, built.event_type, act.change, owed)
    return _Act(None, None, act.change, owed)


def _plan(
    datalayer: CasePersistence,
    case_id: str,
    entries: Sequence[PlannedEmbargoEntry],
    committed_act: str | None,
) -> PendingEmbargoEntries | None:
    """The record of the entries owed after the act's own; ``None`` when none.

    Builds and seals each owed entry's record activity, so the record holds
    exactly what this run will commit (ADR-0146).

    Raises:
        VultronBTInternalError: an owed entry has no record activity a later
            run could commit, or the act's entry is not named.
    """
    act = _act_and_owed(entries, committed_act)
    act_id, owed = act.entry_id, act.owed
    if not any(entry.commit is not None for entry in owed):
        return None
    if act_id is None:
        raise VultronBTInternalError(
            f"an embargo act on case '{case_id}' owes entries after its own,"
            " but its own entry names no ledger object"
        )
    records: list[PlannedEmbargoEntryRecord] = []
    authors: set[str] = set()
    for entry in owed:
        if entry.commit is None:
            if entry.change is not None:
                records.append(PlannedEmbargoEntryRecord(change=entry.change))
            continue
        if entry.record is None:
            raise VultronBTInternalError(
                f"an entry the embargo act '{act_id}' on case '{case_id}'"
                " commits after its own has no record activity, so a later"
                " run could not finish it (CLP-07-015)"
            )
        built = entry.record()
        authors.add(built.actor_id)
        records.append(built.planned(entry.change))
    if len(authors) != 1:
        raise VultronBTInternalError(
            f"the entries the embargo act '{act_id}' on case '{case_id}'"
            f" commits after its own name {sorted(authors)} as their author;"
            " the CASE_MANAGER authors them all"
        )
    ledger = recorded_entries_for_case(case_id=case_id, dl=datalayer)
    return PendingEmbargoEntries.for_act(
        case_id=case_id,
        act_id=act_id,
        act_event_type=act.event_type,
        # Only an entry after today's tail is this run's act, so an earlier
        # entry naming the same object is never taken for it.
        act_committed_after=(
            None
            if committed_act is not None
            else (ledger[-1].log_index if ledger else -1)
        ),
        act_change=act.change,
        author_id=authors.pop(),
        entries=records,
    )


def commit_then_save(
    datalayer: CasePersistence,
    before: EmbargoCaseFile,
    entries: Sequence[PlannedEmbargoEntry],
    states: Sequence[EmbargoCaseFile],
) -> EmbargoCaseFile:
    """Commit *entries* in order, then save the case file *states* reach.

    *states* are the trial's result for *entries*, from *before*.  The save
    in ``finally`` keeps every change whose entry committed, and no other.
    """
    applied = before
    try:
        for entry, state in zip(entries, states, strict=True):
            if entry.commit is not None:
                entry.commit()
            applied = state
    finally:
        # Save what committed.  A save that fails while a commit's failure
        # is in flight chains that failure as its ``__context__``.
        save_case_file(datalayer, before, applied)
    return applied


def commit_and_apply_embargo_entries(
    datalayer: CasePersistence,
    case_id: str,
    entries: Sequence[PlannedEmbargoEntry],
    *,
    committed_act: str | None = None,
) -> EmbargoCaseFile:
    """Trial-apply *entries*, commit them in order, then apply them.

    When the act commits entries after its own, the entries it owes are
    stored (:class:`~vultron.core.models.pending_embargo_entries
    .PendingEmbargoEntries`) after the trial and before the first commit,
    and removed once every entry has committed and the case file is saved.
    A run that fails part-way leaves the record, and the next CASE_MANAGER
    embargo run on the case finishes the act from it
    (:func:`~vultron.core.behaviors.embargo.owed_entries
    .finish_owed_embargo_entries`, CLP-07-015).

    *committed_act* is the ``log_object_id`` of the act's own entry when it
    is already in the ledger (a received act, committed by intake,
    ADR-0111; an Invite committed by an earlier run); every planned entry
    then follows it.  ``None``: the act's own entry is the first planned
    entry with a commit.

    Returns the case file as saved.

    Raises:
        VultronEntryRefusedError: the trial refused an entry; nothing was
            committed, stored or saved.
        VultronNotFoundError: *datalayer* holds no case *case_id*.
        VultronBTInternalError: an entry owed after the act's own cannot be
            finished by a later run; nothing was committed or saved.
        Exception: whatever an entry's commit raised; the changes of the
            entries committed before it are saved first.
    """
    before = read_embargo_case_file(datalayer, case_id)
    states = trial_apply(before, [entry.change for entry in entries])
    plan = _plan(datalayer, case_id, entries, committed_act)
    if plan is not None:
        datalayer.save(plan)
    applied = commit_then_save(datalayer, before, entries, states)
    if plan is not None:
        datalayer.delete(PLAN_TYPE, plan.id_)
    return applied


def recorded_entry(
    *,
    datalayer: CaseOutboxPersistence,
    actor_id: str,
    case_id: str,
    change: EmbargoChange | None,
    event_type: str,
    build: Callable[[], tuple[str, str]],
    sync_port: "SyncActivityPort | None" = None,
) -> PlannedEmbargoEntry:
    """A CASE_MANAGER record entry: built and sealed once, then committed.

    *build* returns ``(activity_id, sealed_blob)`` for an activity addressed
    to nobody, authored by *actor_id*, whose id is derived, so a re-run
    rebuilds the same one.  The entry carries its record activity, so a
    later run can commit it unchanged when this run's commit fails
    (``owed_entries.finish_owed_embargo_entries``).  *sync_port*, when given, fans
    the entry out to the case's participants; a node inside a tree that
    carries one may leave it unset, and the nested commit inherits the
    tree's.
    """
    built: list[RecordedActivity] = []

    def _record() -> RecordedActivity:
        if not built:
            activity_id, blob = build()
            built.append(
                RecordedActivity(
                    activity_id=activity_id,
                    event_type=event_type,
                    actor_id=actor_id,
                    blob=blob,
                )
            )
        return built[0]

    def _commit() -> None:
        activity = _record()
        commit_emitted_activity(
            datalayer=datalayer,
            actor_id=actor_id,
            case_id=case_id,
            activity_id=activity.activity_id,
            activity_blob=activity.blob,
            event_type=event_type,
            sync_port=sync_port,
        )

    return PlannedEmbargoEntry(change=change, commit=_commit, record=_record)


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
    (the CASE_MANAGER) before the act's first commit
    (:func:`recorded_entry`).  *cause_id* names the act the change follows;
    an ``Update``'s id derives from it and the row, so a re-run commits the
    entry its first run committed (ID-04-004).  *sync_port* is as for
    :func:`recorded_entry`.
    """
    # Constants, not the verb map: the ledger-commit inventory resolves
    # each committed event type from its name (RSH-08-004).
    if change.verb == ConsentRowVerb.CREATE:
        return recorded_entry(
            datalayer=datalayer,
            actor_id=actor_id,
            case_id=case_id,
            change=change,
            event_type=CREATE_EMBARGO_CONSENT_EVENT_TYPE,
            build=lambda: trigger_activity.record_embargo_consent_created(
                row=change.row, case_id=case_id, actor=actor_id
            ),
            sync_port=sync_port,
        )
    return recorded_entry(
        datalayer=datalayer,
        actor_id=actor_id,
        case_id=case_id,
        change=change,
        event_type=UPDATE_EMBARGO_CONSENT_EVENT_TYPE,
        build=lambda: trigger_activity.record_embargo_consent_updated(
            row=change.row,
            case_id=case_id,
            actor=actor_id,
            cause_id=cause_id,
        ),
        sync_port=sync_port,
    )


__all__ = [
    "PLAN_TYPE",
    "PlannedEmbargoEntry",
    "RecordedActivity",
    "commit_and_apply_embargo_entries",
    "commit_then_save",
    "consent_row_entry",
    "recorded_entry",
    "read_embargo_case_file",
    "save_case_file",
    "trial_apply",
]
