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

"""Turn the CASE_MANAGER's embargo decision into the entries that record it.

The CASE_MANAGER makes every lifecycle decision before it commits (ADR-0124,
CLP-07-013).  The decision is still the ``EmbargoLifecycle`` operation it
always ran, but it runs against a :class:`StagedCasePersistence`, so its
writes are held back and never reach the store.  :func:`decide_on_stage`
reads what the operation would have written and turns it into an
:class:`EmbargoDecision`:

- the **register step** the act's own activity carries (a
  :class:`~vultron.core.models.embargo_apply.RegisterStep`, named by the
  caller), kept only when the operation moved the register; and
- one **consent-row change** per row the operation brought into existence
  (``Create(EmbargoConsent)``) or changed (``Update(EmbargoConsent)``), in
  roster order, each carrying the row in full (ADR-0122).

It then checks that the decision is the whole of what the operation wrote:
the entries, trial-applied through the one apply function, must reach the
case file the operation staged, and the operation must have staged nothing
but the case and its participant records.  A mismatch is a fault in the
caller (an operation whose effect no entry carries), never a refusal, so it
raises :class:`~vultron.errors.VultronBTInternalError`.

:func:`commit_and_apply_decision` then commits the act's entry (or relies on
intake having committed it, for a received act, ADR-0111), then each
consent-row entry, and applies them by copying, through
:func:`~vultron.core.behaviors.embargo.copy_commit.commit_and_apply_embargo_entries`.
Call both from a BT node's ``update()``, never from a use case's
``execute()`` (CLP-10-020).
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from vultron.core.behaviors.embargo.copy_commit import (
    PlannedEmbargoEntry,
    commit_and_apply_embargo_entries,
    consent_row_entry,
    read_embargo_case_file,
    trial_apply,
)
from vultron.core.models.embargo_apply import (
    ConsentRowChange,
    ConsentRowVerb,
    EmbargoCaseFile,
    RegisterStep,
)
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.services.embargo_lifecycle.staged_persistence import (
    StagedCasePersistence,
)
from vultron.errors import VultronBTInternalError, VultronEntryRefusedError

if TYPE_CHECKING:
    from vultron.core.ports.trigger_activity import TriggerActivityPort


#: ``result_out`` key a deciding lifecycle node leaves its
#: :class:`EmbargoDecision` under, for the commit node that records it.
EMBARGO_DECISION_KEY = "embargo_decision"


@dataclass(frozen=True)
class EmbargoDecision:
    """What one embargo act changes, decided and not yet written.

    *step* is the register step the act's own activity carries, ``None`` when
    the act moves no register entry; *rows* the consent rows it changes, one
    CASE_MANAGER entry each, in commit order.
    """

    case_id: str
    step: RegisterStep | None
    rows: tuple[ConsentRowChange, ...]

    @property
    def changes_nothing(self) -> bool:
        """True when the act writes nothing to the case file."""
        return self.step is None and not self.rows


def consent_row_changes(
    before: EmbargoCaseFile, after: EmbargoCaseFile
) -> list[ConsentRowChange]:
    """One change per consent row *after* holds that *before* does not.

    A row *before* lacks is a ``Create``; a row that differs is an
    ``Update``.  Participants come in the order the case's roster indexes
    them, and each participant's rows in the order the record holds them.

    Raises:
        VultronBTInternalError: *after* holds a participant record *before*
            does not; an embargo act creates no participant.
    """
    changes: list[ConsentRowChange] = []
    # ``participants`` holds the indexed records in roster order.
    for actor_id, record in after.participants.items():
        prior = before.participants.get(actor_id)
        if prior is None:
            raise VultronBTInternalError(
                f"the decision created a participant record for '{actor_id}'"
                f" on case '{after.case.id_}'; an embargo act creates none"
            )
        for row in record.embargo_consents:
            held = prior.held_row(row.embargo_id)
            if held == row:
                continue
            changes.append(
                ConsentRowChange(
                    verb=(
                        ConsentRowVerb.CREATE
                        if held is None
                        else ConsentRowVerb.UPDATE
                    ),
                    row=row.for_actor(actor_id),
                )
            )
    return changes


def _dumped(case_file: EmbargoCaseFile) -> tuple[Any, dict[str, Any]]:
    """*case_file* as comparable data.

    A register entry may hold its embargo inline or by id (the lifecycle
    names it by id, a ``PROPOSE`` entry carries it inline), so each is
    compared by id.
    """
    case = case_file.case
    by_id = case.model_copy(
        update={
            "embargo_register": [
                entry.model_copy(update={"embargo": entry.embargo_id})
                for entry in case.embargo_register
            ]
        }
    )
    return (
        by_id.model_dump(mode="json"),
        {
            actor_id: record.model_dump(mode="json")
            for actor_id, record in case_file.participants.items()
        },
    )


def _require_only_case_file_staged(
    staged: StagedCasePersistence, case_file: EmbargoCaseFile
) -> None:
    """Refuse a decision that wrote an object no embargo entry can carry.

    The case and the participant records its roster indexes are the case
    file the entries carry.  A participant record the case lists but does
    not index by its actor is outside it: no entry can name it, and no
    replica can copy a row onto it, so a row the lifecycle wrote there is
    left unwritten rather than refusing the act.
    """
    allowed = {case_file.case.id_} | {
        record.id_ for record in case_file.participants.values()
    }
    unindexed = {str(p) for p in case_file.case.case_participants} - allowed
    stray = [
        obj.id_
        for obj in staged.staged
        if obj.id_ not in allowed and obj.id_ not in unindexed
    ]
    if stray:
        raise VultronBTInternalError(
            f"the embargo decision on case '{case_file.case.id_}' wrote"
            f" {stray}, which no embargo entry carries"
        )


def decide_on_stage(
    datalayer: CasePersistence,
    staged: StagedCasePersistence,
    case_id: str,
    step: RegisterStep | None,
) -> EmbargoDecision:
    """The decision an operation already run against *staged* made.

    *staged* wraps *datalayer* and holds the operation's writes; nothing
    reaches *datalayer*.  *step* is the register step the act's activity
    carries, kept only when the operation moved the register.

    Raises:
        VultronBTInternalError: the entries do not carry what the operation
            wrote.
    """
    before = read_embargo_case_file(datalayer, case_id)
    decided = read_embargo_case_file(staged, case_id)
    _require_only_case_file_staged(staged, decided)
    kept_step = (
        step
        if decided.case.embargo_register != before.case.embargo_register
        else None
    )
    rows = consent_row_changes(before, decided)
    try:
        states = trial_apply(before, [kept_step, *rows])
    except VultronEntryRefusedError as exc:
        raise VultronBTInternalError(
            f"the entries recording the embargo decision on case '{case_id}'"
            f" do not apply to it: {exc}"
        ) from exc
    if _dumped(states[-1]) != _dumped(decided):
        raise VultronBTInternalError(
            f"the embargo decision on case '{case_id}' changed the case file"
            " in a way its entries do not carry"
        )
    return EmbargoDecision(case_id=case_id, step=kept_step, rows=tuple(rows))


def decide_embargo_act(
    datalayer: CasePersistence,
    case_id: str,
    decide: Callable[[CasePersistence], object],
    step: RegisterStep | None = None,
) -> EmbargoDecision:
    """Run *decide* against a staged copy of *datalayer*; return the decision.

    *decide* is the lifecycle operation, given the store to run against.
    Whatever it raises propagates, and nothing is written.

    Raises:
        VultronBTInternalError: the entries do not carry what *decide* wrote.
    """
    staged = StagedCasePersistence(datalayer)
    decide(staged)
    return decide_on_stage(datalayer, staged, case_id, step)


def commit_and_apply_decision(
    *,
    datalayer: CaseOutboxPersistence,
    decision: EmbargoDecision,
    trigger_activity: "TriggerActivityPort",
    actor_id: str,
    cause_id: str,
    act_commit: Callable[[], Any] | None = None,
) -> EmbargoCaseFile:
    """Commit the act's entry, then each consent-row entry; apply by copying.

    *act_commit* commits the act's own entry; ``None`` when intake already
    committed it (a received act, ADR-0111) or when the act has no entry of
    its own (the CASE_MANAGER's policy consent is its row's entry alone).
    *cause_id* names the act each consent-row ``Update`` follows; its id is
    derived from it and the row (ID-04-004).  *actor_id* is the executing
    CASE_MANAGER, who authors every consent-row entry.

    Raises:
        VultronEntryRefusedError: the case changed since the decision, and
            the trial refused an entry; nothing was committed or saved.
        Exception: whatever a commit raised; the changes of the entries
            committed before it are saved first.
    """
    entries: list[PlannedEmbargoEntry] = []
    if decision.step is not None or act_commit is not None:
        entries.append(
            PlannedEmbargoEntry(change=decision.step, commit=act_commit)
        )
    entries.extend(
        consent_row_entry(
            datalayer=datalayer,
            trigger_activity=trigger_activity,
            actor_id=actor_id,
            case_id=decision.case_id,
            change=row,
            cause_id=cause_id,
        )
        for row in decision.rows
    )
    return commit_and_apply_embargo_entries(
        datalayer, decision.case_id, entries
    )


def decide_commit_and_apply(
    *,
    datalayer: CaseOutboxPersistence,
    case_id: str,
    decide: Callable[[CasePersistence], object],
    trigger_activity: "TriggerActivityPort",
    actor_id: str,
    cause_id: str,
    step: RegisterStep | None = None,
    act_commit: Callable[[], Any] | None = None,
) -> EmbargoDecision:
    """Decide on a staged copy, then commit and apply; return the decision.

    :func:`decide_embargo_act` followed by
    :func:`commit_and_apply_decision`, for a node whose decision and record
    happen in one tick.  Whatever *decide* raises propagates, and nothing is
    committed or written.
    """
    decision = decide_embargo_act(datalayer, case_id, decide, step)
    commit_and_apply_decision(
        datalayer=datalayer,
        decision=decision,
        trigger_activity=trigger_activity,
        actor_id=actor_id,
        cause_id=cause_id,
        act_commit=act_commit,
    )
    return decision


__all__ = [
    "EMBARGO_DECISION_KEY",
    "EmbargoDecision",
    "commit_and_apply_decision",
    "decide_commit_and_apply",
    "consent_row_changes",
    "decide_embargo_act",
    "decide_on_stage",
]
