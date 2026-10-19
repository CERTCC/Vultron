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
import importlib
import logging
from collections.abc import Iterator, Mapping, Sequence
from types import ModuleType, SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import httpx2 as httpx
import pytest
from _pytest.monkeypatch import MonkeyPatch
from fastapi.testclient import TestClient

import vultron.demo.utils as demo_utils
from test.support.ledger import ledger_entries
from test.support.ledger_rebuild import (
    assert_rebuilds_from_ledger,
    replica_actor,
)
from vultron.adapters.driven.datalayer_sqlite import get_all_actor_datalayers
from vultron.core.models.case import VulnerabilityCase
from vultron.core.participants.authority import resolve_case_manager_id
from vultron.demo.actor_session import ActorSession
from vultron.demo.helpers import invite_chain, runner, workflow
from vultron.demo.utils import DataLayerClient
from vultron.errors import VultronError

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
        # Append a placeholder for the case-actor lookup added in #4165: the
        # CASE_MANAGER actor looked up to call set-stub-summary before each
        # invite in _phase_report_submission.
        stack.enter_context(
            patch.object(
                demo,
                "get_actor_by_id",
                side_effect=[*list(actor_lookups), MagicMock()],
            )
        )
        # set_stub_summary is seeding infrastructure not under test here;
        # stub it so tests do not fail on Pydantic validation of a MagicMock.
        stack.enter_context(patch.object(ActorSession, "set_stub_summary"))
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


@contextlib.contextmanager
def stub_closure_gate() -> Iterator[MagicMock]:
    """Satisfy the owner-last gate in ``close_case_owner_last`` without a store.

    A mocked closure-phase test has no CASE_MANAGER store to read, so the
    gate's ``RM.CLOSED`` wait would poll a ``MagicMock`` until it timed out and
    then skip the owner's ``Leave``.  Patching the wait to return at once, and
    the owner's replica-EM wait, and the closure checks the helper runs after
    the owner leaves (the ledger
    order, every record ``RM.CLOSED`` in the CASE_MANAGER's store, and each
    leaver's own replica), lets such a test check what it is about (call
    order, which milestones run).  The CASE_MANAGER's client is the authority
    client itself.
    Yields the patched wait so a test can assert which departures it waited on.
    """
    with (
        patch(
            "vultron.demo.helpers.closure._case_manager_reader",
            side_effect=lambda client, _case_id: client,
        ),
        patch(
            "vultron.demo.helpers.closure.wait_for_participant_rm_state"
        ) as wait,
        patch("vultron.demo.helpers.closure.verify_case_closure_recorded"),
        patch("vultron.demo.helpers.closure.verify_case_closed"),
        patch(
            "vultron.demo.helpers.closure.case_manager_ledger",
            return_value=[],
        ),
        patch("vultron.demo.helpers.closure._verify_own_closure"),
        patch("vultron.demo.helpers.closure._wait_for_owner_replica_em"),
    ):
        yield wait


#: Each case an exchange demo left behind that did not rebuild from its
#: ledger, as a message; checked after every demo test (``conftest``).
REBUILD_FAILURES: list[str] = []

#: Each case the check rebuilt, with its ledger's event types, so a test can
#: see what it covered.
REBUILT_CASES: list[tuple[str, list[str]]] = []


def _managed_cases() -> Iterator[tuple[Any, str]]:
    """``(store, case id)`` for every case a hosted actor manages."""
    for actor_id, dl in get_all_actor_datalayers().items():
        for case in dl.list_objects("VulnerabilityCase"):
            if not isinstance(case, VulnerabilityCase):
                continue
            try:
                manager_id = resolve_case_manager_id(case, dl)
            except VultronError:
                continue  # a case this store names no CASE_MANAGER for
            if (
                manager_id == actor_id
                and ledger_entries(dl, case.id_)
                and replica_actor(dl, case.id_) is not None
            ):
                yield dl, case.id_


def check_cases_rebuild_from_their_ledgers() -> None:
    """Rebuild every managed case from its ledger alone (#4294 AC-5).

    Run before the demo's teardown clears the node.  A case whose rebuild
    differs from its CASE_MANAGER's, or fails in any other way, is recorded in
    :data:`REBUILD_FAILURES` rather than raised, because the demo runner would
    log a raise as a failed demo and hide the difference.  Logging is silenced
    while it runs: the rebuild's own log lines are not the demo's, and the demo
    tests fail on any ERROR they capture.
    """
    logging.disable(logging.CRITICAL)
    try:
        for dl, case_id in list(_managed_cases()):
            REBUILT_CASES.append(
                (
                    case_id,
                    [str(e.event_type) for e in ledger_entries(dl, case_id)],
                )
            )
            try:
                assert_rebuilds_from_ledger(dl, case_id)
            except Exception as exc:  # noqa: BLE001 — recorded, then failed
                REBUILD_FAILURES.append(
                    f"'{case_id}': {type(exc).__name__}: {exc}"
                )
    finally:
        logging.disable(logging.NOTSET)


def assert_no_rebuild_failures() -> None:
    """Fail with every recorded rebuild failure, and clear the record."""
    failures = list(REBUILD_FAILURES)
    REBUILD_FAILURES.clear()
    assert not failures, "\n\n".join(failures)


@contextlib.contextmanager
def route_exchange_demo_at_testclient(
    client: TestClient, demo: ModuleType, *also: ModuleType
) -> Iterator[str]:
    """Route an exchange demo's clients at the in-process *client*; yield the base.

    Patches ``demo.BASE_URL`` and ``demo.DataLayerClient.call`` so requests go
    through the TestClient.  The runner (``run_exchange_demos``) builds its own
    ``DataLayerClient()`` at ``localhost:7999``, but the in-process node hosts
    actors under ``http://testserver``, and ``ActorSession`` refuses a client
    whose base URL is not the authority that hosts the actor (DEMOMA-26-002).
    So the runner's client is also *built* at the test server's base.

    *also* names further demo modules (e.g. ``initialize_case_demo``) whose
    ``BASE_URL`` must point at the same server; each is patched like *demo* and
    reloaded on exit.

    Before each teardown clears the node, every case a hosted actor manages is
    rebuilt from its ledger alone and compared with the CASE_MANAGER's
    (:func:`check_cases_rebuild_from_their_ledgers`, #4294 AC-5).

    Every patch is undone on exit and *demo* and each of *also* is reloaded, so
    nothing leaks into later modules.
    """
    mp = MonkeyPatch()
    base = str(client.base_url).rstrip("/") + "/api/v2"
    try:
        for module in (demo, *also):
            mp.setattr(module, "BASE_URL", base, raising=False)
        mp.setattr(
            demo.DataLayerClient, "call", make_testclient_call(client, base)
        )
        mp.setattr(runner, "DataLayerClient", lambda: make_client(base))
        reset = demo_utils.reset_datalayer

        def _check_then_reset(client: DataLayerClient) -> dict:
            try:
                check_cases_rebuild_from_their_ledgers()
            finally:
                result = reset(client=client)
            return result

        # Every exchange demo tears down through ``demo_environment``, which
        # clears the node with this function: check the cases first.
        mp.setattr(demo_utils, "reset_datalayer", _check_then_reset)
        yield base
    finally:
        mp.undo()
        for module in (demo, *also):
            importlib.reload(module)


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


def null_demo_contexts(stack: contextlib.ExitStack, demo: ModuleType) -> None:
    """Make *demo*'s ``demo_gate``/``demo_check``/``demo_step`` transparent.

    For call-shape tests that observe which client a scenario hands a helper,
    never gate control flow (``test_demo_context_managers.py`` covers that).
    """
    for name in ("demo_gate", "demo_check", "demo_step"):
        stack.enter_context(
            patch.object(
                demo, name, side_effect=lambda _: contextlib.nullcontext()
            )
        )


def assert_reset_reseeds_case_actor(
    demo: ModuleType, participant_clients: Mapping[str, MagicMock]
) -> None:
    """Run *demo*'s ``reset_containers`` and check the case-actor half (#1876).

    The participants are reset in the order given, the dedicated case-actor
    container after them, and its CaseActor identity is then re-seeded — the
    reset wipes it, and every proposal is delivered to it.

    Args:
        demo: The scenario module under test.
        participant_clients: ``reset_containers`` keyword → client, in the
            scenario's reset order.
    """
    case_actor_client = MagicMock(name="case_actor_client")
    for client in (*participant_clients.values(), case_actor_client):
        client.get.return_value = {}

    with (
        patch.object(
            demo, "reset_datalayer", return_value={"status": "ok"}
        ) as reset_mock,
        patch(
            "vultron.demo.helpers.seeding.seed_case_actor_identity"
        ) as reseed_mock,
    ):
        demo.reset_containers(
            case_actor_client=case_actor_client, **participant_clients
        )

    reset_clients = [c.kwargs["client"] for c in reset_mock.call_args_list]
    assert reset_clients == [*participant_clients.values(), case_actor_client]
    reseed_mock.assert_called_once_with(case_actor_client)


def _reporter_links(
    reporter_id: str, report_id: str
) -> list[tuple[str | None, str | None]]:
    """``(case_creator_id, case_id)`` of each of the reporter's links for a report.

    Read from the reporter's own store, where the links are written.
    """
    from vultron.adapters.driven.datalayer_sqlite import get_datalayer
    from vultron.core.models.report_case_link import VultronReportCaseLink

    return [
        (link.case_creator_id, link.case_id)
        for link in get_datalayer(reporter_id).list_objects("ReportCaseLink")
        if isinstance(link, VultronReportCaseLink)
        and link.report_id == report_id
    ]


@contextlib.contextmanager
def expect_trusted_introductions(
    caplog: pytest.LogCaptureFixture,
) -> Iterator[None]:
    """Assert every reporter took its receiver's case introduction as trusted.

    Wrap a demo run in this.  It records each call the demo makes to
    ``wait_for_reporter_introduction`` and, while the reporter's store still
    holds the result (the exchange runner resets it on teardown), reads the
    reporter's own ``ReportCaseLink`` for the report.  A wait that fails is
    recorded too, then re-raised for the demo's ``demo_check`` to record.
    On exit it asserts that at least one introduction was checked, that each
    link names the receiver as ``case_creator_id`` and is bound to the case
    the wait found (the case the demo expected, when it passed one;
    CBT-01-001, CBT-01-005), and that nothing logged a ``CBT-01-011``
    refusal.  The refusal is logged at WARNING, so the caller's ``caplog``
    level must let WARNING records through; entering at a higher level fails
    at once (#4675).
    """
    assert caplog.handler.level <= logging.WARNING, (
        "expect_trusted_introductions needs caplog at WARNING or lower, or a"
        " CBT-01-011 refusal could not be seen"
    )
    checked: list[tuple[str, str | None, list[tuple[str | None, str | None]]]]
    checked = []
    real_wait = workflow.wait_for_reporter_introduction

    def _recording_wait(
        client: DataLayerClient,
        reporter_id: str,
        receiver_id: str,
        report_id: str,
        **kwargs: Any,
    ) -> str:
        try:
            case_id = real_wait(
                client, reporter_id, receiver_id, report_id, **kwargs
            )
        except AssertionError:
            checked.append(
                (receiver_id, None, _reporter_links(reporter_id, report_id))
            )
            raise
        checked.append(
            (receiver_id, case_id, _reporter_links(reporter_id, report_id))
        )
        return case_id

    with patch.object(
        workflow, "wait_for_reporter_introduction", side_effect=_recording_wait
    ):
        yield

    refusals = [
        record.getMessage()
        for record in caplog.records
        if "(CBT-01-011)" in record.getMessage()
    ]
    assert not refusals, (
        "a reporter refused its receiver's case introduction:\n"
        + "\n".join(refusals)
    )
    assert checked, "the demo never checked the reporter's introduction"
    for receiver_id, case_id, links in checked:
        assert case_id is not None, (
            f"the reporter's ReportCaseLink was never bound by {receiver_id!r}'s"
            f" introduction; it holds {links!r}"
        )
        assert links == [(receiver_id, case_id)], (
            f"the reporter's ReportCaseLink should name {receiver_id!r} and be"
            f" bound to {case_id!r}; it holds {links!r}"
        )
