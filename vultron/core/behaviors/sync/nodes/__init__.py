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
- ``replay``: Replay and fan-out action nodes for replication
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
    IsNotRemoveEmbargoEventNode,
    VerifySenderIsOwnIdNode,
    _find_case_actor,  # noqa: F401
    _require_case_actor_id,  # noqa: F401
    _require_log_entry,  # noqa: F401
)
from vultron.core.behaviors.sync.nodes.receive import (
    CheckHashMatchesNode,
    CheckHashOrRejectOnMismatchNode,
    LogDeliveryConfirmationNode,
    PersistReceivedLogEntryNode,
    SendRejectLogEntryNode,
)
from vultron.core.behaviors.sync.nodes.replay import (
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
    "IsNotRemoveEmbargoEventNode",
    # receive
    "LogDeliveryConfirmationNode",
    "PersistReceivedLogEntryNode",
    "CheckHashMatchesNode",
    "SendRejectLogEntryNode",
    "CheckHashOrRejectOnMismatchNode",
    # chain
    "ReconstructChainTailNode",
    "UpdateReplicationStateNode",
    "CreateLogEntryNode",
    "PersistLogEntryNode",
    # replay
    "FindCaseActorNode",
    "CollectAndSortCaseLedgerEntriesNode",
    "FindDivergenceIndexNode",
    "SendMissingEntriesNode",
    "ReplayMissingEntriesNode",
    "CollectLogEntryRecipientsNode",
    "SendLogEntryToEachNode",
    "FanOutLogEntryNode",
    # re-exported helper functions (backward compat)
    "_find_case_actor",
    "_require_case_actor_id",
    "_require_log_entry",
]
