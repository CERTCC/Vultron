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
Participant management behavior-tree nodes for case workflows.

This package replaces the previous monolithic ``participant.py`` module while
preserving its public import surface.

Composite subtrees (``Sequence``/``Selector`` subclasses) for participant
workflows are defined in ``participant_tree.py`` at the process-area root
(BTND-07-003).  They are re-exported here for backward compatibility via
module ``__getattr__`` (PEP 562) to avoid circular imports.
"""

import importlib
from typing import TYPE_CHECKING

from vultron.core.behaviors.case.nodes.participant.common import (
    _create_and_attach_participant,
    _get_or_create_accepted_status,
    _queue_participant_add_notification,
    resolve_participant_state_from_dl,
)
from vultron.core.behaviors.case.nodes.participant.owner import (
    AdvanceOwnerRmToAcceptedNode,
    AttachOwnerParticipantToCaseNode,
    CreateOwnerParticipantNode,
    PersistOwnerCaseNode,
    RecordOwnerJoinedEventNode,
    _build_owner_initial_status,
    _effective_case_roles,
    _resolve_case_id,
    ResolveOwnerInitialStatusNode,
    ShouldAdvanceOwnerToAcceptedNode,
)
from vultron.core.behaviors.case.nodes.participant.participant_add import (
    AttachParticipantToCaseNode,
    CaseHasActiveEmbargoNode,
    CaseHasNoActiveEmbargoNode,
    CreateParticipantNode,
    QueueAddParticipantNotificationNode,
    RecordParticipantAddedEventNode,
    ResolveParticipantAcceptedStatusNode,
    SeedParticipantAsSignatoryNode,
)
from vultron.core.behaviors.case.nodes.participant.status import (
    CreateParticipantStatusNode,
)

__all__ = [
    "_create_and_attach_participant",
    "_resolve_case_id",
    "_build_owner_initial_status",
    "_effective_case_roles",
    "_get_or_create_accepted_status",
    "_queue_participant_add_notification",
    "resolve_participant_state_from_dl",
    "ResolveOwnerInitialStatusNode",
    "CreateOwnerParticipantNode",
    "AttachOwnerParticipantToCaseNode",
    "PersistOwnerCaseNode",
    "ShouldAdvanceOwnerToAcceptedNode",
    "AdvanceOwnerRmToAcceptedNode",
    "RecordOwnerJoinedEventNode",
    # composite subtrees — lazy via __getattr__
    "CreateCaseOwnerParticipant",
    "ResolveParticipantAcceptedStatusNode",
    "CreateParticipantNode",
    "AttachParticipantToCaseNode",
    "RecordParticipantAddedEventNode",
    "CaseHasActiveEmbargoNode",
    "CaseHasNoActiveEmbargoNode",
    "SeedParticipantAsSignatoryNode",
    # composite subtrees — lazy via __getattr__
    "SeedParticipantAsSignatoryIfEmbargoActiveNode",
    "QueueAddParticipantNotificationNode",
    # composite subtrees — lazy via __getattr__
    "CreateCaseParticipantNode",
    "CreateParticipantStatusNode",
]

# TYPE_CHECKING stubs so mypy resolves composite names to their actual types.
# At runtime these imports are skipped; the lazy __getattr__ below handles them.
if TYPE_CHECKING:
    from vultron.core.behaviors.case.participant_tree import (  # noqa: F401
        CreateCaseOwnerParticipant,
        CreateCaseParticipantNode,
        SeedParticipantAsSignatoryIfEmbargoActiveNode,
    )

# Composite subtrees live in participant_tree.py (BTND-07-003).
# Re-exported lazily here to avoid circular imports with that module.
_COMPOSITE_COMPAT: dict[str, str] = {
    "CreateCaseOwnerParticipant": "vultron.core.behaviors.case.participant_tree",
    "SeedParticipantAsSignatoryIfEmbargoActiveNode": "vultron.core.behaviors.case.participant_tree",
    "CreateCaseParticipantNode": "vultron.core.behaviors.case.participant_tree",
}


def __getattr__(name: str) -> object:
    if name in _COMPOSITE_COMPAT:
        mod = importlib.import_module(_COMPOSITE_COMPAT[name])
        obj = getattr(mod, name)
        globals()[name] = obj  # cache to avoid repeated lookup
        return obj
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
