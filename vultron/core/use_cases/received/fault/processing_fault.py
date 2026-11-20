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

from vultron.core.behaviors.case.received_run import (
    ReceivedOutcome,
    run_received_tree,
)
from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlementKind,
    SenderRule,
)
from vultron.core.models.events.fault import (
    CreateProcessingFaultReceivedEvent,
)
from vultron.core.models.fault_classes import (
    VULTRON_FAILURE_LEDGER_ENTRY_REFUSED_CASE_DIVERGED,
    VULTRON_FAILURE_LEDGER_ENTRY_REFUSED_HASH_MISMATCH,
)
from vultron.core.models.use_case_result import HandlerResult
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.ports.trigger_activity import TriggerActivityPort
from vultron.core.ports.wire_render import WireRenderPort
from vultron.core.use_cases.received.fault.responses import (
    ARCHIVE_ONLY,
    CASE_DIVERGED,
    HASH_MISMATCH,
    FaultResponse,
)

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

    A fault carries no case (ASK-07-006).  Each response's tree finds the
    entry its ``inReplyTo`` ``Add(CaseLedgerEntry)`` carried, and so the
    case, with a lookup node of its own (BT-25-009), and refuses a fault
    naming no such ``Add`` this actor sent with that lookup's declared
    refusal (BT-25-010).  ``execute`` reads no store: it builds the tree and
    hands it to the runner (ADR-0195).

    The sender rule is declared once, below, and the receive-tree factory
    composes it into the tree of every class that has an effect: at the
    CASE_MANAGER the sender must be an active participant of the case the
    fault concerns (CM-10-004, SYNC-16-003, SYNC-03-008).  Each response
    tree declares the manager path, where the rule states its one side, and
    the no-case path, where a fault whose entry was not found is refused by
    the lookup's miss guard before that side is read; the path stage
    refuses a replica (HP-01-038, HP-01-041).  A
    class that is only archived runs no guard, because nothing it does is
    gated on a sender's standing.
    """

    sender_entitlement: ClassVar[SenderRule] = SenderRule.at_case_manager_only(
        SenderEntitlementKind.ACTIVE_PARTICIPANT
    )

    #: The response to each failure class that has an effect.
    responses: ClassVar[Mapping[str, FaultResponse]] = MappingProxyType(
        {
            VULTRON_FAILURE_LEDGER_ENTRY_REFUSED_CASE_DIVERGED: CASE_DIVERGED,
            VULTRON_FAILURE_LEDGER_ENTRY_REFUSED_HASH_MISMATCH: HASH_MISMATCH,
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

        def read(outcome: ReceivedOutcome) -> HandlerResult | None:
            return response.reader(outcome)

        # Only the case's CASE_MANAGER acts on a fault about its ledger: the
        # tree declares the manager path, so its path stage refuses a
        # replica (HP-01-005).
        return run_received_tree(
            response.build_tree(request, self.sender_entitlement),
            dl=self._dl,
            request=request,
            label=response.label,
            trigger_activity=self._trigger_activity,
            sync_port=self._sync_port,
            wire_render_port=self._wire_render_port,
            reader=read,
            judges=response.judges,
        )
