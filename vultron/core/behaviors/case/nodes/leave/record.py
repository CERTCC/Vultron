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

import logging
from typing import cast

from py_trees.common import Status

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.ledger_snapshots import (
    build_add_participant_status_snapshot,
)
from vultron.core.behaviors.helpers import DataLayerActionWithPorts
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

logger = logging.getLogger(__name__)


class CommitRMClosureEntriesNode(DataLayerActionWithPorts):
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
    participant.  The leaving actor's own replica therefore receives every
    step, the one that reaches ``RM.CLOSED`` included (CM-23-004).

    Committed synchronously here rather than emitted as a self-addressed
    ``Add(ParticipantStatus)`` through the CLP-10-001 loopback, because
    CM-23-002 requires these entries to **precede** ``case_fully_closed``, the
    owner-close write boundary after which no external act is recorded
    (CM-23-013).  Loopback delivery is an outbox background task, so it could
    not honour that ordering.

    Idempotent by construction: ``CreateLogEntryNode`` skips an entry that
    already exists for the same object (the status id), and the node no-ops
    when the advance wrote nothing (the actor was already ``RM.CLOSED``).

    **Recording is best-effort** (CM-23-001, AC-5 of #4210).  Every way this
    node can fail to produce an entry returns SUCCESS with a WARNING rather
    than FAILURE — see :meth:`_best_effort` for why.  Only the framework regime
    guards (``_require_datalayer_and_actor``, ``_require_case``) still fail,
    because a missing store or case fails ``case_fully_closed`` too and there
    is no closure left to protect.

    Per CM-23-001, CM-23-002 steps 1-2, CM-23-003, CM-23-005, ADR-0051.
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

    def _best_effort(self, reason: str) -> Status:
        """Log *reason* as a WARNING and return SUCCESS.

        Recording an entry must not cost the case its closure (CM-23-001).
        On owner Leave, CM-23-002 places these entries between the advances
        (steps 1 and 2) and ``case_fully_closed`` (step 3), and
        ``create_close_case_received_tree`` runs those as one Sequence — so a
        FAILURE here skips steps 3 and 4 entirely: the case is never recorded
        as fully closed and nothing fans out.  It is worse than a plain abort, because the enclosing
        ``OwnerOrNonOwnerEffects`` Selector reads a failed owner arm as "the
        sender is not the Case Owner" and succeeds down the non-owner path, so
        the half-closed case reports SUCCESS with an empty failure reason.

        A missing entry costs the replicas their view of *one* transition, which
        is ISSUE-2505 in miniature; a missing ``case_fully_closed`` costs every
        replica the case's write-boundary marker.  The lesser loss wins,
        loudly.
        ``_commit_one`` in :mod:`..case_proposal_received_tree` makes the same
        call for the same event type, reserving hard failure for the
        load-bearing genesis entry.

        This is also why a gapped local ledger cannot block closure:
        ``create_commit_log_entry_tree`` opens with ``CheckLedgerFreshnessNode``,
        which fails by design on a gapped prefix (SYNC-10-001/002) — a condition
        the protocol tolerates elsewhere and must keep tolerating here.

        Logs through the **module-level** ``logger`` as well as ``self.logger``.
        ``py_trees.behaviour.Behaviour.logger`` is a ``py_trees.logging.Logger``,
        which writes to the console directly and never reaches the stdlib
        ``logging`` tree — so on its own it is invisible to deployment logs and
        CI artifacts. A silently-dropped entry is exactly what ISSUE-2505 was;
        best-effort is only defensible if the miss is actually observable.
        ``_commit_one`` uses the module logger for the same reason.
        """
        self.feedback_message = f"{self.name}: {reason}"
        logger.warning("%s", self.feedback_message)
        self.logger.warning("%s", self.feedback_message)
        return Status.SUCCESS

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

        if self.wire_render_port is None:
            # A snapshot cannot be rendered without the port, and a snapshot is
            # the whole point of the entry — so skip the entry rather than
            # commit an empty payload. Loudly: ISSUE-2505 was masked for months
            # by a silently absent wire_render_port on the genesis commit path.
            #
            # Deliberately *not* _require_wire_render_port(): elsewhere a
            # missing port is a wiring fault that raises, but this entry sits
            # inside CM-23-002's closure Sequence, and _best_effort() explains
            # why losing the entry is the lesser loss.  In a composed tree the
            # Leave's own guarded commit has already required the port, so
            # this branch is reached only when this node alone is blind to it.
            return self._best_effort(
                "no WireRenderPort — cannot render the RM closure"
                f" ParticipantStatus snapshots of '{self._closing_actor_id}',"
                " so they are not recorded"
            )

        case, failure = self._require_case(self._case_id)
        if failure is not None:
            return failure  # Regime 1: case must exist (ADR-0087)

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
            # Quiet SUCCESS, not a warning: a receiver that is not the
            # CASE_MANAGER has nothing to record here, which is ordinary, not
            # a miss.
            self.logger.debug(
                "%s: receiving actor '%s' is not the CASE_MANAGER for case"
                " '%s' — no canonical entry to author",
                self.name,
                self.actor_id,
                self._case_id,
            )
            return Status.SUCCESS

        return self._record_steps(case)

    def _record_steps(self, case: VulnerabilityCase) -> Status:
        """Commit one entry per closure step, best-effort (CM-23-001)."""
        assert self.datalayer is not None
        participant_id = case.actor_participant_index.get(
            self._closing_actor_id
        )
        if participant_id is None:
            return self._best_effort(
                f"closing actor '{self._closing_actor_id}' not in"
                f" actor_participant_index for case '{self._case_id}'"
            )
        participant = self.datalayer.read(participant_id)
        if not isinstance(participant, CaseParticipant):
            return self._best_effort(
                f"participant '{participant_id}' for closing actor"
                f" '{self._closing_actor_id}' not found or wrong type"
            )

        recorded: list[str] = []
        for status_id in self._closure_steps:
            status = self.datalayer.read(status_id)
            if not isinstance(status, ParticipantStatus):
                return self._best_effort(
                    f"closure step '{status_id}' of"
                    f" '{self._closing_actor_id}' not found or wrong type"
                )
            reason = self._commit_status(status, participant)
            if reason is not None:
                return self._best_effort(reason)
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

        The snapshot is the CASE_MANAGER's own act (``actor`` is the
        receiving CASE_MANAGER, ``published`` its clock); the status it
        carries is the closing actor's.

        Idempotent: ``CreateLogEntryNode`` skips an entry that already exists
        for the same object, so a rung an earlier run recorded is not recorded
        twice.

        Returns:
            ``None`` once the entry is committed; otherwise the reason it was
            not, for :meth:`_best_effort`.
        """
        assert self.datalayer is not None
        assert self.actor_id is not None
        assert self.wire_render_port is not None

        rm_name = participant_status_rm_state(status).name
        status_id = getattr(status, "id_", None)
        if not status_id:
            return (
                f"RM.{rm_name} ParticipantStatus for"
                f" '{self._closing_actor_id}' has no id_"
            )

        snapshot = build_add_participant_status_snapshot(
            status,
            participant,
            self.actor_id,
            self._case_id,
            self.wire_render_port,
        )

        result = BTBridge(
            datalayer=cast(CaseOutboxPersistence, self.datalayer)
        ).execute_with_setup(
            tree=create_commit_log_entry_tree(
                case_id=self._case_id,
                object_id=str(status_id),
                event_type="add_participant_status_to_participant",
                payload_snapshot=snapshot,
            ),
            actor_id=self.actor_id,
        )
        if result.status != Status.SUCCESS:
            # The reachable one: CheckLedgerFreshnessNode opens the commit tree
            # and fails on a gapped local prefix by design (SYNC-10-001/002).
            return (
                f"could not commit the RM.{rm_name} entry of"
                f" '{self._closing_actor_id}' for case '{self._case_id}'"
                f" (best-effort): {result.feedback_message}"
            )
        return None
