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

"""Ledger recording of the RM closure transitions a Leave causes.

Separate module from :mod:`.advance` because applying a state change to the
local store and recording it as a canonical ``CaseLedgerEntry`` are different
concerns — and conflating them is what let ISSUE-2505 happen: the advance
existed, the record did not.

Per CM-23-001, CM-23-002 steps 1-2, CM-23-003, CM-23-005, ADR-0051.
"""

import json
from typing import cast

from py_trees.common import Status

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes.participant.rm_closure import (
    withdraw_closure_steps,
)
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
from vultron.core.models.participant_status import (
    ParticipantStatus,
    participant_status_rm_state,
)
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.predicates.roles import has_case_manager_role
from vultron.errors import VultronBTInternalError, VultronWiringError


class CommitRMClosureEntriesNode(DataLayerActionWithPorts, StateWriteCapable):
    """Record each RM closure step a Leave caused, one ledger entry per step.

    The advance node just before this one (:class:`~.advance
    .AdvanceParticipantToRMClosedNode` for the leaving actor,
    :class:`~.advance.AdvanceCaseActorToRMClosedNode` for the CASE_MANAGER
    itself) writes the closure to the CASE_MANAGER's *own* store and reports
    the id of each status it wrote in the shared ``closure_steps`` list.  This
    node commits one ``add_participant_status_to_participant`` entry for each
    of those statuses, in order, and fans it out.  A closure from *Valid*
    writes ``V → D → C`` (RMB-14-005), so it records two entries.

    **Why every step is its own entry.**  A replica is the case as seeded plus
    the ledger entries since (CM-23-016).  It applies these status entries
    through the ordinary participant-status effect and never works out a
    closure path from its own stored state: the ``close_case`` entry that
    records the Leave changes no RM state anywhere (CM-23-001).  A replica
    that walked the RM table instead would write a step no entry backs when
    it held an older status for the actor (#4091).  The entries are not the
    Leave's duplicate: the Leave is the act, these are the transitions the
    CASE_MANAGER wrote as its consequence (CLP-07-002).

    **Why the CASE_MANAGER's own closure needs it too.**  ``close_case`` names
    the *departing* actor, and the Case Actor never sends itself a ``Leave``.
    ``case_fully_closed`` is attributed to the *owner* who left.  Without its
    own entries the CASE_MANAGER is permanently ``RM.ACCEPTED`` on every
    replica (ISSUE-2505).

    **Attribution.**  The CASE_MANAGER authors each entry: the snapshot's
    ``actor`` is the receiving CASE_MANAGER and its ``published`` is the
    CASE_MANAGER's clock.  The status inside it is the closing actor's
    (``attributedTo``).  This is not the trap-3 case of
    ``notes/case-ledger-authority.md``: no snapshot here poses as the leaving
    actor's own act, so no claimed time is carried or invented.

    **Fan-out.**  Through the standard commit tree, to every active
    participant not at ``RM.CLOSED``, plus the closing actor itself: the
    advance has already written its ``CLOSED`` when the first of these
    entries fans out, but each entry records the closing actor's own closure,
    so the shared selection still sends it (``ledger_entry_recipients``,
    CM-23-004).  The leaving actor's replica therefore receives every step,
    the one that reaches ``RM.CLOSED`` included, and nothing after them.

    Committed synchronously here rather than emitted as a self-addressed
    ``Add(ParticipantStatus)`` through the CLP-10-001 loopback, because
    CM-23-002 requires these entries to **precede** ``case_fully_closed``, the
    owner-close write boundary after which no external act is recorded
    (CM-23-013).  Loopback delivery is an outbox background task, so it could
    not honour that ordering.

    Idempotent by construction: ``CreateLogEntryNode`` skips an entry that
    already exists for the same object (the status id), and the node no-ops
    when the advance wrote nothing (the actor was already ``RM.CLOSED``).

    **A step with no committed entry is taken back** (CLP-07-013, CM-23-001).
    The advance writes each step before this node commits it, the order
    CLP-07-013 gives a consequence, so a commit that fails leaves a step the
    ledger lacks.  On every such path the node withdraws each step not yet
    committed (:func:`~vultron.core.behaviors.case.nodes.participant
    .rm_closure.withdraw_closure_steps`) and fails: a refused commit returns
    FAILURE, a missing trigger-activity port raises
    :class:`~vultron.errors.VultronWiringError`, and a nested commit that
    reports ``internal_error`` raises
    :class:`~vultron.errors.VultronBTInternalError`.  Steps already committed
    stay, because the ledger records them.  The Leave is then not applied:
    the owner arm stops before ``case_fully_closed``, and a redelivered Leave
    walks the closure again from the state the ledger records.

    The commits skip ``CheckLedgerFreshnessNode``, as the ``case_fully_closed``
    commit does: a gapped local prefix fails that check by design
    (SYNC-10-001/002), and it must not block case closure (CM-23-002).

    Per CM-23-001, CM-23-002 steps 1-2, CM-23-003, CM-23-005, CLP-07-013,
    ADR-0051.
    """

    def __init__(
        self,
        closing_actor_id: str,
        case_id: str,
        closure_steps: list[str],
        name: str | None = None,
    ) -> None:
        """Create the node.

        Args:
            closing_actor_id: The actor whose closure is recorded: the leaving
                actor, or the CASE_MANAGER closing its own lifecycle.
            case_id: The case.
            closure_steps: The list the paired advance node fills with the id
                of each status it wrote, in order.
            name: Node name.
        """
        super().__init__(name=name or self.__class__.__name__)
        self._closing_actor_id = closing_actor_id
        self._case_id = case_id
        self._closure_steps = closure_steps
        # How many of the closure steps have a committed entry; the steps
        # after them are the ones a raise part-way must take back.
        self._steps_committed = 0

    def _withdraw(self, participant_id: str, unrecorded: list[str]) -> None:
        """Take back the *unrecorded* steps and log that they were."""
        assert self.datalayer is not None
        withdraw_closure_steps(self.datalayer, participant_id, unrecorded)
        message = (
            f"{self.name}: withdrew {len(unrecorded)} RM closure step(s) of"
            f" '{self._closing_actor_id}' on case '{self._case_id}' that the"
            " ledger does not record (CLP-07-013)"
        )
        self.logger.warning("%s", message)

    def _refuse(
        self, reason: str, participant_id: str, unrecorded: list[str]
    ) -> Status:
        """Withdraw the *unrecorded* steps, then report *reason* as FAILURE."""
        self._withdraw(participant_id, unrecorded)
        self.feedback_message = f"{self.name}: {reason}"
        self.logger.warning("%s", self.feedback_message)
        return Status.FAILURE

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None

        if not self._closure_steps:
            # The advance wrote nothing: the actor was already RM.CLOSED, or
            # the advance never ran.  Nothing to record.
            self.logger.debug(
                "%s: no closure step written for actor '%s' — no-op",
                self.name,
                self._closing_actor_id,
            )
            return Status.SUCCESS

        case, failure = self._require_case(self._case_id)
        if failure is not None:
            return failure  # Regime 1: case must exist (ADR-0087)

        participant_id = case.actor_participant_index.get(
            self._closing_actor_id
        )
        participant = (
            self.datalayer.read(participant_id) if participant_id else None
        )
        if participant_id is None or not isinstance(
            participant, CaseParticipant
        ):
            # The advance found this record to write the steps on, so it
            # vanishing in between is a fault, not a refusal: there is
            # nothing left to take the steps back from.
            raise VultronBTInternalError(
                f"{self.name}: participant record of closing actor"
                f" '{self._closing_actor_id}' on case '{self._case_id}' is"
                f" gone; its {len(self._closure_steps)} closure step(s)"
                " cannot be recorded or withdrawn"
            )

        if self.trigger_activity_factory is None:
            # The entry's snapshot is the factory-built activity's sealed blob
            # (VM-08-003), so without the port there is nothing to commit.  A
            # composition fault, not a refusal: the steps are withdrawn and
            # the fault raised (ARCH-15-001), as
            # _CommitCaseManagerActivityBase does for the closure itself.
            self._withdraw(participant_id, list(self._closure_steps))
            raise VultronWiringError(
                f"{self.name}: {TRIGGER_FACTORY_UNAVAILABLE} to build the RM"
                f" closure Add(ParticipantStatus) activities of"
                f" '{self._closing_actor_id}' on case '{self._case_id}'"
            )

        if not self._receiver_is_case_manager(case):
            # Authority gate (CLP-09-001, BT-17-005/006), which requires every
            # canonical-commit call site to reach the commit through a check
            # that the active actor holds CVDRole.CASE_MANAGER *at invocation
            # time* — explicitly "a role-based check, not an identity
            # comparison, even where the CASE_MANAGER and the role holder
            # happen to coincide today".
            #
            # ``DeclineForeignLedgerCommitNode`` inside the commit tree does not
            # satisfy that: it is a store-consistency check, not an authority one
            # (ARCH-24-005).  On a container co-hosting the CaseActor and another
            # actor, ``store_for_actor(require_same_authority=True)`` resolves for
            # the co-hosted actor, so the guard reports "not foreign" and would
            # let a non-CASE_MANAGER mint a canonical index in its own log.
            #
            # The steps the advance wrote have no entry to back them, so they
            # are withdrawn: an actor that cannot record a closure step does
            # not keep it (CLP-07-013).
            return self._refuse(
                f"receiving actor '{self.actor_id}' is not the CASE_MANAGER"
                f" for case '{self._case_id}', so it cannot author the RM"
                f" closure entries of '{self._closing_actor_id}'",
                participant_id,
                list(self._closure_steps),
            )

        # The sole try/except (BT-HELPER-01): whatever raises part-way
        # through the commits -- the factory, the snapshot, a nested crash --
        # every step not yet committed is taken back before the fault
        # propagates, so no step outlives its missing entry (CLP-07-013).
        self._steps_committed = 0
        try:
            return self._record_steps(participant_id, participant)
        except Exception:
            self._withdraw(
                participant_id,
                list(self._closure_steps)[self._steps_committed :],
            )
            raise

    def _record_steps(
        self, participant_id: str, participant: CaseParticipant
    ) -> Status:
        """Commit one entry per closure step, withdrawing any that fail.

        A refusal withdraws here; a raise is withdrawn by :meth:`update`,
        which reads :attr:`_steps_committed`.
        """
        assert self.datalayer is not None
        recorded: list[str] = []
        steps = list(self._closure_steps)
        for index, status_id in enumerate(steps):
            unrecorded = steps[index:]
            status = self.datalayer.read(status_id)
            if not isinstance(status, ParticipantStatus):
                return self._refuse(
                    f"closure step '{status_id}' of"
                    f" '{self._closing_actor_id}' not found or wrong type",
                    participant_id,
                    unrecorded,
                )
            reason = self._commit_status(status, participant)
            if reason is not None:
                return self._refuse(reason, participant_id, unrecorded)
            self._steps_committed = index + 1
            recorded.append(participant_status_rm_state(status).name)

        self.logger.info(
            "%s: recorded actor '%s' RM closure (%s) as canonical ledger"
            " entries for case '%s' (CM-23-001, CM-23-005)",
            self.name,
            self._closing_actor_id,
            " -> ".join(recorded),
            self._case_id,
        )
        return Status.SUCCESS

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
        """Commit one closure status as a canonical ledger entry.

        The snapshot is the CASE_MANAGER's own act, the factory-built
        ``Add(ParticipantStatus)`` sealed blob (``actor`` is the receiving
        CASE_MANAGER, ``published`` its clock, VM-08-003); the status it
        carries is the closing actor's.

        Idempotent: ``CreateLogEntryNode`` skips an entry that already exists
        for the same object, so a rung an earlier run recorded is not recorded
        twice.

        Returns:
            ``None`` once the entry is committed; otherwise the reason it was
            not, for :meth:`_refuse`.
        """
        assert self.datalayer is not None
        assert self.actor_id is not None

        rm_name = participant_status_rm_state(status).name
        status_id = getattr(status, "id_", None)
        if not status_id:
            return (
                f"RM.{rm_name} ParticipantStatus for"
                f" '{self._closing_actor_id}' has no id_"
            )

        assert self.trigger_activity_factory is not None
        _, blob = (
            self.trigger_activity_factory.record_participant_status_added(
                status=status,
                participant=participant,
                case_id=self._case_id,
                actor=self.actor_id,
            )
        )
        snapshot = json.loads(blob)

        result = BTBridge(
            datalayer=cast(CaseOutboxPersistence, self.datalayer)
        ).execute_with_setup(
            tree=create_commit_log_entry_tree(
                case_id=self._case_id,
                object_id=str(status_id),
                event_type="add_participant_status_to_participant",
                payload_snapshot=snapshot,
                # A gapped local prefix must not block case closure
                # (CM-23-002, SYNC-10-001/002), as for case_fully_closed.
                check_freshness=False,
            ),
            actor_id=self.actor_id,
        )
        if result.internal_error:
            # A crash in the nested commit is our fault, not a refusal: carry
            # the nested bridge's classification across the hop rather than
            # report it as a refused commit (CONCERN-3019, #4113; the same
            # idiom as the settle step).
            raise VultronBTInternalError(
                f"{self.name}: nested commit of the RM.{rm_name} entry of"
                f" '{self._closing_actor_id}' for case '{self._case_id}'"
                f" failed: {result.feedback_message}"
            )
        if result.status != Status.SUCCESS:
            return (
                f"could not commit the RM.{rm_name} entry of"
                f" '{self._closing_actor_id}' for case '{self._case_id}':"
                f" {result.feedback_message}"
            )
        return None
