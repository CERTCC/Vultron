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

1. **Trial apply** — reads the case file and applies every entry's change
   to a copy through the one apply function
   (:func:`~vultron.core.models.embargo_apply.apply_embargo_change`).  A
   refusal (the register invariants, the EM check, or a starting-state check)
   raises :class:`~vultron.errors.VultronEntryRefusedError` before anything
   is committed or saved.
2. **Commit** — commits each entry in order.  An entry whose activity is
   already committed (a received act's own entry, committed by the guarded
   commit before this node runs) has no commit step.
3. **Apply** — saves the case file the trial produced.

All three run in one DataLayer transaction, so no other writer changes the
case between the trial and the commit.

The act is atomic: every entry, the activities and outbox rows each commit
writes, and the case-file changes they carry commit together, or, when any
step raises, none of them is written (CLP-07-015, ADR-0146).  A tree whose
later nodes commit more of the act's consequences (the stub re-issue, a
proposal's relay) runs this node and them in one
:class:`~vultron.core.behaviors.act_transaction.ActTransaction`, which this
helper's transaction joins.  A received tree's ``ActTransaction`` also holds
the guarded commit of the act's own entry (ADR-0151), so a failure here
removes that entry too.  No failure leaves part of an act for a later run to
finish.

The trial is the result: a replica applying the same entries through the same
function reaches the same case file (CM-23-016).

A **received** act's trial must also run earlier, as a guard: call
:func:`trial_apply` on :func:`read_embargo_case_file`'s result in the guard
phase, before the guarded commit, so a refused step refuses the act and no
entry is committed for it.  The helper then repeats the trial, which passes
unless the case changed in between, and commits the consequence entries.
Call it from a BT node's ``update()``, never from a use case's ``execute()``
(CLP-10-020).
"""

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
from vultron.core.models.embargo_consent_semantic_types import (
    CREATE_EMBARGO_CONSENT_SEMANTIC_TYPE,
    UPDATE_EMBARGO_CONSENT_SEMANTIC_TYPE,
)
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.ports.case_persistence import CasePersistence

if TYPE_CHECKING:
    from vultron.core.ports.sync_activity import SyncActivityPort
    from vultron.core.ports.trigger_activity import TriggerActivityPort


@dataclass(frozen=True)
class PlannedEmbargoEntry:
    """One entry the CASE_MANAGER has decided to commit, and what it changes.

    *change* is what applying the entry writes; ``None`` for an act whose own
    activity changes no embargo object, such as an ``Accept`` of an embargo
    Invite, whose consent row follows as its own entry.  *commit* commits the entry,
    raising when it does not commit (``RuntimeError`` from
    :func:`~vultron.core.behaviors.sync.commit_tree.commit_emitted_activity`,
    or a ``VultronError`` when it cannot be built); ``None`` when the entry is
    already committed, as a received act's own entry is.
    """

    change: EmbargoChange | None
    commit: Callable[[], Any] | None = None


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


def commit_and_apply_embargo_entries(
    datalayer: CasePersistence,
    case_id: str,
    entries: Sequence[PlannedEmbargoEntry],
) -> EmbargoCaseFile:
    """Trial-apply *entries*, then commit and apply them as one transaction.

    The entries are one act and its consequences, in commit order, such as
    an act's own entry followed by the consent rows it changes, or several
    acts that must land together.  Returns the case file as saved.

    The read, the trial, every commit and the save run in one
    ``datalayer.transaction()``.  Inside an
    :class:`~vultron.core.behaviors.act_transaction.ActTransaction` it is
    part of the enclosing act, so a later node's failure rolls it back too,
    and in a received tree so does the act's own entry (ADR-0151).

    Raises:
        VultronEntryRefusedError: the trial refused an entry; nothing was
            committed or saved.
        VultronNotFoundError: *datalayer* holds no case *case_id*.
        Exception: whatever an entry's commit or the save raised; nothing
            the transaction wrote is kept.
    """
    with datalayer.transaction():
        before = read_embargo_case_file(datalayer, case_id)
        states = trial_apply(before, [entry.change for entry in entries])
        for entry in entries:
            if entry.commit is not None:
                entry.commit()
        applied = states[-1] if states else before
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
    on_commit: Callable[[dict[str, Any]], None] | None = None,
) -> PlannedEmbargoEntry:
    """The CASE_MANAGER's own entry for one consent row it creates or changes.

    Its activity is ``Create(EmbargoConsent)`` or ``Update(EmbargoConsent)``
    carrying the row in full, built through *trigger_activity* as *actor_id*
    (the CASE_MANAGER) when the entry commits.  *cause_id* names the act the
    change follows; an ``Update``'s id derives from it and the row, so a
    re-run commits the entry its first run committed (ID-04-004).
    *sync_port*, when given, fans the entry out to the case's participants;
    a node inside a tree that carries one may leave it unset, and the nested
    commit inherits the tree's.  *on_commit*, when given, is called with the
    committed snapshot, so a caller can report the activity it committed.
    """

    def _commit() -> dict[str, Any]:
        # Constants, not the verb map: the ledger-commit inventory resolves
        # each committed semantic type from its name (RSH-08-004).
        if change.verb == ConsentRowVerb.CREATE:
            semantic_type = CREATE_EMBARGO_CONSENT_SEMANTIC_TYPE
            activity_id, blob = (
                trigger_activity.record_embargo_consent_created(
                    row=change.row, case_id=case_id, actor=actor_id
                )
            )
        else:
            semantic_type = UPDATE_EMBARGO_CONSENT_SEMANTIC_TYPE
            activity_id, blob = (
                trigger_activity.record_embargo_consent_updated(
                    row=change.row,
                    case_id=case_id,
                    actor=actor_id,
                    cause_id=cause_id,
                )
            )
        snapshot = commit_emitted_activity(
            datalayer=datalayer,
            actor_id=actor_id,
            case_id=case_id,
            activity_id=activity_id,
            activity_blob=blob,
            semantic_type=semantic_type,
            sync_port=sync_port,
        )
        if on_commit is not None:
            on_commit(snapshot)
        return snapshot

    return PlannedEmbargoEntry(change=change, commit=_commit)


__all__ = [
    "PlannedEmbargoEntry",
    "commit_and_apply_embargo_entries",
    "consent_row_entry",
    "read_embargo_case_file",
    "save_case_file",
    "trial_apply",
]
