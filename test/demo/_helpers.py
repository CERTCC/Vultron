#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
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

"""Shared helpers for demo test fixtures."""

from typing import Any

import httpx2 as httpx
from fastapi.testclient import TestClient

from vultron.demo.utils import DataLayerClient


def make_testclient_call(client: TestClient, base: str):
    """Returns a DataLayerClient.call method that routes through TestClient.

    Translates full-URL paths used by demo scripts into relative paths accepted
    by the TestClient, stripping the base URL prefix and ensuring the /api/v2
    prefix is present.

    An HTTP error raises :class:`httpx.HTTPStatusError`, as the real client does,
    **not** a bare ``AssertionError``. Production code distinguishes error codes —
    ``ledger_dump._fetch_entries`` treats a 404 as "this container does not hold
    this case", which is a legitimate outcome — and it does so by catching
    ``HTTPStatusError`` and inspecting ``response.status_code``. A double that
    raises ``AssertionError`` slips past every such handler, so tolerated
    conditions became hard failures that exist only under test. The message is
    preserved in the exception so failures read the same as before.
    """

    def testclient_call(self, method: str, path: Any, **kwargs) -> Any:
        url = str(path)
        if url.startswith(base):
            url = url[len(base) :]
        if not url.startswith("/"):
            url = "/" + url
        if not url.startswith("/api/v2"):
            url = "/api/v2" + url
        resp = client.request(method.upper(), url, **kwargs)
        if resp.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"API call failed: {method.upper()} {url} --> "
                f"{resp.status_code} {resp.text}",
                request=resp.request,
                response=resp,
            )
        try:
            return resp.json()
        except Exception:
            return resp.text

    return testclient_call


def make_client(base: str, actor_id: str | None = None) -> DataLayerClient:
    """Return a DataLayerClient pointing at *base*.

    Shared by demo test modules that patch ``DataLayerClient.call`` with
    ``make_testclient_call`` to route requests through a FastAPI TestClient.

    *actor_id* names the actor whose store this client's DataLayer reads address.
    It is optional because many callers only use non-DataLayer endpoints, and
    ``dl_path`` raises rather than guessing (ADR-0070) — so a client that needs it
    and lacks it fails loudly at the read instead of silently reporting another
    replica's state.
    """
    return DataLayerClient(base_url=base, actor_id=actor_id)


def seed_case_replica_for_actor(
    source_dl: Any, target_dl: Any, case_id: str
) -> Any:
    """Copy *case_id* from *source_dl* into *target_dl*, replica and participants.

    Stands in for the ``Create(VulnerabilityCase)`` the CaseActor would deliver to
    each participant.

    Note on why that delivery does not happen: *not* because nested delivery is
    blocked.  Several comments in this suite claim loopback delivery is "blocked
    at depth > 0 to prevent deadlocks", but nothing implements such a guard —
    ``_TestClientRouter`` dispatches each POST via ``anyio.to_thread.run_sync``
    precisely so nested sends do not deadlock, and multi-hop deliveries are
    observably completing with 202s.  The seeding here compensates for the
    *sender* never queueing the message, not for the transport dropping it.

    Copies the participant rows as well as the case.  ``_resolve_case_manager_id``
    walks ``actor_participant_index`` and does ``dl.read(participant_id)`` on each,
    so a replica holding only the case object resolves no CASE_MANAGER and any
    participant-originated outbound activity fails with "No CASE_MANAGER
    participant found" (PCR-08-001).

    Both stores are passed in rather than derived here via ``clone_for_actor``:
    only ``get_datalayer`` registers an instance, and for an in-memory ``db_url``
    that registry *is* the hosted-actor list, so a cloned store can be the right
    database while leaving the node not hosting that actor.  Callers therefore
    hand over the same instances the routes will be given.

    Returns:
        The target actor's store, so callers can seed further objects into it.
    """
    target = target_dl
    case = source_dl.read(case_id)
    if case is None:
        raise AssertionError(
            f"cannot replicate case {case_id!r}: absent from the source store"
            f" ({getattr(source_dl, 'actor_id', '<unknown>')})"
        )

    # Overwrite an existing replica rather than leaving it alone.  The target
    # often *does* already hold a case row — an earlier `Create(VulnerabilityCase)`
    # delivery can seed a skeleton whose `actor_participant_index` is empty — and
    # "create only if absent" then silently keeps the empty one, which is
    # indistinguishable from this helper never having run.
    if target.read(case_id) is None:
        target.create(case)
    else:
        target.save(case)

    for participant_id in getattr(
        case, "actor_participant_index", {}
    ).values():
        participant = source_dl.read(participant_id)
        if participant is None:
            continue
        if target.read(participant_id) is None:
            target.create(participant)
        else:
            target.save(participant)
    return target


def seed_replicas_for_case_participants(
    source_dl: Any, case_id: str, db_url: str = "sqlite:///:memory:"
) -> dict[str, Any]:
    """Replicate *case_id* into the store of every actor participating in it.

    Stands in for the CaseActor's ``Create(VulnerabilityCase)`` /
    ``Announce(CaseLedgerEntry)`` fan-out, which seeds each participant's replica
    in a real deployment.

    The CaseActor's own replica matters as much as the participants':
    ``CheckIsCaseManagerNode`` reads the case from the store of the actor
    executing the tree, so a CaseActor with no case fails the role gate with
    "case not found in DataLayer" — which reads like a *role* problem and is
    really a *replica* problem. The gate then skips silently, no ledger entry is
    committed, and nothing is announced onward.

    Args:
        source_dl: Store holding the authoritative case (usually the owner's).
        case_id: Case to replicate.
        db_url: Backing URL for the target stores; must match the one the app's
            ``get_actor_dl`` override uses or the routes will read a different
            database.

    Returns:
        Mapping of actor id to the store seeded for it, source actor excluded.
    """
    from vultron.adapters.driven.datalayer_sqlite import get_datalayer

    case = source_dl.read(case_id)
    if case is None:
        raise AssertionError(
            f"cannot replicate case {case_id!r}: absent from the source store"
            f" ({getattr(source_dl, 'actor_id', '<unknown>')})"
        )

    seeded: dict[str, Any] = {}
    own = getattr(source_dl, "actor_id", None)
    for actor_id in getattr(case, "actor_participant_index", {}):
        if actor_id == own:
            continue
        target = get_datalayer(actor_id, db_url=db_url)
        seed_case_replica_for_actor(source_dl, target, case_id)
        seeded[actor_id] = target
    return seeded
