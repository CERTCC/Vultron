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
"""BT nodes that judge a case copy by its ledger tail and ask for the rest.

The guard that decides whether a copy of a case this replica already holds
may replace it (SYNC-16-006), and the node that asks the CASE_MANAGER for the
entries a replacing copy is ahead of the replica's chain by (SYNC-16-007).
:class:`~vultron.core.behaviors.case.nodes.announce.SeedAnnouncedCaseNode`
does the replacement between them (ADR-0142).
"""

from typing import Any, cast

from py_trees.common import Status
from py_trees.ports import NoDataAvailable, PortInformation

from vultron.core.behaviors.helpers import (
    DataLayerActionWithPorts,
    DataLayerConditionWithPorts,
)
from vultron.core.behaviors.idempotency import FlaggedRepeatGuardMixin
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.events.actor import (
    AnnounceVulnerabilityCaseReceivedEvent,
)
from vultron.core.models.ledger_position import LedgerPosition
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.services.case_copy import CaseCopyVerdict, judge_case_copy
from vultron.errors import VultronValidationError, VultronWiringError

#: Blackboard key: whether the announced copy replaces a case this replica
#: already holds, written by :class:`CaseCopyNotStaleNode` and read by
#: :class:`RequestCaseCopyBackfillNode`.
CASE_COPY_REPLACES_KEY = "case_copy_replaces"


class CaseCopyNotStaleNode(
    FlaggedRepeatGuardMixin, DataLayerConditionWithPorts
):
    """Guard: a copy of a case this replica holds may replace it (SYNC-16-006).

    A replica that does not hold the case yet seeds it from any copy
    (PCR-02-003): ``SUCCESS``.  One that holds it compares the ledger tail
    the copy names (SYNC-16-005) with its own position
    (:func:`~vultron.core.services.case_copy.judge_case_copy`):

    - the replica is already past the tail: ``FAILURE`` with ``is_stale``
      set, logged at INFO; the handler reports ``SKIPPED`` and the case is
      unchanged;
    - it holds a different entry at the tail's index: ``FAILURE`` with
      ``is_conflict`` set, logged at ERROR; the handler reports ``REFUSED``
      and the case is unchanged;
    - otherwise ``SUCCESS``: the copy replaces the case.

    A copy that names no tail cannot be told from a stale one, so a replica
    holding the case refuses it (``FAILURE``, WARNING).

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
        case_obj: VulnerabilityCase | Any,
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

        tail = getattr(self.case_obj, "ledger_tail", None)
        if tail is None:
            self.feedback_message = (
                f"the copy of case '{self.case_id}' names no ledger tail, so"
                " this replica cannot tell it from a stale one (SYNC-16-005)"
            )
            self.logger.warning(
                "%s: refusing Announce '%s' from '%s': %s",
                self.name,
                self._request.activity_id,
                self._request.actor_id,
                self.feedback_message,
            )
            return Status.FAILURE

        judgement = judge_case_copy(self.case_id, tail, self.datalayer)
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

    Runs after :class:`SeedAnnouncedCaseNode`, which recorded the copy's
    tail with the replacement (SYNC-16-007).  When the copy replaced a case
    this replica held (``/case_copy_replaces``) and its tail is ahead of the
    replica's chain, the node sends the sender ``Reject(CaseLedgerEntry)``
    carrying the replica's own tail, which the CASE_MANAGER answers by
    replaying from it (SYNC-03-002).

    The ``Reject`` names the last entry the chain stores.  A replica whose
    chain stores none has no entry to name, so it sends the ``Reject`` that
    names no entry, with an empty last-accepted hash and the case as its
    target: the CASE_MANAGER answers it by replaying from genesis, and each
    entry up to the copy's tail is stored as a no-op (SYNC-16-007).

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
        case_obj: VulnerabilityCase | Any,
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
        tail = required_tail(self.case_obj, self.case_id, self.name)
        chain_tail = judge_case_copy(
            self.case_id, tail, self.datalayer
        ).chain_tail
        chain_index = chain_tail.log_index if chain_tail else -1
        if tail.log_index <= chain_index:
            return Status.SUCCESS
        self._send_reject(chain_tail, tail)
        return Status.SUCCESS

    def _send_reject(
        self, chain_tail: CaseLedgerEntry | None, tail: LedgerPosition
    ) -> None:
        if self._sync_port is None:
            raise VultronWiringError(
                f"{self.name}: sync_port must be injected to ask for the"
                " entries a replacing case copy is ahead by (SYNC-16-007)"
            )
        assert self.actor_id is not None
        to = [self._request.actor_id]
        self.logger.info(
            "%s: case '%s' replaced by a copy at entry %d, ahead of this"
            " replica's chain at %d; sending Reject(CaseLedgerEntry) to '%s'"
            " (SYNC-16-007)",
            self.name,
            self.case_id,
            tail.log_index,
            chain_tail.log_index if chain_tail else -1,
            self._request.actor_id,
        )
        if chain_tail is None:
            # No entry to name: ask for a replay from genesis (SYNC-16-007).
            self._sync_port.send_genesis_replay_reject(
                case_id=self.case_id, actor_id=self.actor_id, to=to
            )
            return
        self._sync_port.send_reject_log_entry(
            entry=chain_tail,
            tail_hash=chain_tail.entry_hash,
            actor_id=self.actor_id,
            to=to,
        )


def required_tail(
    case_obj: Any, case_id: str, node_name: str
) -> LedgerPosition:
    """The tail of a copy the guard admitted to replace a held case.

    Raises:
        VultronValidationError: The copy names none; the guard refuses such a
            copy, so reaching here is a composition fault.
    """
    tail = getattr(case_obj, "ledger_tail", None)
    if not isinstance(tail, LedgerPosition):
        raise VultronValidationError(
            f"{node_name}: the copy replacing case '{case_id}' names no"
            " ledger tail; the guard admits none (SYNC-16-006)"
        )
    return tail


__all__ = [
    "CASE_COPY_REPLACES_KEY",
    "CaseCopyNotStaleNode",
    "RequestCaseCopyBackfillNode",
    "required_tail",
]
