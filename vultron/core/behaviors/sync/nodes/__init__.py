#!/usr/bin/env python
#
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

"""
SYNC log-replication behavior tree nodes subpackage.

Re-exports all public node classes from domain-specific submodules so that
existing import paths (``from vultron.core.behaviors.sync.nodes import ...``)
continue to work without modification.

Submodules:
- ``conditions``: Idempotency guard and sender verification condition nodes
- ``receive``: Log entry delivery and validation action nodes
- ``chain``: Chain reconstruction and log entry creation action nodes
- ``canonical_entry``: Canonical ``payloadSnapshot`` validation (CLP-07)
- ``replay``: Replay and fan-out action nodes for replication
- ``effects``: Ledger-apply side-effect nodes (note, invite-accept, close-case)
- ``participant_status_effect``: Ledger-apply of ``ParticipantStatus``, with the
  monotonic-RM ratchet (ADR-0061)
- ``offer_report_effect``, ``ownership_effects``, ``ownership_offer_effect``:
  per-effect ledger-apply nodes
"""

from vultron.core.behaviors.sync.nodes.chain import (
    CreateLogEntryNode,
    PersistLogEntryNode,
    ReconstructChainTailNode,
    UpdateReplicationStateNode,
)
from vultron.core.behaviors.sync.nodes.conditions import (
    CheckIsNotOwnCaseActorNode,
    CheckIsOwnCaseActorNode,
    CheckLedgerEntryAlreadyStoredNode,
    CheckLedgerFreshnessNode,
    IsAddNoteEventNode,
    IsCloseCaseEventNode,
    IsInviteAcceptEventNode,
    IsOwnershipTransferEventNode,
    IsParticipantStatusEventNode,
    IsRemoveEmbargoEventNode,
    IsSubmitReportEventNode,
    VerifySenderIsOwnIdNode,
    _find_case_actor,  # noqa: F401
    _require_case_actor_id,  # noqa: F401
    _require_log_entry,  # noqa: F401
)
from vultron.core.behaviors.sync.nodes.receive import (
    BufferOutOfOrderEntryNode,
    BufferPreGenesisEntryNode,
    CheckHashMatchesNode,
    CheckHashOrRejectOnMismatchNode,
    LogDeliveryConfirmationNode,
    PersistReceivedLogEntryNode,
    SendRejectLogEntryNode,
)
from vultron.core.behaviors.sync.nodes.close_case_effect import (
    ApplyCloseCaseFromLedgerNode,
)
from vultron.core.behaviors.sync.nodes.invite_accept_effect import (
    ApplyInviteAcceptFromLedgerNode,
)
from vultron.core.behaviors.sync.nodes.note_effect import (
    ApplyNoteFromLedgerNode,
)
from vultron.core.behaviors.sync.nodes.participant_status_effect import (
    ApplyParticipantStatusFromLedgerNode,
)
from vultron.core.behaviors.sync.nodes.offer_report_effect import (
    ApplyOfferReportFromLedgerNode,
)
from vultron.core.behaviors.sync.nodes.ownership_effects import (
    ApplyOwnershipTransferFromLedgerNode,
)
from vultron.core.behaviors.sync.nodes.ownership_offer_effect import (
    ApplyOfferOwnershipTransferFromLedgerNode,
    IsOfferOwnershipTransferEventNode,
)
from vultron.core.behaviors.sync.nodes.fanout import (
    CollectNonClosedLogEntryRecipientsNode,
    FanOutLogEntryExcludingClosedNode,
)
from vultron.core.behaviors.sync.nodes.replay import (
    AnnounceCaseOnGenesisRejectNode,
    CollectAndSortCaseLedgerEntriesNode,
    CollectLogEntryRecipientsNode,
    FanOutLogEntryNode,
    FindCaseActorNode,
    FindDivergenceIndexNode,
    ReplayMissingEntriesNode,
    SendLogEntryToEachNode,
    SendMissingEntriesNode,
)

__all__ = [
    # conditions
    "CheckIsOwnCaseActorNode",
    "CheckIsNotOwnCaseActorNode",
    "VerifySenderIsOwnIdNode",
    "CheckLedgerEntryAlreadyStoredNode",
    "CheckLedgerFreshnessNode",
    "IsRemoveEmbargoEventNode",
    "IsParticipantStatusEventNode",
    "IsAddNoteEventNode",
    "IsInviteAcceptEventNode",
    "IsCloseCaseEventNode",
    "IsSubmitReportEventNode",
    "IsOwnershipTransferEventNode",
    # effects
    "ApplyNoteFromLedgerNode",
    "ApplyInviteAcceptFromLedgerNode",
    "ApplyCloseCaseFromLedgerNode",
    # participant_status_effect
    "ApplyParticipantStatusFromLedgerNode",
    # per-effect ledger-apply modules
    "ApplyOfferReportFromLedgerNode",
    "ApplyOwnershipTransferFromLedgerNode",
    "ApplyOfferOwnershipTransferFromLedgerNode",
    "IsOfferOwnershipTransferEventNode",
    # receive
    "LogDeliveryConfirmationNode",
    "PersistReceivedLogEntryNode",
    "CheckHashMatchesNode",
    "BufferOutOfOrderEntryNode",
    "BufferPreGenesisEntryNode",
    "SendRejectLogEntryNode",
    "CheckHashOrRejectOnMismatchNode",
    # chain
    "ReconstructChainTailNode",
    "UpdateReplicationStateNode",
    "CreateLogEntryNode",
    "PersistLogEntryNode",
    # replay
    "AnnounceCaseOnGenesisRejectNode",
    "FindCaseActorNode",
    "CollectAndSortCaseLedgerEntriesNode",
    "FindDivergenceIndexNode",
    "SendMissingEntriesNode",
    "ReplayMissingEntriesNode",
    "CollectLogEntryRecipientsNode",
    "CollectNonClosedLogEntryRecipientsNode",
    "SendLogEntryToEachNode",
    "FanOutLogEntryNode",
    "FanOutLogEntryExcludingClosedNode",
    # re-exported helper functions (backward compat)
    "_find_case_actor",
    "_require_case_actor_id",
    "_require_log_entry",
]
