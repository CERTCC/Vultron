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

"""Received use case for a ``Create(ProcessingFault)`` NACK (ADR-0080, ASK-07-001)."""

import logging
from collections.abc import Mapping
from types import MappingProxyType
from typing import ClassVar

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlementKind,
    SenderRule,
)
from vultron.core.behaviors.sync.nodes.reseed import (
    announced_ledger_entry,
)
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.events.fault import (
    CreateProcessingFaultReceivedEvent,
)
from vultron.core.models.fault_classes import (
    VULTRON_FAILURE_LEDGER_ENTRY_REFUSED_CASE_DIVERGED,
    VULTRON_FAILURE_LEDGER_ENTRY_REFUSED_HASH_MISMATCH,
)
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.ports.trigger_activity import TriggerActivityPort
from vultron.core.ports.wire_render import WireRenderPort
from vultron.core.use_cases._helpers import resolve_receiving_actor_id
from vultron.core.use_cases.received.fault.responses import (
    ARCHIVE_ONLY,
    FaultResponse,
    _case_diverged_tree,
    _hash_mismatch_tree,
    _hash_mismatch_verdict,
    _reseed_verdict,
)
from vultron.errors import VultronNotFoundError

logger = logging.getLogger(__name__)


class CreateProcessingFaultReceivedUseCase:
    """Answer a received ``Create(ProcessingFault)`` by its failure class.

    Every fault is logged at WARNING, naming its sender, class and failed
    activity.  The response is then chosen by the fault's class, one
    :class:`FaultResponse` in :attr:`responses` per class that has an effect:

    - ``LedgerEntryRefused/CaseDiverged`` — at the case's CASE_MANAGER,
      re-seed the replica with ``Announce(VulnerabilityCase)`` of the current
      case, rate-bounded per peer, ledgering nothing (SYNC-16-002,
      SYNC-16-003, SYNC-16-004, SYNC-16-008).
    - ``LedgerEntryRefused/HashMismatch`` — at the case's CASE_MANAGER, log
      the fault at ERROR and re-check its own stored copy of the named entry,
      changing nothing and reporting ``SKIPPED``: neither a replay nor a
      re-seed can heal a hash mismatch (SYNC-03-008, SYNC-03-010).

    A class with no entry is only archived, as every received tree archives
    what arrived (CLP-10-018), and reports ``SKIPPED``: correlating it to the
    ask it answers is #2883 (:data:`ARCHIVE_ONLY`).  A new class's effect is
    a new entry; ``execute`` builds and runs exactly one tree whatever the
    class (CLP-10-005).

    A fault carries no case (ASK-07-006).  When its ``inReplyTo`` names an
    ``Announce(CaseLedgerEntry)`` this actor sent, the entry that announce
    carried is read from this store and handed to the response, so the case
    is the entry's.

    The sender rule is declared once, below, and the receive-tree factory
    composes it into the tree of every class that has an effect: at the
    CASE_MANAGER the sender must be an active participant of the case the
    fault concerns (CM-10-004, SYNC-16-003, SYNC-03-008), and at a
    participant the fault must come from the CASE_MANAGER (PCR-03-001).  A
    class that is only archived runs no guard, because nothing it does is
    gated on a sender's standing.
    """

    sender_entitlement: ClassVar[SenderRule] = SenderRule.to_case_manager(
        SenderEntitlementKind.ACTIVE_PARTICIPANT
    )

    #: The response to each failure class that has an effect.
    responses: ClassVar[Mapping[str, FaultResponse]] = MappingProxyType(
        {
            VULTRON_FAILURE_LEDGER_ENTRY_REFUSED_CASE_DIVERGED: FaultResponse(
                build_tree=_case_diverged_tree, read_verdict=_reseed_verdict
            ),
            VULTRON_FAILURE_LEDGER_ENTRY_REFUSED_HASH_MISMATCH: FaultResponse(
                build_tree=_hash_mismatch_tree,
                read_verdict=_hash_mismatch_verdict,
            ),
        }
    )

    def __init__(
        self,
        dl: CasePersistence,
        request: CreateProcessingFaultReceivedEvent,
        sync_port: SyncActivityPort | None = None,
        wire_render_port: WireRenderPort | None = None,
        trigger_activity: TriggerActivityPort | None = None,
    ) -> None:
        self._dl = dl
        self._wire_render_port = wire_render_port
        self._sync_port = sync_port
        self._trigger_activity = trigger_activity
        self._request = request

    def execute(self) -> HandlerResult:
        request = self._request
        logger.warning(
            "ProcessingFault received from '%s': failed activity '%s'"
            " (failure class: '%s', fault: '%s', carried by Create: '%s')",
            request.actor_id,
            # A fault may omit inReplyTo; say so rather than print 'None'.
            request.failed_activity_id or "<not named: no inReplyTo>",
            request.failure_class,
            request.fault_id,
            request.activity_id,
        )
        response = self.responses.get(request.failure_class, ARCHIVE_ONLY)
        refused_entry = (
            self._refused_entry() if response.reads_refused_entry else None
        )
        tree = response.build_tree(
            refused_entry, request, self.sender_entitlement
        )
        result = BTBridge(
            datalayer=self._dl,
            trigger_activity=self._trigger_activity,
            wire_render_port=self._wire_render_port,
            sync_port=self._sync_port,
        ).execute_with_setup(
            tree=tree,
            actor_id=resolve_receiving_actor_id(
                self._dl, request.receiving_actor_id
            ),
            activity=request,
        )
        verdict = response.read_verdict(tree, result, self._dl, refused_entry)
        if verdict.disposition is HandlerDisposition.REFUSED:
            logger.warning(
                "ProcessingFault '%s' from '%s' refused: %s",
                request.fault_id,
                request.actor_id,
                verdict.reason,
            )
        return verdict

    def _refused_entry(self) -> CaseLedgerEntry | None:
        """The entry the fault's ``inReplyTo`` announce carried, if this
        store sent it; read-only."""
        failed_id = self._request.failed_activity_id
        if failed_id is None:
            return None
        try:
            return announced_ledger_entry(
                self._dl,
                failed_id,
                resolve_receiving_actor_id(
                    self._dl, self._request.receiving_actor_id
                ),
            )
        except VultronNotFoundError:
            return None
