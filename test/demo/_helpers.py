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

import contextlib
from collections.abc import Iterator, Mapping, Sequence
from types import ModuleType, SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import httpx2 as httpx
from fastapi.testclient import TestClient

from vultron.demo.actor_session import ActorSession
from vultron.demo.helpers import invite_chain
from vultron.demo.utils import DataLayerClient

# Names the invite chain (``vultron.demo.helpers.invite_chain``) calls itself.
_CHAIN_OWNED = frozenset({"find_case_invite_for_actor"})
# Names both a scenario and the invite chain call, so both are stubbed.
_CHAIN_SHARED = frozenset({"wait_for_case_on_container"})


@contextlib.contextmanager
def patch_chain_shared(
    demo: ModuleType, name: str, **kwargs: Any
) -> Iterator[MagicMock]:
    """Stub *name* on *demo* and on the invite chain with one shared mock.

    Both call it (:data:`_CHAIN_SHARED`), so a test asserting on the mock sees
    the scenario's calls and the chain's alike.
    """
    with patch.object(demo, name, **kwargs) as mock:
        with patch.object(invite_chain, name, new=mock):
            yield mock


def mock_actor(id_: str = "urn:test:actor") -> MagicMock:
    """A stand-in actor whose only observed attribute is ``id_``."""
    actor = MagicMock()
    actor.id_ = id_
    return actor


def mock_case(id_: str = "urn:test:case") -> MagicMock:
    """A stand-in ``as_VulnerabilityCase`` whose only observed attribute is ``id_``."""
    case = MagicMock()
    case.id_ = id_
    return case


@contextlib.contextmanager
def patched_report_submission(
    demo: ModuleType,
    *,
    seed_fn: str,
    seeded_actors: Sequence[MagicMock],
    actor_lookups: Sequence[MagicMock],
    case: MagicMock,
    demo_patches: Mapping[str, Mapping[str, Any]],
    session_patches: Sequence[str] = (),
) -> Iterator[dict[str, MagicMock]]:
    """Patch every collaborator of a scenario's ``_phase_report_submission``.

    One patch stack for the call-shape tests of every scenario module (CS-22-001):
    the seeding, report-submission and RM-triage collaborators are stubbed the
    same way in each, and the scenario's own ``demo_gate`` / ``demo_check`` /
    ``demo_step`` become ``nullcontext`` so a test observes call shapes, never
    gate control flow.  ``ActorSession.invite_actor_to_case`` returns a
    successful invite; further ``ActorSession`` methods named in
    *session_patches* are stubbed bare.

    *demo_patches* maps a name on *demo* to the ``patch.object`` kwargs for it
    (``{}`` for a bare ``MagicMock``).  A collaborator left out of it runs for
    real — that is how a test lets ``wait_for_replica_ledger_coverage`` execute
    while stubbing its primitives elsewhere.

    Yields the mocks by name so the test asserts on the one it cares about.
    """
    with contextlib.ExitStack() as stack:
        mocks: dict[str, MagicMock] = {}
        stack.enter_context(patch.object(demo, "reset_containers"))
        stack.enter_context(
            patch.object(demo, seed_fn, return_value=tuple(seeded_actors))
        )
        stack.enter_context(
            patch.object(
                demo, "get_actor_by_id", side_effect=list(actor_lookups)
            )
        )
        stack.enter_context(
            patch.object(
                demo,
                "reporter_submits_report",
                return_value=(MagicMock(), MagicMock(id_="urn:test:offer")),
            )
        )
        stack.enter_context(
            patch.object(demo, "run_direct_path_rm_triage", return_value=case)
        )
        for name, kwargs in demo_patches.items():
            # The invite chain owns the invite lookup and the invitee's
            # replica wait (#4192); the scenario still owns its other waits.
            if name in _CHAIN_OWNED:
                mocks[name] = stack.enter_context(
                    patch.object(invite_chain, name, **kwargs)
                )
            else:
                mocks[name] = stack.enter_context(
                    patch.object(demo, name, **kwargs)
                )
            if name in _CHAIN_SHARED:
                stack.enter_context(
                    patch.object(invite_chain, name, new=mocks[name])
                )
        mocks["invite_actor_to_case"] = stack.enter_context(
            patch.object(
                ActorSession,
                "invite_actor_to_case",
                return_value=SimpleNamespace(
                    activity=MagicMock(id_="urn:test:invite")
                ),
            )
        )
        for name in session_patches:
            mocks[name] = stack.enter_context(patch.object(ActorSession, name))
        mock_vc = stack.enter_context(
            patch.object(demo, "as_VulnerabilityCase")
        )
        mock_vc.model_validate.return_value = case
        for name in ("demo_gate", "demo_check", "demo_step"):
            stack.enter_context(
                patch.object(
                    demo, name, side_effect=lambda _: contextlib.nullcontext()
                )
            )
        yield mocks


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
        except Exception:  # noqa: BLE001  # ruff-baseline #3989
            return resp.text

    return testclient_call


def make_client(base: str, actor_id: str | None = None) -> DataLayerClient:
    """Return a DataLayerClient pointing at *base*.

    Shared by demo test modules that patch ``DataLayerClient.call`` with
    ``make_testclient_call`` to route requests through a FastAPI TestClient.

    *actor_id* names the actor whose store this client's DataLayer reads address.
    It is optional because many callers only use non-DataLayer endpoints, and
    ``dl_path`` raises rather than guessing (ADR-0073) — so a client that needs it
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

    Copies the participant rows as well as the case.  ``resolve_case_manager_id``
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
    source_dl: Any, case_id: str, db_url: str | None = None
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
        db_url: Storage-deployment template for the target stores. Defaults to
            *source_dl*'s own, which is nearly always what a caller wants: the
            replicas belong beside the case they are replicated from. It must
            match the template the app's ``get_actor_dl`` override uses, and a
            mismatch does not raise — ``get_datalayer`` caches on
            ``(actor_id, db_url)``, so the wrong template seeds a real but
            *separate* database and the routes go on reading an empty one. This
            defaulted to a bare ``sqlite:///:memory:`` while every node shared
            that anonymous template; now that each node gets its own named
            deployment (``test/demo/conftest.py::node_db_url``) a hardcoded
            default would silently seed nothing any node can see.

    Returns:
        Mapping of actor id to the store seeded for it, source actor excluded.
    """
    from vultron.adapters.driven.datalayer_sqlite import get_datalayer

    if db_url is None:
        db_url = getattr(source_dl, "db_url", None)

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
