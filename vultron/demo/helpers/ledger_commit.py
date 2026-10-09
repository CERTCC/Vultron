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

"""Commit a demo ledger entry and fan it out to the case participants.

:func:`trigger_log_commit` drives the ``sync-log-entry`` trigger on an actor so
a test can introduce a *real* canonical ledger entry and then wait for its
replica. It lived in :mod:`vultron.demo.helpers.sync` until that module took on
the shared sync-verification phase helpers (#3846) and reached the CS-18 module
cap; committing is a separate responsibility from verifying replication.
"""

import logging

from vultron.demo.actor_session import ActorSession
from vultron.demo.utils import DataLayerClient
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

logger = logging.getLogger(__name__)


def trigger_log_commit(
    client: DataLayerClient,
    actor_id: str,
    case_id: str,
    event_type: str,
    object_id: str | None = None,
) -> str:
    """Commit a log entry for *case_id* and return the entry hash.

    POSTs to ``/actors/{actor_id}/demo/sync-log-entry`` and returns the
    ``entry_hash`` from the response.  The entry is also fanned out to all
    case participants via ``Announce(CaseLedgerEntry)`` activities queued in the
    actor's outbox.

    Args:
        client: DataLayerClient connected to the CaseActor container.
        actor_id: Full URI of the actor committing the log entry.
        case_id: Full URI of the ``as_VulnerabilityCase``.
        event_type: Short machine-readable event descriptor.
        object_id: Optional URI of the primary object.  Defaults to
            *case_id* when not supplied.

    Returns:
        The ``entry_hash`` of the newly committed log entry.

    Spec: SYNC-02-002, SYNC-02-003.
    """
    session = ActorSession(
        client=client, actor=as_Actor(id_=actor_id)
    ).with_case(as_VulnerabilityCase(id_=case_id))
    result = session.sync_log_entry(
        object_id=object_id if object_id is not None else case_id,
        event_type=event_type,
    )
    entry_hash = result.entry_hash
    logger.info(
        "Log entry committed for case '%s': hash=%s, index=%d",
        case_id,
        entry_hash[:16],
        result.log_index if result.log_index is not None else -1,
    )
    return entry_hash
