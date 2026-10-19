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

"""Finish the embargo acts a failed commit left part-way (CLP-07-015).

:func:`~vultron.core.behaviors.embargo.copy_commit.commit_and_apply_embargo_entries`
stores the entries an act owes after its own as a
:class:`~vultron.core.models.pending_embargo_entries.PendingEmbargoEntries`
plan before its first commit, and removes it once the act is whole.  A plan
still stored is an act a failed run left part-way.
:func:`finish_owed_embargo_entries` finishes it, from
``FinishOwedEmbargoEntriesNode``: when the act's own entry is in the ledger it
commits what the plan owes, unchanged and in order, and applies it; when it is
not, the act never happened and the plan is discarded (ADR-0146).

The plan is case bookkeeping (CLP-07-014): it is read only to commit what was
already decided, never to decide a case-file value.  Call from a BT node's
``update()``, never from a use case's ``execute()`` (CLP-10-020).
"""

import logging
from collections.abc import Callable, Sequence
from functools import partial
from typing import Any

from vultron.core.behaviors.embargo.copy_commit import (
    PLAN_TYPE,
    PlannedEmbargoEntry,
    commit_then_save,
    read_embargo_case_file,
    trial_apply,
)
from vultron.core.behaviors.sync.commit_tree import commit_emitted_activity
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.embargo_apply import (
    EmbargoCaseFile,
    change_is_in_place,
)
from vultron.core.models.pending_embargo_entries import PendingEmbargoEntries
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.sync_helpers import recorded_entries_for_case
from vultron.errors import VultronBTInternalError, VultronEntryRefusedError

logger = logging.getLogger(__name__)


def open_embargo_plans(
    datalayer: CasePersistence, case_id: str
) -> list[PendingEmbargoEntries]:
    """The stored plans of embargo acts on *case_id* not yet finished."""
    return sorted(
        (
            plan
            for plan in datalayer.list_objects(PLAN_TYPE)
            if isinstance(plan, PendingEmbargoEntries)
            and plan.case_id == case_id
        ),
        key=lambda plan: plan.id_,
    )


def _act_entry(
    plan: PendingEmbargoEntries, ledger: Sequence[CaseLedgerEntry]
) -> CaseLedgerEntry | None:
    """The ledger entry of *plan*'s act, or ``None`` when it never committed.

    An act this run committed is the first matching entry after the ledger
    tail the plan recorded, so an earlier entry naming the same object (an
    earlier expiry of the same Invite) is never taken for it.
    """
    for entry in ledger:
        if (
            plan.act_committed_after is not None
            and entry.log_index <= plan.act_committed_after
        ):
            continue
        if entry.log_object_id == plan.act_id and (
            plan.act_event_type is None
            or str(entry.event_type) == plan.act_event_type
        ):
            return entry
    return None


def _owed_entries(
    datalayer: CaseOutboxPersistence,
    plan: PendingEmbargoEntries,
    case_file: EmbargoCaseFile,
    recorded: set[tuple[str, str]],
) -> list[PlannedEmbargoEntry]:
    """The planned entries still to commit or apply, rebuilt from *plan*.

    An entry already committed is not committed again, and a change already
    in *case_file* is not applied again; the act's own change, committed with
    its entry, comes first when the case file lacks it.  Each commit is the
    sealed body the plan stored, unchanged.
    """
    owed: list[PlannedEmbargoEntry] = []
    if plan.act_change is not None and not change_is_in_place(
        case_file, plan.act_change
    ):
        # The act's entry is committed (the caller checked), so its change
        # is applied with no commit of its own.
        owed.append(PlannedEmbargoEntry(change=plan.act_change))
    for item in plan.entries:
        change = (
            item.change
            if item.change is not None
            and not change_is_in_place(case_file, item.change)
            else None
        )
        commit: Callable[[], Any] | None = None
        activity = item.recorded
        if activity is not None and (
            (activity.activity_id, activity.event_type) not in recorded
        ):
            commit = partial(
                commit_emitted_activity,
                datalayer=datalayer,
                actor_id=plan.author_id,
                case_id=plan.case_id,
                activity_id=activity.activity_id,
                activity_blob=activity.activity_json,
                event_type=activity.event_type,
            )
        if change is not None or commit is not None:
            owed.append(PlannedEmbargoEntry(change=change, commit=commit))
    return owed


def _finish(
    datalayer: CaseOutboxPersistence,
    plan: PendingEmbargoEntries,
    ledger: Sequence[CaseLedgerEntry],
) -> int:
    """Commit and apply what *plan* still owes; return how many entries.

    Raises:
        VultronBTInternalError: an owed entry no longer applies.
    """
    recorded = {
        (entry.log_object_id, str(entry.event_type)) for entry in ledger
    }
    before = read_embargo_case_file(datalayer, plan.case_id)
    owed = _owed_entries(datalayer, plan, before, recorded)
    if owed:
        try:
            states = trial_apply(before, [entry.change for entry in owed])
        except VultronEntryRefusedError as exc:
            raise VultronBTInternalError(
                f"the entries embargo act '{plan.act_id}' on case"
                f" '{plan.case_id}' still owes no longer apply: {exc}"
            ) from exc
        commit_then_save(datalayer, before, owed, states)
    return len(owed)


def finish_owed_embargo_entries(
    datalayer: CaseOutboxPersistence, case_id: str, actor_id: str
) -> list[PendingEmbargoEntries]:
    """Finish every embargo act on *case_id* that a failed commit left open.

    For each stored plan, in the ledger order of its act: when the act's own
    entry is in the ledger, commit the entries the plan still owes,
    unchanged and in their planned order, and apply them through the one
    apply function; when it is not, the act never happened, and the plan is
    discarded with nothing committed (CLP-07-015, ADR-0146).  *actor_id* is
    the executing CASE_MANAGER, who authored the plan's entries; it alone
    finishes or discards one.  Returns the plans handled.

    Raises:
        VultronBTInternalError: a plan was authored by another actor, or an
            owed entry no longer applies to the case; the plan is kept.
        Exception: whatever a commit raised; the plan is kept, and the
            changes of the entries committed before it are saved.
    """
    plans = open_embargo_plans(datalayer, case_id)
    for plan in plans:
        if plan.author_id != actor_id:
            raise VultronBTInternalError(
                f"the plan of embargo act '{plan.act_id}' on case"
                f" '{case_id}' was authored by '{plan.author_id}', not by"
                f" the executing CASE_MANAGER '{actor_id}'"
            )
    ledger = recorded_entries_for_case(case_id=case_id, dl=datalayer)
    located = [(plan, _act_entry(plan, ledger)) for plan in plans]
    # A plan whose act never committed owes nothing; the rest are finished
    # in the order their acts were committed.
    for plan, act in located:
        if act is None:
            logger.info(
                "Discarding the plan of embargo act '%s' on case '%s': its"
                " own entry was never committed, so it owes nothing"
                " (CLP-07-015)",
                plan.act_id,
                case_id,
            )
            datalayer.delete(PLAN_TYPE, plan.id_)
    committed = sorted(
        ((plan, act) for plan, act in located if act is not None),
        key=lambda pair: pair[1].log_index,
    )
    for plan, _ in committed:
        count = _finish(
            datalayer,
            plan,
            recorded_entries_for_case(case_id=case_id, dl=datalayer),
        )
        datalayer.delete(PLAN_TYPE, plan.id_)
        logger.info(
            "Finished embargo act '%s' on case '%s': %d owed entr(ies)"
            " committed or applied (CLP-07-015)",
            plan.act_id,
            case_id,
            count,
        )
    return plans


__all__ = ["finish_owed_embargo_entries", "open_embargo_plans"]
