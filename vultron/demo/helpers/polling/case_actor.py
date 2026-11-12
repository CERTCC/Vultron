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

"""Locating the CaseActor and the store its authoritative state is read from.

Under ADR-0073 the CaseActor has a store of its own, so a demo read of the
CASE_MANAGER's state must name it; these helpers resolve which store that is.
"""

import logging

from vultron.adapters.utils import parse_id, strip_id_prefix
from vultron.demo.utils import (
    CASE_ACTOR_SLUG,
    DataLayerClient,
)
from vultron.demo.utils.served import from_server
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

logger = logging.getLogger(__name__)


def case_actor_participant_id_in(case: as_VulnerabilityCase) -> str | None:
    """Return the CaseActor's actor URI from *case*'s participant index.

    The read-free half of :func:`find_case_actor_participant_id`, for callers
    that already hold the case (e.g. the one
    :func:`~vultron.demo.helpers.workflow.setup_canonical_case` just polled for)
    and would otherwise have to name a store to re-read it from.
    """
    for actor_id in case.actor_participant_index:
        if strip_id_prefix(actor_id).startswith(CASE_ACTOR_SLUG):
            return actor_id
    return None


def find_case_actor_participant_id(
    client: DataLayerClient,
    case_id: str,
) -> str | None:
    """Return the CaseActor's *actor* URI for *case_id* from *client*'s replica.

    Scans ``actor_participant_index`` for an actor ID whose bare segment starts
    with ``"case-actor"``.  A single read, not a poll: callers use it to resolve
    the CaseActor's URI once the case replica is already known to be present.

    The index is keyed by actor URI (its values are the participant-record
    URIs), so what comes back names the CaseActor itself — it is usable as a
    ``DataLayerClient.dl_path`` actor scope, which is what
    :func:`resolve_case_actor_store_id` builds on.

    Args:
        client: DataLayerClient connected to any container holding the case.
        case_id: Full URI of the ``as_VulnerabilityCase``.

    Returns:
        The CaseActor's actor URI, or ``None`` when the case is unreadable
        or has no CaseActor participant.
    """
    try:
        case_data = client.get(client.dl_path(case_id))
        return case_actor_participant_id_in(
            from_server(as_VulnerabilityCase, case_data)
        )
    except Exception:  # noqa: BLE001, S110  # ruff-baseline #3326
        pass
    return None


def resolve_case_actor_store_id(
    client: DataLayerClient,
    case_id: str,
) -> str | None:
    """Return the CaseActor URI to read *case_id*'s authoritative state through.

    A CaseActor owns the case: it is where the participant records are written
    when it applies an RM/EM transition.  Under ADR-0073#peer-records-in-knowers-store it also has
    a store of its own, so a participant's authoritative state is *not* visible
    in the store of the actor that merely self-hosts it — the host's replica
    only advances when a ledger entry it recognises tells it to, and the
    per-participant RM transitions the CaseActor makes are not ledgered as
    ``add_participant_status_to_participant`` events.  Reading the host's
    replica therefore reports a stale ``RM.START`` indefinitely.

    Returns ``None`` — meaning "read *client*'s own actor, as before" — when
    either the case has no CaseActor participant, or the CaseActor lives in some
    other container.  In the latter case *client* cannot address its store at
    all, and scoping to it would 404 on every poll rather than fall back.

    Args:
        client: DataLayerClient for the container to read through.
        case_id: Full URI of the ``as_VulnerabilityCase``.

    Returns:
        The CaseActor's actor URI when it is co-hosted with *client*'s own
        actor, else ``None``.
    """
    case_actor_id = find_case_actor_participant_id(client, case_id)
    if case_actor_id is None or client.actor_id is None:
        return None
    if (
        parse_id(case_actor_id)["base_url"]
        != parse_id(client.actor_id)["base_url"]
    ):
        logger.debug(
            "CaseActor %s is not hosted by %s — reading %s's own store",
            case_actor_id,
            client.base_url,
            client.actor_id,
        )
        return None
    return case_actor_id


def case_manager_store(
    client: DataLayerClient,
    case_id: str,
    case_manager_client: DataLayerClient | None = None,
) -> tuple[DataLayerClient, str | None]:
    """Return ``(client, dl_actor_id)`` to read *case_id*'s CASE_MANAGER store.

    When the CaseActor runs in its own container — the dedicated case-actor
    container of the Docker scenarios (DEMOMA-06-004) — no participant's
    container can address its store, and a participant's replica is no
    substitute: the CaseActor applies some participant transitions without a
    ledger entry, so a replica can lag them indefinitely.  *case_manager_client*
    names that container, bound to the CaseActor, and is read as-is.

    Without one, *client* is read, scoped to a CaseActor it co-hosts
    (:func:`resolve_case_actor_store_id`) — the single-container exchange demos.

    Args:
        client: The participant client the caller would otherwise read through.
        case_id: Full URI of the ``as_VulnerabilityCase``.
        case_manager_client: Client for the CaseActor's own container, if the
            caller has one.

    Returns:
        The client to read through and the ``dl_path`` actor scope to pass it.
    """
    if case_manager_client is not None:
        return case_manager_client, None
    return client, resolve_case_actor_store_id(client, case_id)
