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

"""The CASE_MANAGER's own note on a case, committed and attached (#4829).

A note the CASE_MANAGER writes for a participant — the RSH-06-004 RM-anomaly
clarification, the CSB-18 diagnostic, the CM-16-016 reinforcing-suggestion
note — is case content, and so is a note its own add-note trigger posts.  The CASE_MANAGER does not send it as a direct
``Add(Note)``: a participant's note handler refuses any ``Add(Note)`` it is
not the CASE_MANAGER for (HP-01-005), a replica changes only from the
ledger (CLP-07-013), and its own handler refuses an ``Add(Note)`` whose note
it already holds (HP-08-006).  It records the note as its own act instead
(CLP-10-001): it builds the ``Add(Note)`` carrying the note inline,
addressed to nobody, commits its sealed blob as an ``add_note_to_case``
entry, then attaches the note to its case.  The ``Announce(CaseLedgerEntry)``
fan-out is the delivery, and each replica attaches the note from the entry
(``ApplyNoteFromLedgerNode``, SYNC-02-002).

Every active participant sees such a note, not only the one it is for.  A
private message outside the case record is not implemented (#4885).
"""

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import ClassVar, cast

from py_trees.common import Status

from vultron.core.behaviors.case_manager_commit import (
    _CommitCaseManagerActivityBase,
)
from vultron.core.behaviors.note.attach import attach_note
from vultron.core.behaviors.state_write_capable import StateWriteCapable
from vultron.core.models.events.base import MessageSemantics


@dataclass(frozen=True)
class CaseManagerNote:
    """The text of one note the CASE_MANAGER writes on a case."""

    name: str
    content: str
    in_reply_to: str | None = None


class _CommitCaseManagerNoteBase(
    _CommitCaseManagerActivityBase, StateWriteCapable
):
    """Commit the CASE_MANAGER's own note as ``add_note_to_case``, then attach it.

    Subclasses supply :meth:`_compose`, which returns the note the case is
    owed, or ``None`` when none is (the node then succeeds and writes
    nothing).  The commit follows the base class: a failed commit raises and
    the note is not attached (CLP-07-013).

    A state writer: the attach changes the case's ``notes``.  Its own entry
    records that change, so the factory admits it as a refusal effect, the
    one state writer it does (CLP-10-022).

    ``_BEST_EFFORT`` marks a note the protocol asks for at SHOULD level
    (RSH-06-004, CSB-18): a missing trigger-activity port or a commit the
    ledger refuses is logged at WARNING and the node succeeds, so the note
    never undoes the work it describes (``notes/bt-pitfalls.md`` §
    "SHOULD-Level Emission Nodes Must Always Return SUCCESS").  An internal
    error (:class:`~vultron.errors.VultronBTInternalError`) still propagates
    (ADR-0095).
    """

    _BEST_EFFORT: ClassVar[bool] = False

    def __init__(self, case_id: str, name: str | None = None) -> None:
        super().__init__(
            case_id=case_id,
            semantic_type=MessageSemantics.ADD_NOTE_TO_CASE.value,
            notify_participants=False,
            name=name,
        )
        self._composed: CaseManagerNote | None = None
        self._note_id: str | None = None
        self._note_blob: str | None = None
        self._entry_committed = False

    def _compose(self) -> CaseManagerNote | None:
        """Return the note the case is owed, or ``None``."""
        raise NotImplementedError

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        self._entry_committed = False
        self._composed = self._compose()
        if self._composed is None:
            return Status.SUCCESS
        if not self._BEST_EFFORT:
            return super().update()
        if self.trigger_activity_factory is None:
            return self._skip("no TriggerActivityPort")
        try:
            return super().update()
        except RuntimeError as exc:
            if self._entry_committed:
                # The entry exists, so this is no refused commit to log as
                # "not recorded": the BT bridge reports it as internal.
                raise
            # The ledger refused the commit, so nothing was attached.
            return self._skip(str(exc))

    def _skip(self, reason: str) -> Status:
        """Log that the SHOULD-level note was not recorded, and succeed."""
        assert self._composed is not None
        self.logger.warning(
            "%s: note '%s' not recorded on case '%s': %s",
            self.name,
            self._composed.name,
            self._case_id,
            reason,
        )
        return Status.SUCCESS

    def _build(self, to: list[str] | None) -> tuple[str, str]:
        assert self.trigger_activity_factory is not None
        assert self._composed is not None
        assert self.actor_id is not None
        actor_id = self.actor_id
        note_id, note_blob = self.trigger_activity_factory.create_note(
            name=self._composed.name,
            content=self._composed.content,
            context_id=self._case_id,
            attributed_to=self.actor_id,
            in_reply_to=self._composed.in_reply_to,
        )
        self._note_id = note_id
        self._note_blob = note_blob
        return self.trigger_activity_factory.add_note_to_case(
            note_id=note_id, case_id=self._case_id, actor=actor_id, to=to
        )

    def _record(
        self, activity_id: str, send_and_commit: Callable[[], None]
    ) -> None:
        # Attached once its entry commits, as a replica attaches it from the
        # entry (CLP-07-013, ADR-0124).
        send_and_commit()
        self._entry_committed = True
        assert self.datalayer is not None
        case, failure = self._require_case(self._case_id)
        if failure is not None:
            raise RuntimeError(
                f"{self.name}: case '{self._case_id}' vanished after its"
                f" '{self._semantic_type}' entry committed"
            )
        attach_note(self.datalayer, case, cast(str, self._note_id))
        self.logger.info(
            "%s: recorded note '%s' (%s) on case '%s' as its own '%s' entry",
            self.name,
            self._note_id,
            self._composed.name if self._composed else "",
            self._case_id,
            self._semantic_type,
        )


class CommitRequestedCaseManagerNoteNode(_CommitCaseManagerNoteBase):
    """Commit a note the CASE_MANAGER's add-note trigger was asked to post.

    The CASE_MANAGER does not send itself the ``Add(Note)``: its own handler
    would find the note already stored and refuse it (HP-08-006).  The note
    is recorded as its own entry instead, like every other note it writes.

    Writes ``note_id``, ``note_dict`` and ``activity_blob`` to *result_out*
    for the trigger's result.
    """

    def __init__(
        self,
        case_id: str,
        note: CaseManagerNote,
        result_out: dict,
        name: str | None = None,
    ) -> None:
        super().__init__(case_id=case_id, name=name)
        self._note = note
        self.result_out = result_out

    def _compose(self) -> CaseManagerNote:
        return self._note

    def _build(self, to: list[str] | None) -> tuple[str, str]:
        activity_id, blob = super()._build(to)
        self.result_out["note_id"] = self._note_id
        self.result_out["note_dict"] = json.loads(cast(str, self._note_blob))
        self.result_out["activity_blob"] = blob
        return activity_id, blob


__all__ = [
    "CaseManagerNote",
    "CommitRequestedCaseManagerNoteNode",
    "_CommitCaseManagerNoteBase",
]
