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

"""Ledger recording of the participant statuses a CASE_MANAGER act wrote.

Every change the CASE_MANAGER makes to the case file is committed as its own
entry carrying the changed object in full (CLP-07-013, ADR-0124).  When a
received act moves a participant's RM state — a report verdict, an engagement
decision, a reply to the full-case Invite, a Leave's closure — the act's own
entry records the act, and each ``ParticipantStatus`` the CASE_MANAGER wrote as
its consequence follows as its own ``add_participant_status_to_participant``
entry, built from the very object it stored.  A replica copies that status,
id and times included, and derives nothing (CM-23-016).

:class:`CommitParticipantStatusEntriesNode` is that recording step.  The
writer just before it reports the id of each status it wrote in a shared list;
this node commits one entry per id, in order.  Both run inside the received
act's ``ActTransaction``, so a status whose entry does not commit is rolled
back with the rest of the act (CLP-07-015).
"""

import json
from typing import cast

from py_trees.common import Status

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.helpers import (
    TRIGGER_FACTORY_UNAVAILABLE,
    DataLayerActionWithPorts,
)
from vultron.core.behaviors.state_write_capable import StateWriteCapable
from vultron.core.behaviors.sync.commit_tree import (
    create_commit_log_entry_tree,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.participant_status import (
    ParticipantStatus,
    participant_status_rm_state,
)
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.predicates.roles import has_case_manager_role
from vultron.errors import VultronBTInternalError, VultronWiringError

#: ``semantic_type`` of the entry recording one participant status.
ADD_PARTICIPANT_STATUS_SEMANTIC_TYPE = (
    MessageSemantics.ADD_PARTICIPANT_STATUS_TO_PARTICIPANT.value
)


class CommitParticipantStatusEntriesNode(
    DataLayerActionWithPorts, StateWriteCapable
):
    """Commit one ledger entry per status the writer before it wrote.

    The writer (``CreateParticipantStatusNode`` with ``written_ids``, or a
    closure advance node) writes each status to the CASE_MANAGER's *own*
    store and appends its id to *status_ids*.  This node commits one
    ``add_participant_status_to_participant`` entry for each, in order, and
    fans it out.  The entry's snapshot is the factory-built
    ``Add(ParticipantStatus)`` sealed blob (VM-08-003): its ``actor`` is the
    receiving CASE_MANAGER, its ``published`` the CASE_MANAGER's clock, and the
    status it carries is the subject's (``attributedTo``) exactly as stored.

    **A status with no committed entry is not kept** (CLP-07-013).  The
    writer writes each status before this node commits it, and both run in
    the received act's ``ActTransaction``, so a commit that fails takes the
    status back with the rest of the act (CLP-07-015): a refused commit
    returns FAILURE, a missing trigger-activity port raises
    :class:`~vultron.errors.VultronWiringError`, and a nested commit that
    reports ``internal_error`` raises
    :class:`~vultron.errors.VultronBTInternalError`.

    No-op SUCCESS when the writer wrote nothing (the subject already held the
    state, RSH-08-002).  Idempotent by construction: ``CreateLogEntryNode``
    skips an entry that already exists for the same object (the status id).

    Authority: the receiver must hold ``CVDRole.CASE_MANAGER`` on the case at
    invocation time (CLP-09-001, BT-17-005); otherwise the node fails.

    Per CLP-07-013, CM-23-016, ADR-0124.
    """

    #: Whether each commit runs ``CheckLedgerFreshnessNode``.  Only the
    #: case-closure commits turn it off (CM-23-002, SYNC-10-001/002).
    check_freshness: bool = True

    def __init__(
        self,
        subject_actor_id: str,
        case_id: str | None,
        status_ids: list[str],
        name: str | None = None,
    ) -> None:
        """Create the node.

        Args:
            subject_actor_id: The actor whose statuses are recorded.
            case_id: The case, or ``None`` for the case the first written
                status names as its ``context`` (the writer resolved it from
                ``/case_id``).
            status_ids: The list the paired writer fills with the id of each
                status it wrote, in order.
            name: Node name.
        """
        super().__init__(name=name or self.__class__.__name__)
        self._subject_actor_id = subject_actor_id
        self._given_case_id = case_id
        self._case_id = case_id or ""
        self._status_ids = status_ids

    def _refuse(self, reason: str) -> Status:
        """Fail with *reason*; the act's transaction takes the statuses back."""
        self.feedback_message = f"{self.name}: {reason}"
        self.logger.warning("%s", self.feedback_message)
        return Status.FAILURE

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None

        if not self._status_ids:
            self.logger.debug(
                "%s: no status written for actor '%s' — no-op",
                self.name,
                self._subject_actor_id,
            )
            return Status.SUCCESS

        self._case_id = self._given_case_id or self._written_case_id()
        case, failure = self._require_case(self._case_id)
        if failure is not None:
            return failure  # Regime 1: case must exist (ADR-0087)

        participant_id = case.actor_participant_index.get(
            self._subject_actor_id
        )
        participant = (
            self.datalayer.read(participant_id) if participant_id else None
        )
        if participant_id is None or not isinstance(
            participant, CaseParticipant
        ):
            # The writer found this record to write the statuses on, so it
            # vanishing in between is a fault, not a refusal.
            raise VultronBTInternalError(
                f"{self.name}: participant record of '{self._subject_actor_id}'"
                f" on case '{self._case_id}' is gone; its"
                f" {len(self._status_ids)} status(es) cannot be recorded"
            )

        if self.trigger_activity_factory is None:
            # The entry's snapshot is the factory-built activity's sealed blob
            # (VM-08-003), so without the port there is nothing to commit.  A
            # composition fault, not a refusal (ARCH-15-001).
            raise VultronWiringError(
                f"{self.name}: {TRIGGER_FACTORY_UNAVAILABLE} to build the"
                f" Add(ParticipantStatus) activities of"
                f" '{self._subject_actor_id}' on case '{self._case_id}'"
            )

        if not self._receiver_is_case_manager(case):
            # Authority gate (CLP-09-001, BT-17-005/006): a role-based check
            # at invocation time.  ``DeclineForeignLedgerCommitNode`` inside
            # the commit tree is a store-consistency check, not an authority
            # one (ARCH-24-005).  An actor that cannot record a status does
            # not keep it (CLP-07-013).
            return self._refuse(
                f"receiving actor '{self.actor_id}' is not the CASE_MANAGER"
                f" for case '{self._case_id}', so it cannot author the status"
                f" entries of '{self._subject_actor_id}'"
            )
        return self._record(participant)

    def _record(self, participant: CaseParticipant) -> Status:
        """Commit one entry per status, failing at the first that does not."""
        assert self.datalayer is not None
        recorded: list[str] = []
        for status_id in self._status_ids:
            status = self.datalayer.read(status_id)
            if not isinstance(status, ParticipantStatus):
                return self._refuse(
                    f"status '{status_id}' of '{self._subject_actor_id}'"
                    " not found or wrong type"
                )
            reason = self._commit_status(status, participant)
            if reason is not None:
                return self._refuse(reason)
            recorded.append(participant_status_rm_state(status).name)

        self.logger.info(
            "%s: recorded actor '%s' status(es) (%s) as canonical ledger"
            " entries for case '%s' (CLP-07-013)",
            self.name,
            self._subject_actor_id,
            " -> ".join(recorded),
            self._case_id,
        )
        return Status.SUCCESS

    def _written_case_id(self) -> str:
        """The case the first written status records itself in."""
        assert self.datalayer is not None
        status = self.datalayer.read(self._status_ids[0])
        context = getattr(status, "context", None)
        if not isinstance(status, ParticipantStatus) or not context:
            raise VultronBTInternalError(
                f"{self.name}: status '{self._status_ids[0]}' of"
                f" '{self._subject_actor_id}' names no case"
            )
        return str(context)

    def _receiver_is_case_manager(self, case: VulnerabilityCase) -> bool:
        """Whether the receiving actor holds CASE_MANAGER on *case* now."""
        assert self.datalayer is not None
        assert self.actor_id is not None
        participant_id = case.actor_participant_index.get(self.actor_id)
        if participant_id is None:
            return False
        participant = self.datalayer.read(participant_id)
        return isinstance(participant, CaseParticipant) and (
            has_case_manager_role(list(participant.case_roles or []))
        )

    def _commit_status(
        self, status: ParticipantStatus, participant: CaseParticipant
    ) -> str | None:
        """Commit one status as a canonical ledger entry.

        Returns:
            ``None`` once the entry is committed; otherwise the reason it was
            not, for :meth:`_refuse`.
        """
        assert self.datalayer is not None
        assert self.actor_id is not None
        assert self.trigger_activity_factory is not None

        rm_name = participant_status_rm_state(status).name
        _, blob = (
            self.trigger_activity_factory.record_participant_status_added(
                status=status,
                participant=participant,
                case_id=self._case_id,
                actor=self.actor_id,
            )
        )
        result = BTBridge(
            datalayer=cast(CaseOutboxPersistence, self.datalayer)
        ).execute_with_setup(
            tree=create_commit_log_entry_tree(
                case_id=self._case_id,
                object_id=status.id_,
                semantic_type=ADD_PARTICIPANT_STATUS_SEMANTIC_TYPE,
                payload_snapshot=json.loads(blob),
                check_freshness=self.check_freshness,
            ),
            actor_id=self.actor_id,
        )
        if result.internal_error:
            # A crash in the nested commit is our fault, not a refusal: carry
            # the nested bridge's classification across the hop (#4113).
            raise VultronBTInternalError(
                f"{self.name}: nested commit of the RM.{rm_name} entry of"
                f" '{self._subject_actor_id}' for case '{self._case_id}'"
                f" failed: {result.feedback_message}"
            )
        if result.status != Status.SUCCESS:
            return (
                f"could not commit the RM.{rm_name} entry of"
                f" '{self._subject_actor_id}' for case '{self._case_id}':"
                f" {result.feedback_message}"
            )
        return None
