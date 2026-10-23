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

"""Post-mutation CaseStatus snapshot, shared across behavior domains.

:class:`EmitCaseStatusUpdateNode` commits a ``CaseStatus`` snapshot after an
EM or PXA lifecycle node mutates the case (RSH-04-002, RSH-04-003).  The
embargo trigger trees and the status trees both compose it, so it lives in this
purpose-built shared module rather than in either domain's ``nodes`` package
(BTND-04-001).  It cannot live in ``status.nodes``: that package re-exports the
lifecycle nodes that compose the embargo trigger trees, so an embargo tree
importing from it would close an import cycle (CS-05-003).

:func:`promote_pxa` is the SM-09-001 persistence-boundary promotion this node
applies.  :func:`adopted_pxa` is the case ``pxa`` after a participant's
adopted report, the union of the two sets of latches (RSH-01-003).
:func:`last_committed_case_status` is the status the node measures a change
against: a snapshot that changes neither EM nor PXA is not committed
(CLP-07-013, ADR-0152).
"""

import json
import logging
from typing import Any, cast

from py_trees.common import Status

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.helpers import DataLayerActionWithPorts
from vultron.core.behaviors.state_write_capable import StateWriteCapable
from vultron.core.behaviors.sync.commit_tree import (
    create_commit_log_entry_tree,
)
from vultron.core.models._helpers import _as_id
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.dimensions import EmDimension, PxaDimension
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.states.cs import CS_pxa
from vultron.core.sync_helpers import (
    at_stored_position,
    case_status_from_snapshot,
    sorted_case_ledger_entries,
)
from vultron.errors import VultronNotFoundError, VultronValidationError

logger = logging.getLogger(__name__)


def promote_pxa(pxa: CS_pxa) -> CS_pxa:
    """SM-09-001: promote ephemeral pX states at the persistence boundary."""
    if pxa is CS_pxa.pXa:
        return CS_pxa.PXa
    if pxa is CS_pxa.pXA:
        return CS_pxa.PXA
    return pxa


def _latch_pairs(
    current: CS_pxa, reported: CS_pxa
) -> list[tuple[str, bool, bool]]:
    """Each of P, X and A as ``(letter, set in current, set in reported)``.

    ``CS_pxa`` names spell each latch upper-case when set (``PxA``)."""
    return [
        (mine.upper(), mine.isupper(), theirs.isupper())
        for mine, theirs in zip(current.name, reported.name, strict=True)
    ]


def adopted_pxa(current: CS_pxa, reported: CaseStatus | None) -> CS_pxa:
    """The case ``pxa`` after adopting *reported* (RSH-01-003).

    P, X and A are one-way latches, so the adopted state sets every latch
    either *current* or *reported* sets, and clears none: a report that
    omits a latch the case holds still adds the ones it newly sets.  With no
    report the result is *current*.  It is promoted at the persistence
    boundary either way (SM-09-001).
    """
    if reported is None:
        return promote_pxa(current)
    union = "".join(
        letter if mine or theirs else letter.lower()
        for letter, mine, theirs in _latch_pairs(current, reported.pxa.state)
    )
    return promote_pxa(CS_pxa[union])


def latches_cleared_by(current: CS_pxa, reported: CaseStatus | None) -> str:
    """The latches *current* sets that *reported* does not, as ``"PXA"``
    letters (empty when none): what adopting *reported* ignores."""
    if reported is None:
        return ""
    return "".join(
        letter
        for letter, mine, theirs in _latch_pairs(current, reported.pxa.state)
        if mine and not theirs
    )


_ADD_CASE_STATUS = MessageSemantics.ADD_CASE_STATUS_TO_CASE.value


def last_committed_case_status(
    case_id: str, dl: CasePersistence
) -> CaseStatus | None:
    """The ``CaseStatus`` the case's last ``add_case_status_to_case`` entry
    carries, or ``None`` when *dl* holds no such entry.

    The ledger, not the case's current status, is what a change is measured
    against: the case stamps the register's EM onto its current status as
    soon as the register moves (ADR-0122), so the current status already
    shows an EM change no entry has carried yet.

    Raises:
        VultronValidationError: the last entry carries no valid
            ``CaseStatus``.  It was validated when it was committed, so this
            is a broken store, never a reason to skip (ARCH-15-001).
    """
    entries = [
        entry
        for entry in sorted_case_ledger_entries(dl, case_id)
        if entry.semantic_type == _ADD_CASE_STATUS
    ]
    if not entries:
        return None
    last = entries[-1]
    try:
        return case_status_from_snapshot(last.payload_snapshot.get("object"))
    except VultronValidationError as exc:
        raise VultronValidationError(
            f"ledger entry '{last.id_}': {exc}"
        ) from exc


def changes_case_status(
    committed: CaseStatus | None, em: EmDimension, pxa: PxaDimension
) -> bool:
    """Whether a snapshot of *em* and *pxa* differs from *committed*.

    With nothing committed yet, any snapshot is a change.
    """
    if committed is None:
        return True
    return (committed.em.state, committed.pxa.state) != (em.state, pxa.state)


class EmitCaseStatusUpdateNode(DataLayerActionWithPorts, StateWriteCapable):
    """Snapshot the post-mutation CaseStatus, commit a CaseLedgerEntry, and fan out.

    After an EM or PXA lifecycle node mutates the case state, this node:

    1. Reads the VulnerabilityCase from the DataLayer (post-mutation).
    2. Creates a new CaseStatus snapshotting the current ``em`` + ``pxa`` state.
       With ``reported_status_id`` set, the ``pxa`` also sets every P/X/A
       latch the adopted ``ParticipantStatus`` reports, clearing none
       (RSH-01-003).  A snapshot whose EM and PXA equal the last committed
       status's is no change: the node returns ``SUCCESS`` having written
       nothing (CLP-07-013, ADR-0152).
    3. Builds the CASE_MANAGER's ``Add(CaseStatus)`` through the
       trigger-activity port and commits its sealed blob as a CaseLedgerEntry
       via ``create_commit_log_entry_tree`` (VM-08-003).
    4. Persists the CaseStatus and appends it to ``case.case_statuses``.
    5. FanOutLogEntryNode (inside the commit tree) announces to participants
       when a ``sync_port`` is available on the blackboard.

    MUST NOT route through the inbox seam (RSH-04-004).
    Per RSH-04-002 (EM mutations) and RSH-04-003 (PXA mutations).

    Args:
        case_id: The case whose status is snapshotted.
        name: Node name; defaults to the class name.
        reported_status_id: The adopted ``ParticipantStatus``, read at tick
            time, whose embedded ``case_status`` reports P/X/A.  Every latch it
            sets is added to the case's, and none is cleared
            (:func:`adopted_pxa`, RSH-01-003).  ``None`` for trees that mutate
            the case before the snapshot (EM lifecycle).
    """

    def __init__(
        self,
        case_id: str | None,
        name: str | None = None,
        reported_status_id: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.reported_status_id = reported_status_id
        self._committed_status_id: str | None = None

    def _reported(self) -> CaseStatus | None:
        """The case status the adopted ``ParticipantStatus`` embeds.

        Read from the stored status the append step saved, which is the
        status as received (RSH-09-001), so a status received by reference is
        adopted too.  ``None`` when no report is named, or the status embeds
        no ``case_status`` (it reports no P/X/A).

        Raises:
            VultronNotFoundError: no ``ParticipantStatus`` is stored at
                ``reported_status_id``.  The append step saves it before
                this node runs, so its absence is a broken store, never a
                report to skip (ARCH-15-001).
        """
        if self.reported_status_id is None:
            return None
        assert self.datalayer is not None
        reported = self.datalayer.read(self.reported_status_id)
        if not isinstance(reported, ParticipantStatus):
            raise VultronNotFoundError(
                "ParticipantStatus", self.reported_status_id
            )
        return reported.case_status

    def _adopted_pxa(
        self, current: CaseStatus, reported: CaseStatus | None
    ) -> CS_pxa:
        """The snapshot's ``pxa``: *reported*'s latches added, none cleared."""
        # AC-1: pX → PX forced promotion at persistence boundary (SM-09-001)
        pxa_state = adopted_pxa(current.pxa.state, reported)
        if cleared := latches_cleared_by(current.pxa.state, reported):
            self.logger.info(
                "%s: status '%s' for case '%s' omits %s, which the case"
                " already records; kept (RSH-01-003, actor_id=%s)",
                self.name,
                self.reported_status_id,
                self.case_id,
                cleared,
                self.actor_id,
            )
        return pxa_state

    def _unchanged(self, em: EmDimension, pxa: PxaDimension) -> Status | None:
        """``SUCCESS`` when the snapshot changes nothing, else ``None``.

        A snapshot whose EM and PXA equal the last committed status's is not
        committed: a decision that changes nothing takes no entry
        (CLP-07-013, ADR-0152; #5123).  ``FAILURE`` when the committed status
        cannot be read.
        """
        assert self.case_id is not None
        assert self.datalayer is not None
        try:
            committed = last_committed_case_status(
                self.case_id, self.datalayer
            )
        except VultronValidationError as exc:
            self.feedback_message = (
                f"Cannot read the committed CaseStatus of case"
                f" '{self.case_id}': {exc}"
            )
            self.logger.exception("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        if committed is None or changes_case_status(committed, em, pxa):
            return None
        self.logger.info(
            "%s: case '%s' is still %s %s, as status '%s' records;"
            " nothing to commit (CLP-07-013, actor_id=%s)",
            self.name,
            self.case_id,
            em.state.name,
            pxa.state.name,
            committed.id_,
            self.actor_id,
        )
        return Status.SUCCESS

    def update(self) -> Status:
        if not self.case_id:
            self.feedback_message = (
                "case_id is absent — cannot snapshot CaseStatus"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None

        case, failure = self._require_case(self.case_id)
        if failure is not None:
            return failure  # Regime 1 (ADR-0087)

        # Within-tick idempotency: if this node already committed a CaseStatus
        # for this case during the current BT execution, skip the duplicate write.
        if self._committed_status_id is not None:
            existing_ids = {_as_id(s) for s in case.case_statuses}
            if self._committed_status_id in existing_ids:
                self.logger.info(
                    "%s: already committed '%s' for case '%s' — skipping"
                    " duplicate write (idempotent)",
                    self.name,
                    self._committed_status_id,
                    self.case_id,
                )
                return Status.SUCCESS

        try:
            current = case.current_status
        except (ValueError, IndexError):
            self.feedback_message = (
                f"Case '{self.case_id}' has no materialized CaseStatus"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        try:
            reported = self._reported()
        except VultronNotFoundError as exc:
            self.feedback_message = (
                f"Cannot adopt reported status into case '{self.case_id}':"
                f" {exc}"
            )
            self.logger.exception("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        em = EmDimension(state=case.em_state)
        pxa = PxaDimension(state=self._adopted_pxa(current, reported))
        if (done := self._unchanged(em, pxa)) is not None:
            return done
        new_status = CaseStatus(
            context=self.case_id,
            attributed_to=self.actor_id,
            em=em,
            pxa=pxa,
        )

        # The entry records the CASE_MANAGER's own Add(CaseStatus), built by
        # the factory and sealed; its blob is the snapshot, verbatim
        # (VM-08-003, CLP-07-013).  The status is carried inline before it is
        # persisted: it is stored only once the commit succeeds (below).
        _, blob = (
            self._require_trigger_activity_port().record_case_status_added(
                status=new_status, case_id=self.case_id, actor=self.actor_id
            )
        )
        payload: dict[str, Any] = json.loads(blob)

        commit_tree = create_commit_log_entry_tree(
            case_id=self.case_id,
            object_id=new_status.id_,
            semantic_type=MessageSemantics.ADD_CASE_STATUS_TO_CASE.value,
            payload_snapshot=payload,
        )
        result = BTBridge(
            datalayer=cast(CaseOutboxPersistence, self.datalayer)
        ).execute_with_setup(tree=commit_tree, actor_id=self.actor_id)
        if result.status != Status.SUCCESS:
            self.feedback_message = (
                f"Ledger commit failed for CaseStatus '{new_status.id_}'"
                f" in case '{self.case_id}': {result.feedback_message}"
            )
            self.logger.error("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        # Persist only after the ledger commit succeeds to avoid phantom state.
        self.datalayer.save(new_status)
        # The commit moved the stored case's ledger position (SYNC-16-005).
        case = at_stored_position(case, self.datalayer)
        case.add_case_status(new_status)
        self.datalayer.save(case)

        # Record committed ID for within-tick idempotency guard.
        self._committed_status_id = new_status.id_

        self.logger.info(
            "%s: committed CaseStatus '%s' for case '%s'",
            self.name,
            new_status.id_,
            self.case_id,
        )
        return Status.SUCCESS
