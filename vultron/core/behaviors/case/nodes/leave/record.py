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

"""Ledger recording of the CASE_MANAGER's own RM closure transitions.

Separate module from :mod:`.advance` because applying a state change to the
local store and recording it as a canonical ``CaseLedgerEntry`` are different
concerns — and conflating them is what let ISSUE-2505 happen: the advance
existed, the record did not.

Per CM-23-002 step 2, CM-23-005, ADR-0051.
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
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.participant_status import (
    ParticipantStatus,
    participant_status_rm_state,
)
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.states.rm import RM, rm_closure_path
from vultron.enums.roles import CVDRole

logger = logging.getLogger(__name__)


class CommitCaseActorRMClosedEntryNode(DataLayerActionWithPorts):
    """Record the Case Actor's own RM closure transitions in the ledger.

    :class:`AdvanceCaseActorToRMClosedNode` writes the transitions to the Case
    Actor's *own* store and nothing more.  CM-23-005 requires every CASE_MANAGER
    RM transition to be recorded as a ``CaseLedgerEntry``, and this node is that
    record: it commits one ``add_participant_status_to_participant`` entry for
    each status the closure wrote and fans it out, so every replica observes the
    terminal state instead of inferring it.  A closure from *Valid* writes two
    statuses, ``V → D → C`` (RMB-14-005), so it records two entries, in order.

    Why the replicas cannot infer it. ``close_case`` names the *departing* actor
    in ``payloadSnapshot.actor``, and the Case Actor never sends itself a
    ``Leave``, so :class:`~vultron.core.behaviors.sync.nodes.close_case_effect
    .ApplyCloseCaseFromLedgerNode` never fires for it.  ``case_fully_closed``
    is attributed to the *owner* who left, not to the Case Actor, and has no
    effect node at all.  Without this entry the CASE_MANAGER is therefore
    permanently ``RM.ACCEPTED`` on every replica and in every ledger-derived
    invariant check, which is the defect behind ISSUE-2505.

    Committed synchronously here rather than emitted as a self-addressed
    ``Add(ParticipantStatus)`` through the CLP-10-001 loopback, because
    CM-23-002 makes this the **penultimate** step and ``case_fully_closed`` the
    final entry.  Loopback delivery is an outbox background task, so it could
    not honour that ordering.

    Idempotent by construction: ``CreateLogEntryNode`` skips an entry that
    already exists for the same object, and the node no-ops when the Case Actor
    has no ``RM.CLOSED`` status to record.

    **Recording is best-effort.**  Every way this node can fail to produce the
    entry returns SUCCESS with a WARNING rather than FAILURE — see
    :meth:`_best_effort` for why.  Only the framework regime guards
    (``_require_datalayer_and_actor``, ``_require_case``) still fail, because a
    missing store or case fails ``case_fully_closed`` too and there is no
    closure left to protect.

    Per CM-23-002 step 2, CM-23-005, ADR-0051.
    """

    def __init__(
        self,
        case_actor_id: str,
        case_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_actor_id = case_actor_id
        self._case_id = case_id

    def _best_effort(self, reason: str) -> Status:
        """Log *reason* as a WARNING and return SUCCESS.

        Recording this entry must not cost the case its closure.  CM-23-002
        places this entry between the CASE_MANAGER's own advance (step 2) and
        ``case_fully_closed`` (step 3), and ``create_close_case_received_tree``
        runs those as one Sequence — so a FAILURE here skips steps 3 and 4
        entirely: the case is never recorded as fully closed and nothing fans
        out.  It is worse than a plain abort, because the enclosing
        ``OwnerOrNonOwnerEffects`` Selector reads a failed owner arm as "the
        sender is not the Case Owner" and succeeds down the non-owner path, so
        the half-closed case reports SUCCESS with an empty failure reason.

        A missing entry costs the replicas their view of *one* transition, which
        is ISSUE-2505 in miniature; a missing ``case_fully_closed`` costs every
        replica the case's terminal anchor.  The lesser loss wins, loudly.
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

    def _closure_statuses(
        self, participant: CaseParticipant
    ) -> list[ParticipantStatus]:
        """Return the statuses of the participant's latest RM closure, in order.

        The closure ends at the most recent ``RM.CLOSED`` status, walking in
        reverse so it is the one :class:`AdvanceCaseActorToRMClosedNode` just
        appended.  Its earlier rungs are the longest run of statuses that,
        read from the state before them, match
        :func:`~vultron.core.states.rm.rm_closure_path` — so a ``V → D → C``
        closure returns the DEFERRED and the CLOSED status, and a one-step
        closure returns the CLOSED status alone.  The first status is the
        bootstrap write, never a closure rung, so it is never matched as one.
        Returns an empty list when the participant has no ``RM.CLOSED``
        status.
        """
        statuses = [
            status
            for status in participant.participant_statuses
            if isinstance(status, ParticipantStatus)
        ]
        rms = [participant_status_rm_state(status) for status in statuses]
        closed_at = next(
            (i for i in reversed(range(len(rms))) if rms[i] == RM.CLOSED),
            None,
        )
        if closed_at is None:
            return []
        # Longest path first: a closure from Valid leaves ``V, D, C``, whose
        # tail ``D, C`` also reads as a one-step closure from Deferred.  A
        # DEFERRED rung recorded earlier is skipped by the commit's idempotency.
        # A window starts at index 1 or later: the status at index 0 is the
        # bootstrap write (owner.py may seed RECEIVED), and reading it as the
        # R rung of an S → R → C closure would ledger it after the fact.
        longest = max(len(rm_closure_path(source)) for source in RM)
        for first in range(max(closed_at - longest + 1, 1), closed_at + 1):
            source = rms[first - 1]
            if tuple(rms[first : closed_at + 1]) == rm_closure_path(source):
                return statuses[first : closed_at + 1]
        return [statuses[closed_at]]

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None
        assert self.actor_id is not None

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
                "no WireRenderPort — cannot render the CASE_MANAGER's"
                " RM.CLOSED ParticipantStatus snapshot, so it is not recorded"
            )

        case, failure = self._require_case(self._case_id)
        if failure is not None:
            return failure  # Regime 1: case must exist (ADR-0087)

        participant_id = case.actor_participant_index.get(self._case_actor_id)
        if participant_id is None:
            return self._best_effort(
                f"case actor '{self._case_actor_id}' not in"
                f" actor_participant_index for case '{self._case_id}'"
            )

        participant = self.datalayer.read(participant_id)
        if not isinstance(participant, CaseParticipant):
            return self._best_effort(
                f"participant '{participant_id}' for case actor not found or"
                " wrong type"
            )

        if CVDRole.CASE_MANAGER not in (participant.case_roles or []):
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
            # Quiet SUCCESS, not a warning: a participant that is not the
            # CASE_MANAGER has nothing to record here, which is ordinary, not a
            # miss.  The tree reaches this node with ``case_actor_id`` set to
            # whoever received the Leave, so this is the check that makes that
            # assumption explicit rather than inherited from addressing.
            self.logger.debug(
                "%s: receiving actor '%s' is not the CASE_MANAGER for case"
                " '%s' — no canonical entry to author",
                self.name,
                self._case_actor_id,
                self._case_id,
            )
            return Status.SUCCESS

        closure = self._closure_statuses(participant)
        if not closure:
            # AdvanceCaseActorToRMClosedNode runs immediately before this node
            # and fails if it cannot write, so reaching here means the write
            # landed somewhere this store cannot see. Nothing to record.
            self.logger.debug(
                "%s: case actor '%s' has no RM.CLOSED ParticipantStatus"
                " to record — no-op",
                self.name,
                self._case_actor_id,
            )
            return Status.SUCCESS

        for status in closure:
            reason = self._commit_status(status, participant)
            if reason is not None:
                return self._best_effort(reason)

        self.logger.info(
            "%s: recorded case actor '%s' RM closure (%s) as canonical ledger"
            " entries for case '%s' (CM-23-005, ADR-0051)",
            self.name,
            self._case_actor_id,
            " -> ".join(
                participant_status_rm_state(status).name for status in closure
            ),
            self._case_id,
        )
        return Status.SUCCESS

    def _commit_status(
        self, status: ParticipantStatus, participant: CaseParticipant
    ) -> str | None:
        """Commit one closure status as a canonical ledger entry.

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
                f"RM.{rm_name} ParticipantStatus for case actor"
                f" '{self._case_actor_id}' has no id_"
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
                f"could not commit the CASE_MANAGER's RM.{rm_name} entry for"
                f" case '{self._case_id}' (best-effort):"
                f" {result.feedback_message}"
            )
        return None
