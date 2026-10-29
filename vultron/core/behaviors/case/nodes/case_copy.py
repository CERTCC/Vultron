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
"""BT nodes that judge a case copy by its ledger position and ask for the rest.

The guard that decides whether a copy of a case this replica already holds
may replace it (SYNC-16-006), the node that asks the CASE_MANAGER for the
entries a replacing copy is ahead of the replica's chain by (SYNC-16-007),
and the node that states the position a first copy seeded the replica at
(SYNC-17-008, ADR-0163).
:class:`~vultron.core.behaviors.case.nodes.announce.SeedAnnouncedCaseNode`
does the seed or replacement between them (ADR-0142).
"""

from typing import cast

from py_trees.common import Status
from py_trees.ports import NoDataAvailable, PortInformation

from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    DataLayerConditionWithPorts,
)
from vultron.core.behaviors.idempotency import FlaggedRepeatGuardMixin
from vultron.core.behaviors.sync.nodes.position_statement import (
    position_statement_recipient,
    stated_replica_position,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.events.actor import (
    AnnounceVulnerabilityCaseReceivedEvent,
)
from vultron.core.models.ledger_position import LedgerPosition
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.services.case_copy import (
    CaseCopyJudgement,
    CaseCopyVerdict,
    judge_case_copy,
)
from vultron.errors import VultronNotFoundError, VultronWiringError

#: Blackboard key: whether the announced copy replaces a case this replica
#: already holds, written by :class:`CaseCopyNotStaleNode` and read by
#: :class:`RequestCaseCopyBackfillNode` and
#: :class:`StateSeededLedgerPositionNode`.
CASE_COPY_REPLACES_KEY = "case_copy_replaces"


class CaseCopyNotStaleNode(
    FlaggedRepeatGuardMixin, DataLayerConditionWithPorts
):
    """Guard: a copy of a case this replica holds may replace it (SYNC-16-006).

    A replica that does not hold the case yet seeds it from any copy
    (PCR-02-003): ``SUCCESS``.  One that holds it compares the ledger
    position the copy names (SYNC-16-005) with its own
    (:func:`~vultron.core.services.case_copy.judge_case_copy`):

    - the replica is already past the position: ``FAILURE`` with ``is_stale``
      set, logged at INFO; the handler reports ``SKIPPED`` and the case is
      unchanged;
    - it holds a different entry at the position's index: ``FAILURE`` with
      ``is_conflict`` set, logged at ERROR; the handler reports ``REFUSED``
      and the case is unchanged;
    - otherwise ``SUCCESS``: the copy replaces the case.

    Every case names its position (SYNC-16-005): an ownerless one, which
    could not, is refused when it is built (ARCH-10-001).  A copy this actor
    sent itself, as the CASE_MANAGER receiving its own broadcast, is skipped
    like a stale one: its case is the copy's source (``is_stale``, INFO).

    Writes ``/case_copy_replaces`` on every ``SUCCESS``: ``True`` when the
    copy replaces a held case, ``False`` for a first seed.
    """

    _REPEAT_FLAG = "is_stale"

    OUTPUT_PORTS: dict[str, PortInformation] = {
        CASE_COPY_REPLACES_KEY: PortInformation(data_type=bool, required=True),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {CASE_COPY_REPLACES_KEY: f"/{CASE_COPY_REPLACES_KEY}"}

    def __init__(
        self,
        case_id: str,
        case_obj: VulnerabilityCase,
        request: AnnounceVulnerabilityCaseReceivedEvent,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.case_obj = case_obj
        self._request = request
        #: True only after the copy was found stale (SYNC-16-006).
        self.is_stale = False
        #: True only after the copy was found to conflict with the chain.
        self.is_conflict = False

    def update(self) -> Status:
        self.is_stale = False
        self.is_conflict = False
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        if self._resolve_case_replica(self.case_id) is None:
            # Regime 2 (ADR-0087): no replica yet, so this is a first seed.
            self._set_output(CASE_COPY_REPLACES_KEY, False)
            return Status.SUCCESS

        if self._request.actor_id == self.actor_id:
            # The CASE_MANAGER receives its own broadcast as a participant.
            # Its case is the source of the copy, not a replica of it, so the
            # copy has nothing to give it (ADR-0124).
            self.is_stale = True
            self.feedback_message = (
                f"the copy of case '{self.case_id}' is this actor's own; its"
                " case is the source of the copy"
            )
            self.logger.info(
                "%s: skipping Announce '%s': %s",
                self.name,
                self._request.activity_id,
                self.feedback_message,
            )
            return Status.FAILURE

        position = self.case_obj.ledger_position
        judgement = judge_case_copy(self.case_id, position, self.datalayer)
        if judgement.verdict is CaseCopyVerdict.CONFLICT:
            self.is_conflict = True
            self.feedback_message = judgement.reason
            self.logger.error(
                "%s: case copy '%s' in Announce '%s' from '%s' conflicts with"
                " this replica's ledger; case unchanged: %s",
                self.name,
                self.case_id,
                self._request.activity_id,
                self._request.actor_id,
                judgement.reason,
            )
            return Status.FAILURE
        if judgement.verdict is CaseCopyVerdict.STALE:
            self.is_stale = True
            self.feedback_message = judgement.reason
            self.logger.info(
                "%s: skipping case copy '%s' in Announce '%s' from '%s';"
                " case unchanged: %s",
                self.name,
                self.case_id,
                self._request.activity_id,
                self._request.actor_id,
                judgement.reason,
            )
            return Status.FAILURE
        self.logger.debug("%s: %s", self.name, judgement.reason)
        self._set_output(CASE_COPY_REPLACES_KEY, True)
        return Status.SUCCESS


class RequestCaseCopyBackfillNode(DataLayerActionWithPorts):
    """Ask for the entries a replacing copy is ahead of this chain by.

    Runs after :class:`SeedAnnouncedCaseNode`, which stored the case at the
    copy's position (SYNC-16-007).  When the copy replaced a case this
    replica held (``/case_copy_replaces``) and its position is ahead of the
    replica's chain, the node sends the sender ``Reject(CaseLedgerEntry)``
    carrying the replica's own tail, which the CASE_MANAGER answers by
    replaying from it (SYNC-03-002).

    The ``Reject`` names the last entry the chain stores.  A replica whose
    chain stores none has no entry to name, so it sends the ``Reject`` that
    names no entry, stating the empty chain's position and the case as its
    target: the CASE_MANAGER answers it by replaying from genesis, and each
    entry up to the copy's position is stored as a no-op (SYNC-16-007).

    A repeat of the same copy, such as the one the CASE_MANAGER's genesis
    answer starts with, asks again while the chain is still short.  The
    ``Reject``'s id is derived from what it asks for, so that is the same
    request queued once more, which the receiver deduplicates (ID-04-005),
    never a new one.

    Raises:
        VultronWiringError: A ``Reject`` is due and no ``sync_port`` was
            injected.
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        CASE_COPY_REPLACES_KEY: PortInformation(data_type=bool, required=True),
        "sync_port": PortInformation(data_type=object, required=False),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            CASE_COPY_REPLACES_KEY: f"/{CASE_COPY_REPLACES_KEY}",
            "sync_port": "/sync_port",
        }

    def __init__(
        self,
        case_id: str,
        case_obj: VulnerabilityCase,
        request: AnnounceVulnerabilityCaseReceivedEvent,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.case_obj = case_obj
        self._request = request
        self._replaces = False
        self._sync_port: SyncActivityPort | None = None

    def initialise(self) -> None:
        super().initialise()
        self._replaces = bool(self.get_input(CASE_COPY_REPLACES_KEY))
        try:
            self._sync_port = cast(
                SyncActivityPort, self.get_input("sync_port")
            )
        except (NoDataAvailable, NotImplementedError):
            self._sync_port = None

    def update(self) -> Status:
        if not self._replaces:
            return Status.SUCCESS
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None and self.actor_id is not None
        position = self.case_obj.ledger_position
        judgement = judge_case_copy(self.case_id, position, self.datalayer)
        if position.log_index <= judgement.chain_index:
            return Status.SUCCESS
        self._send_reject(judgement, position)
        return Status.SUCCESS

    def _send_reject(
        self, judgement: CaseCopyJudgement, position: LedgerPosition
    ) -> None:
        if self._sync_port is None:
            raise VultronWiringError(
                f"{self.name}: sync_port must be injected to ask for the"
                " entries a replacing case copy is ahead by (SYNC-16-007)"
            )
        assert self.actor_id is not None
        to = [self._request.actor_id]
        chain_tail = judgement.chain_tail
        self.logger.info(
            "%s: case '%s' replaced by a copy at entry %d, ahead of this"
            " replica's chain at %d; sending Reject(CaseLedgerEntry) to '%s'"
            " (SYNC-16-007)",
            self.name,
            self.case_id,
            position.log_index,
            judgement.chain_index,
            self._request.actor_id,
        )
        if chain_tail is None:
            # No entry to name: ask for a replay from genesis (SYNC-16-007).
            self._sync_port.send_genesis_replay_reject(
                case_id=self.case_id,
                copy_tail_hash=position.entry_hash,
                actor_id=self.actor_id,
                to=to,
            )
            return
        self._sync_port.send_reject_log_entry(
            entry=chain_tail,
            tail_hash=chain_tail.entry_hash,
            actor_id=self.actor_id,
            to=to,
        )


class StateSeededLedgerPositionNode(DataLayerActionWithPorts):
    """State the ledger position a first case copy seeded the replica at.

    Runs after :class:`SeedAnnouncedCaseNode` has stored the case.  When the
    copy seeded a replica this actor did not hold (``/case_copy_replaces`` is
    ``False``, PCR-02-003), the participant queues one
    ``Read(CaseLedgerEntry)`` to the case's CASE_MANAGER stating the stored
    case's ledger position (SYNC-17-008,
    :func:`~vultron.core.behaviors.sync.nodes.position_statement.stated_replica_position`).
    That is the replica's tail: a first seed finds no entry stored, since a
    replica stores no entry for a case it does not hold, and the case is at
    the copy's position, which reflects every entry up to it (SYNC-16-005,
    SYNC-16-007).  If the send fails after the seed, a redelivery replaces
    the case and states nothing; the participant's restart statement
    (SYNC-17-007) states the same position instead.  The statement
    tells the CASE_MANAGER the replica is ready, so it can resend an Invite
    the participant dropped before the copy arrived (ADR-0163).

    It sends nothing for a copy that replaced a held case: the participant
    already held the case, and :class:`RequestCaseCopyBackfillNode` asks for
    what it lacks.  It sends nothing either for a case at the empty ledger's
    position, which names no entry (SYNC-17-001), or one
    :func:`~vultron.core.behaviors.sync.nodes.position_statement.position_statement_recipient`
    names no CASE_MANAGER for, such as a copy of a case this actor manages.

    Raises:
        VultronWiringError: A statement is due and no ``sync_port`` was
            injected.
    """

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerActionWithPorts.INPUT_PORTS,
        CASE_COPY_REPLACES_KEY: PortInformation(data_type=bool, required=True),
        "sync_port": PortInformation(data_type=object, required=False),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {
            CASE_COPY_REPLACES_KEY: f"/{CASE_COPY_REPLACES_KEY}",
            "sync_port": "/sync_port",
        }

    def __init__(self, case_id: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self._replaces = False
        self._sync_port: SyncActivityPort | None = None

    def initialise(self) -> None:
        super().initialise()
        self._replaces = bool(self.get_input(CASE_COPY_REPLACES_KEY))
        try:
            self._sync_port = cast(
                SyncActivityPort, self.get_input("sync_port")
            )
        except (NoDataAvailable, NotImplementedError):
            self._sync_port = None

    def update(self) -> Status:
        if self._replaces:
            return Status.SUCCESS
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None and self.actor_id is not None
        case = self._resolve_case_replica(self.case_id)
        if case is None:
            # The seed before this node stores the case (BT-HELPER-01).
            raise VultronNotFoundError("VulnerabilityCase", self.case_id)
        manager_id = position_statement_recipient(
            case, self.datalayer, self.actor_id
        )
        position = stated_replica_position(case, self.datalayer)
        if manager_id is None or position is None:
            self.logger.debug(
                "%s: case '%s' seeded; no ledger position to state",
                self.name,
                self.case_id,
            )
            return Status.SUCCESS
        if self._sync_port is None:
            raise VultronWiringError(
                f"{self.name}: sync_port must be injected to state the"
                " ledger position a case copy seeded (SYNC-17-008)"
            )
        self._sync_port.send_read_ledger_entry(
            case_id=self.case_id,
            ledger_position=position,
            actor_id=self.actor_id,
            to=[manager_id],
        )
        self.logger.info(
            "%s: case '%s' seeded at log_index=%d; stated the position to"
            " CASE_MANAGER '%s' (SYNC-17-008)",
            self.name,
            self.case_id,
            position.log_index,
            manager_id,
        )
        return Status.SUCCESS


__all__ = [
    "CASE_COPY_REPLACES_KEY",
    "CaseCopyNotStaleNode",
    "RequestCaseCopyBackfillNode",
    "StateSeededLedgerPositionNode",
]
