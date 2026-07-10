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

"""
Case management behavior tree nodes subpackage.

Re-exports all public node classes from domain-specific submodules so that
existing import paths (``from vultron.core.behaviors.case.nodes import ...``)
continue to work without modification.

Submodules:
- ``actor``: Actor-participation invite/accept emit nodes
- ``conditions``: Idempotency guard condition nodes
- ``case_setup``: Case persistence and actor setup leaf action nodes
- ``participant``: Participant creation and attachment leaf action nodes
- ``embargo``: Default embargo initialization action nodes
- ``communication``: Outbound activity emission action nodes
- ``lifecycle``: Case log entry commit action node

Composite subtrees (``Sequence``/``Selector`` subclasses) are defined in
sibling ``*_tree.py`` modules at the process-area root per BTND-07-003.
They are re-exported here for backward compatibility via module
``__getattr__`` (PEP 562) to avoid circular imports:

- ``RecordCaseCreationEvents``, ``CreateCaseActorNode``
  → ``vultron.core.behaviors.case.case_setup_tree``
- ``CreateCaseOwnerParticipant``, ``CreateCaseParticipantNode``
  → ``vultron.core.behaviors.case.participant_tree``
- ``EmitCreateCaseActivity``, ``SendOfferCaseManagerRoleNode``
  → ``vultron.core.behaviors.case.communication_tree``
- ``InitializeDefaultEmbargoNode``
  → ``vultron.core.behaviors.case.embargo_tree``
"""

import importlib
from typing import TYPE_CHECKING

from vultron.core.behaviors.case.nodes.actor import (
    EmitAcceptCaseInviteNode,
    EmitInviteActorToCaseNode,
    ProposeCaseToActorNode,
)
from vultron.core.behaviors.case.nodes.case_setup import (
    PersistCase,
    RecordCaseCreatedEventNode,
    RecordOfferReceivedEventNode,
    SetCaseAttributedTo,
)
from vultron.core.behaviors.case.nodes.communication import (
    CollectCaseAddresseesNode,
    CreateAndPersistCaseActivityNode,
)
from vultron.core.behaviors.case.nodes.delegation import (
    AutoAcceptCaseManagerRoleNode,
    CreateOfferCaseManagerActivityNode,
    EmitRejectCaseManagerRoleNode,
    ResolveCaseManagerOfferContextNode,
)
from vultron.core.behaviors.case.nodes.conditions import (
    CheckAutoCaseCreationEnabledNode,
    CheckCaseAlreadyExists,
    CheckCaseExistsForReport,
    CheckIsCaseManagerNode,
)
from vultron.core.behaviors.case.nodes.embargo import (
    AdvanceEMStateToActiveNode,
    AttachEmbargoToCaseNode,
    CreateEmbargoEventNode,
    ResolveEmbargoDurationNode,
    SeedOwnerAsSignatoryNode,
)
from vultron.core.behaviors.case.nodes.lifecycle import (
    CommitCaseLedgerEntryNode,
    create_guarded_commit_case_ledger_entry_tree,
    create_receive_activity_tree,
)
from vultron.core.behaviors.case.nodes.participant import (
    CreateParticipantStatusNode,
    RecordOwnerJoinedEventNode,
    _create_and_attach_participant,
    resolve_participant_state_from_dl,
)
from vultron.core.behaviors.case.nodes.update import (
    ApplyCaseUpdateNode,
    BroadcastCaseUpdateNode,
    CaptureCaseUpdateBroadcastExclusionsNode,
    CheckCaseUpdateOwnerNode,
)
from vultron.core.behaviors.helpers import UpdateActorOutbox  # noqa: F401

__all__ = [
    # actor (leaf nodes)
    "EmitInviteActorToCaseNode",
    "EmitAcceptCaseInviteNode",
    "ProposeCaseToActorNode",
    # conditions
    "CheckAutoCaseCreationEnabledNode",
    "CheckCaseAlreadyExists",
    "CheckCaseExistsForReport",
    "CheckIsCaseManagerNode",
    # case_setup (leaf nodes)
    "PersistCase",
    "SetCaseAttributedTo",
    "RecordOfferReceivedEventNode",
    "RecordCaseCreatedEventNode",
    # case_setup_tree (composite subtrees — lazy via __getattr__)
    "RecordCaseCreationEvents",
    "CreateCaseActorNode",
    # participant (leaf nodes)
    "CreateParticipantStatusNode",
    "RecordOwnerJoinedEventNode",
    "_create_and_attach_participant",
    "resolve_participant_state_from_dl",
    # participant_tree (composite subtrees — lazy via __getattr__)
    "CreateCaseOwnerParticipant",
    "CreateCaseParticipantNode",
    # embargo (leaf nodes)
    "AdvanceEMStateToActiveNode",
    "AttachEmbargoToCaseNode",
    "CreateEmbargoEventNode",
    "ResolveEmbargoDurationNode",
    "SeedOwnerAsSignatoryNode",
    # embargo_tree (composite subtree — lazy via __getattr__)
    "InitializeDefaultEmbargoNode",
    # communication (leaf nodes)
    "AutoAcceptCaseManagerRoleNode",
    "CollectCaseAddresseesNode",
    "CreateAndPersistCaseActivityNode",
    "CreateOfferCaseManagerActivityNode",
    "EmitRejectCaseManagerRoleNode",
    "ResolveCaseManagerOfferContextNode",
    # communication_tree (composite subtrees — lazy via __getattr__)
    "EmitCreateCaseActivity",
    "SendOfferCaseManagerRoleNode",
    # lifecycle
    "CommitCaseLedgerEntryNode",
    "create_guarded_commit_case_ledger_entry_tree",
    "create_receive_activity_tree",
    # update
    "CheckCaseUpdateOwnerNode",
    "CaptureCaseUpdateBroadcastExclusionsNode",
    "ApplyCaseUpdateNode",
    "BroadcastCaseUpdateNode",
    # re-exported from helpers (backward compat)
    "UpdateActorOutbox",
]

# TYPE_CHECKING stubs so mypy resolves composite names to their actual types.
# At runtime these imports are skipped; the lazy __getattr__ below handles them.
if TYPE_CHECKING:
    from vultron.core.behaviors.case.case_setup_tree import (  # noqa: F401
        CreateCaseActorNode,
        RecordCaseCreationEvents,
    )
    from vultron.core.behaviors.case.communication_tree import (  # noqa: F401
        EmitCreateCaseActivity,
        SendOfferCaseManagerRoleNode,
    )
    from vultron.core.behaviors.case.embargo_tree import (  # noqa: F401
        InitializeDefaultEmbargoNode,
    )
    from vultron.core.behaviors.case.participant_tree import (  # noqa: F401
        CreateCaseOwnerParticipant,
        CreateCaseParticipantNode,
    )

# Composite subtrees live in sibling *_tree.py modules (BTND-07-003).
# They are re-exported lazily here to avoid circular imports: the tree
# modules import leaf nodes from this package, so eager re-exports would
# create a cycle.  PEP 562 module __getattr__ resolves the name only when
# first accessed, after this __init__ is fully initialized.
_COMPOSITE_COMPAT: dict[str, str] = {
    "CreateCaseActorNode": "vultron.core.behaviors.case.case_setup_tree",
    "RecordCaseCreationEvents": "vultron.core.behaviors.case.case_setup_tree",
    "CreateCaseOwnerParticipant": "vultron.core.behaviors.case.participant_tree",
    "CreateCaseParticipantNode": "vultron.core.behaviors.case.participant_tree",
    "EmitCreateCaseActivity": "vultron.core.behaviors.case.communication_tree",
    "SendOfferCaseManagerRoleNode": "vultron.core.behaviors.case.communication_tree",
    "InitializeDefaultEmbargoNode": "vultron.core.behaviors.case.embargo_tree",
}


def __getattr__(name: str) -> object:
    if name in _COMPOSITE_COMPAT:
        mod = importlib.import_module(_COMPOSITE_COMPAT[name])
        obj = getattr(mod, name)
        globals()[name] = obj  # cache to avoid repeated lookup
        return obj
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
