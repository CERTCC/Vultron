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

"""What a new case's first creation entries carry.

Split from ``proposal_ledger.py`` to keep that module within the BTND-07-004
500-line leaf limit.  :func:`genesis_record` is the genesis entry's snapshot,
the ``Create(VulnerabilityCase)`` the creation built and queued, so the case's
creation is one activity, delivered and ledgered (CLP-07-011, ADR-0157).
:func:`creation_embargoes` is each embargo the creation wrote, which follows
genesis as its own ``create_embargo_event`` entry (CLP-07-013).
"""

import logging

from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.events.base import MessageSemantics
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.trigger_activity import TriggerActivityPort
from vultron.core.services.embargo_ordering import read_embargo_event
from vultron.core.sync_helpers import recorded_entries_for_case
from vultron.errors import VultronError, VultronNotFoundError

logger = logging.getLogger(__name__)

#: ``semantic_type`` of a case's genesis ledger entry, the root of the
#: CASE_MANAGER's hash chain.  Its presence is what "the case's creation
#: entries are committed" means to a later step (CM-14-007, CM-14-011).
CREATE_CASE_SEMANTIC_TYPE = MessageSemantics.CREATE_CASE.value


class _EntryNotCommitted(VultronError):
    """A creation entry the commit tree did not commit (CLP-07-013)."""


def genesis_record(
    datalayer: CasePersistence,
    port: TriggerActivityPort,
    case_id: str,
    create_activity_id: str | None,
) -> tuple[str, str] | None:
    """The genesis entry's ``(activity_id, sealed_body)``, or ``None``.

    The body is the ``Create(VulnerabilityCase)`` the creation built under
    *create_activity_id*, read back from its seal: the activity the case's
    first participant receives is the one the ledger records (CLP-07-011,
    CLP-02-013).  ``None`` when the case already has its genesis entry: a
    proposal that resolved to an existing case (CP-05-008) built no
    ``Create`` and commits none.

    Raises:
        _EntryNotCommitted: The case has no genesis entry and no ``Create``
            was built for it, or none is sealed under *create_activity_id*.
    """
    recorded = recorded_entries_for_case(case_id=case_id, dl=datalayer)
    if any(e.semantic_type == CREATE_CASE_SEMANTIC_TYPE for e in recorded):
        logger.debug(
            "case '%s' already has its genesis entry — not recording another",
            case_id,
        )
        return None
    if not create_activity_id:
        raise _EntryNotCommitted(
            f"case '{case_id}' has no genesis entry and no"
            " Create(VulnerabilityCase) was built for it to record"
            " (CLP-07-011)"
        )
    try:
        return port.record_case_created(create_activity_id=create_activity_id)
    except VultronNotFoundError as exc:
        raise _EntryNotCommitted(
            f"the Create(VulnerabilityCase) '{create_activity_id}' built for"
            f" case '{case_id}' is not sealed: {exc}"
        ) from exc


def creation_embargoes(
    datalayer: CasePersistence, case: VulnerabilityCase
) -> list[EmbargoEvent]:
    """Each embargo *case*'s register names, in register order (CLP-07-013).

    The default embargo, and a contested creation's losing terms
    (EP-04-003).  A replica's embargo decisions read the event's times, so
    no entry may name it by id alone (#5122).

    Raises:
        _EntryNotCommitted: An embargo the register names cannot be read.
    """
    embargoes: list[EmbargoEvent] = []
    for entry in case.embargo_register:
        try:
            embargoes.append(read_embargo_event(datalayer, entry.embargo_id))
        except VultronError as exc:
            raise _EntryNotCommitted(
                f"embargo '{entry.embargo_id}' of case '{case.id_}' cannot"
                f" be read: {exc}"
            ) from exc
    return embargoes


__all__ = [
    "CREATE_CASE_SEMANTIC_TYPE",
    "creation_embargoes",
    "genesis_record",
]
