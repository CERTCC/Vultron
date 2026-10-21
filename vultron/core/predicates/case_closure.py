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

"""The one "case is fully closed" condition (CM-23-013, ADR-0085).

A case is fully closed once its ledger holds the CASE_MANAGER's own status
entry reaching ``RM.CLOSED``: the ``add_participant_status_to_participant``
entry the CASE_MANAGER commits for its own closure, the last step of the
owner-close sequence (CM-23-002 step 2, CM-23-005).  That entry is the
owner-close write boundary: after it, no inbound activity for the case is
recorded (CM-23-013).  No separate entry marks the closure: anything that
holds the case and its ledger can see it (ADR-0152).

Every check of that boundary uses :func:`entry_closes_case_manager`, through
:func:`ledger_records_full_closure` or :func:`closure_boundary_indices`, so the
BT guard, the demo checks, the invariant harness and the tests cannot
disagree about what "closed" means (CS-22-001).  The entry is read as the
ledger carries it, a ``semantic_type`` and a ``payloadSnapshot``, so a
core ``CaseLedgerEntry`` and an exported ledger row are judged alike.
"""

from collections.abc import Iterable, Mapping
from typing import Protocol

from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.models.wire_keys import wire_key
from vultron.core.predicates.addressing import (
    same_actor_id,
    snapshot_actor_id,
)
from vultron.core.states.rm import RM

#: ``semantic_type`` of a participant status entry; the boundary is one.
_PARTICIPANT_STATUS = (
    MessageSemantics.ADD_PARTICIPANT_STATUS_TO_PARTICIPANT.value
)

#: The keys of the status a participant status entry carries, in the AS2
#: spelling the snapshot holds (ARCH-25-002).
_ATTRIBUTED_TO = wire_key("attributed_to")
_RM_STATE = wire_key("rm", ParticipantStatus)


class _LedgerEntryLike(Protocol):
    @property
    def semantic_type(self) -> str: ...

    @property
    def payload_snapshot(self) -> Mapping[str, object]: ...


def entry_closes_case_manager(
    semantic_type: object, payload_snapshot: object, case_manager_id: str
) -> bool:
    """True when the entry is the CASE_MANAGER's own ``RM.CLOSED`` status.

    The entry is an ``add_participant_status_to_participant`` entry whose
    snapshot the CASE_MANAGER sent (its ``actor``) about itself (the status's
    ``attributedTo``), with ``rmState`` ``CLOSED`` (CM-23-005).  The
    CASE_MANAGER writes that status only on the Case Owner's
    ``Leave(VulnerabilityCase)`` (CM-23-002 step 2, CM-23-010), or in step 1
    when the Case Owner is the CASE_MANAGER itself.

    Args:
        semantic_type: The entry's ``semantic_type``.
        payload_snapshot: The entry's ``payloadSnapshot``, as the ledger
            carries it.
        case_manager_id: The case's CASE_MANAGER.
    """
    if semantic_type != _PARTICIPANT_STATUS or not isinstance(
        payload_snapshot, Mapping
    ):
        return False
    status = payload_snapshot.get("object")
    if not isinstance(status, Mapping) or status.get(_RM_STATE) != RM.CLOSED:
        return False
    sender = snapshot_actor_id(payload_snapshot.get("actor"))
    subject = snapshot_actor_id(status.get(_ATTRIBUTED_TO))
    return (
        sender is not None
        and subject is not None
        and same_actor_id(sender, case_manager_id)
        and same_actor_id(subject, case_manager_id)
    )


def ledger_records_full_closure(
    entries: Iterable[_LedgerEntryLike], case_manager_id: str
) -> bool:
    """True when *entries* include the CASE_MANAGER's own closure entry.

    Pure: the caller supplies the case's ledger entries (from a store) and
    its CASE_MANAGER.  Order does not matter, because the boundary is a fact
    once committed.
    """
    return any(
        entry_closes_case_manager(
            e.semantic_type, e.payload_snapshot, case_manager_id
        )
        for e in entries
    )


def closure_boundary_indices(
    entries: Iterable[Mapping[str, object]], case_manager_id: str
) -> list[int]:
    """The ``log_index`` of every boundary entry in an exported ledger.

    *entries* are rows in DataLayer shape (``log_index``, ``semantic_type``,
    ``payload_snapshot``), as a demo or the invariant harness reads them.  A
    closed case has exactly one; the caller judges any other count.  Sorted
    ascending.
    """
    return sorted(
        index
        for entry in entries
        if isinstance(index := entry.get("log_index"), int)
        and entry_closes_case_manager(
            entry.get("semantic_type"),
            entry.get("payload_snapshot"),
            case_manager_id,
        )
    )


__all__ = [
    "closure_boundary_indices",
    "entry_closes_case_manager",
    "ledger_records_full_closure",
]
