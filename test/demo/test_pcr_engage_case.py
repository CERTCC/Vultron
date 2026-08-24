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

"""Integration tests for the engage-case (Join) path (#572, #573, #574).

Verifies that when an owner triggers ``engage-case``, the outbound
``Join(VulnerabilityCase)`` carries expanded participant objects (not bare
URI strings), and that the receiving actor's ``EngageCaseReceivedUseCase``
stores those participant objects in the receiver's DataLayer before running
the BT.

Coverage
--------
- **#572 (send side):** ``dl.hydrate()`` expands ``case_participants`` bare
  strings to full ``CaseParticipant`` objects in the outbound
  ``Join(VulnerabilityCase)`` before delivery.
- **#573 (receive side):** ``EngageCaseReceivedUseCase`` calls
  ``_store_embedded_participants`` so the sender's ``CaseParticipant`` is
  persisted in the receiver's DataLayer before ``EngageCaseBT`` runs.
- **#574 (demo):** The full owner-validate → engage-case sequence completes
  without a BT timeout.

These tests exercise the full outbox → inbox dispatch path using real
in-memory ``SqliteDataLayer`` instances — use cases are not mocked.  They
are auto-marked as ``@pytest.mark.integration`` by the conftest hook in
``test/demo/``.
"""

import asyncio

import pytest

from test.demo.conftest import _TestClientRouter, create_isolated_actor_app
from vultron.adapters.driving.fastapi.outbox_handler import outbox_handler
from vultron.core.models.report_case_link import VultronReportCaseLink
from vultron.core.use_cases._helpers import _find_case_actor_id
from vultron.demo.utils import case_actor_id_for_report
from vultron.wire.as2.factories import rm_submit_report_activity
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

# ---------------------------------------------------------------------------
# Constants — all IDs use HTTP-routable URIs
# ---------------------------------------------------------------------------

_OWNER_BASE = "http://owner-engage-case.test"
_REPORTER_BASE = "http://reporter-engage-case.test"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def two_app_setup(monkeypatch):
    """Owner app + reporter app wired for end-to-end delivery.

    Uses two isolated FastAPI app instances each with their own in-memory
    ``SqliteDataLayer``.  A shared ``_TestClientRouter`` routes outbound
    deliveries between the apps in-process so the full
    outbox → inbox → inbox-handler chain is exercised without real HTTP.

    Lifecycle:
      1. Patches ``VULTRON_SERVER__BASE_URL`` to ``{_OWNER_BASE}/api/v2``
         and reloads the config cache so ``CreateCaseActorNode`` builds
         the CaseActor ID using the owner's routable base URL (not the
         default ``http://localhost:7999`` which lacks the ``/api/v2/``
         prefix and therefore gets a 404 from the owner's ASGI app).
      2. Enters both TestClient contexts (triggers lifespan startup).
      3. Configures the module-level default emitter to the shared router so
         all outbox_handler deliveries POST to each target TestClient inbox
         instead of making real HTTP requests (ADR-0042).
      4. Registers the patched base URL with the router so that CaseActor
         deliveries are routed to the owner's app correctly.

    Yields:
        Tuple of (owner_iso, reporter_iso, owner_tc, reporter_tc).
    """
    from vultron.adapters.driving.fastapi.outbox_handler import (
        configure_default_emitter,
        get_default_emitter,
    )
    from vultron.config import get_config, reload_config

    # Patch the server base URL so the CaseActor is created with the owner's
    # routable base URL.  Without this, CreateCaseActorNode reads the default
    # http://localhost:7999 which produces IDs like
    # http://localhost:7999/actors/case-actor-... and the owner's app returns
    # 404 for /actors/ paths (it expects /api/v2/actors/).
    monkeypatch.setenv("VULTRON_SERVER__BASE_URL", f"{_OWNER_BASE}/api/v2")
    # ResolveCaseActorUrlsNode reads case_actor_service_url from ActorConfig
    # (CP-08-002); in this single-owner test setup the owner IS the case-actor
    # service, so we point it at the same base URL.
    monkeypatch.setenv(
        "VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL", f"{_OWNER_BASE}/api/v2"
    )
    reload_config()

    router = _TestClientRouter()
    owner_iso = create_isolated_actor_app(base_url=_OWNER_BASE, router=router)
    reporter_iso = create_isolated_actor_app(
        base_url=_REPORTER_BASE, router=router
    )

    config_base_url = get_config().server.base_url.rstrip("/")
    router.register(config_base_url, owner_iso.client)

    previous_emitter = get_default_emitter()
    configure_default_emitter(router)  # type: ignore[arg-type]

    with owner_iso.client as owner_tc:
        with reporter_iso.client as reporter_tc:
            yield (owner_iso, reporter_iso, owner_tc, reporter_tc)

    configure_default_emitter(previous_emitter)  # type: ignore[arg-type]
    owner_iso.dl.close()
    reporter_iso.dl.close()
    # Undo the env patches BEFORE reloading: monkeypatch's own undo runs after
    # this teardown, so reloading first would re-cache this fixture's URLs into
    # the module-level config for the rest of the session (#2086).
    monkeypatch.undo()
    reload_config()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_actor(client, base_api: str, slug: str, name: str) -> str:
    """Create an Organization actor and return its full ID."""
    actor_id = f"{base_api}/actors/{slug}"
    resp = client.post(
        "/api/v2/actors/",
        json={"type": "Organization", "name": name, "id": actor_id},
    )
    assert resp.status_code in (
        200,
        201,
    ), f"Actor creation failed ({resp.status_code}): {resp.text}"
    return actor_id


def _post_to_inbox(client, actor_slug: str, activity) -> None:
    """POST *activity* JSON to ``/api/v2/actors/{actor_slug}/inbox/``."""
    resp = client.post(
        f"/api/v2/actors/{actor_slug}/inbox/",
        content=activity.model_dump_json(by_alias=True, exclude_none=True),
        headers={"Content-Type": "application/json"},
    )
    assert (
        resp.status_code == 202
    ), f"Inbox POST returned {resp.status_code}: {resp.text}"


def _actor_slug(actor_id: str) -> str:
    """Return the last path segment of *actor_id*."""
    return actor_id.rstrip("/").rsplit("/", 1)[-1]


def _drain_case_actor_outbox(owner_iso, case_actor_id: str) -> None:
    """Drain the CaseActor's outbox via the real outbox_handler.

    Args:
        owner_iso: Owner's ``IsolatedActorApp`` (contains the CaseActor's
            outbox queue and the activity objects).
        case_actor_id: Full ID of the CaseActor.
    """
    # The CaseActor's own store, and no close(): it is the app's live store,
    # and an in-memory store is named, so disposing the engine destroys the
    # database every other holder shares.
    case_actor_dl = owner_iso.store_for(case_actor_id)
    asyncio.run(outbox_handler(case_actor_id, case_actor_dl))


def _bootstrap_and_engage(
    owner_iso,
    reporter_iso,
    owner_tc,
    reporter_tc,
    owner_slug: str,
    reporter_slug: str,
) -> tuple[str, str, str]:
    """Run the full bootstrap + engage-case sequence.

    Steps:
      1. Reporter submits ``SubmitReport`` offer to owner's inbox.
      2. Owner validates the report (``trigger/validate-report``).
      3. CaseActor's outbox is drained so ``Create(VulnerabilityCase)``
         is delivered to reporter's inbox.
      4. Owner triggers ``engage-case`` to send ``Join(VulnerabilityCase)``
         to the CaseActor.  Background task drains owner's outbox automatically.
      5. CaseActor's outbox is drained again so ``Announce(VulnerabilityCase)``
         (queued by ``EngageCaseBT → BroadcastCaseUpdateNode``) reaches reporter.

    Returns:
        Tuple of (case_id, owner_actor_id, reporter_actor_id).  The actor ids
        are returned so callers can open each actor's own store rather than
        rebuilding a per-test slug.
    """
    owner_base_api = owner_iso.base_url + "/api/v2"
    reporter_base_api = reporter_iso.base_url + "/api/v2"

    owner_actor_id = _create_actor(
        owner_tc, owner_base_api, owner_slug, "Owner"
    )
    reporter_actor_id = _create_actor(
        reporter_tc, reporter_base_api, reporter_slug, "Reporter"
    )

    # Owner's app must know the reporter so outbound Create is routable.
    _create_actor(owner_tc, reporter_base_api, reporter_slug, "Reporter")

    report = as_VulnerabilityReport(
        attributed_to=reporter_actor_id,
        name="PCR engage-case integration test report",
        content=(
            "Integration test vulnerability report for #572/#573/#574 "
            "regression coverage."
        ),
    )
    offer = rm_submit_report_activity(
        report,
        actor=reporter_actor_id,
        target=owner_actor_id,
        to=owner_actor_id,
    )
    # Provision the CaseActor the case-creation flow will address.  Its id is
    # *derived* from the report (ResolveCaseActorUrlsNode) and the owner is the
    # case-actor service in this setup, so the owner's node must host it or the
    # Announce/Invite deliveries to it answer 404.  Spawning one on demand for an
    # as-yet-unknown case is #2469 / #1700.
    _create_actor(
        owner_tc,
        owner_base_api,
        _actor_slug(case_actor_id_for_report(str(report.id_))),
        "Case Actor",
    )
    _post_to_inbox(owner_tc, _actor_slug(owner_actor_id), offer)

    # ADR-0041: receive_report_case_tree writes a VultronReportCaseLink and
    # sends Create(as_CaseProposal) — no VulnerabilityCase yet.
    # Simulate the CaseActor's Create(VulnerabilityCase) response directly.
    # Pass reporter as `to` so the outbound activity satisfies OX-08-001.
    resp = owner_tc.post(
        f"/api/v2/actors/{_actor_slug(owner_actor_id)}/trigger/create-case",
        json={
            "name": "PCR engage-case integration test case",
            "content": "Case seeded by trigger/create-case (ADR-0041).",
            "report_id": report.id_,
            "to": [reporter_actor_id],
        },
    )
    assert (
        resp.status_code == 202
    ), f"trigger/create-case failed ({resp.status_code}): {resp.text}"

    # Find the canonical case by report_id to avoid picking up the extra
    # VulnerabilityCase created by trigger/create-case above (ADR-0041 flow
    # also creates one via case_proposal_received_tree).
    # The owner's own store, not `owner_iso.dl`: this test creates its actor
    # under a per-test slug, while `dl` is the app's default-slug store, so
    # reading `dl` reports an empty store and the assertion fails for the wrong
    # reason (ADR-0071 — a store is exactly one actor's).
    owner_dl = owner_iso.store_for(owner_actor_id)

    case_from_proposal = owner_dl.find_case_by_report_id(report.id_)
    case_id: str
    if case_from_proposal is not None:
        case_id = str(case_from_proposal.id_)
    else:
        all_cases = owner_dl.get_all("VulnerabilityCase")
        assert len(all_cases) >= 1, (
            "Expected at least one VulnerabilityCase in owner's DataLayer "
            "after trigger/create-case."
        )
        case_id = str(all_cases[0]["id_"])

    # In this test the owner acts as the CaseActor.  Register that identity
    # in the VultronReportCaseLink so _find_case_actor_id resolves correctly.
    for link in owner_dl.list_objects("ReportCaseLink"):
        if isinstance(link, VultronReportCaseLink):
            link.case_id = case_id
            link.trusted_case_actor_id = owner_actor_id
            owner_dl.save(link)
            break

    # Validate the report → CaseActor queues Create(VulnerabilityCase).
    resp = owner_tc.post(
        f"/api/v2/actors/{_actor_slug(owner_actor_id)}/trigger/validate-report",
        json={"offer_id": offer.id_},
    )
    assert (
        resp.status_code == 202
    ), f"validate-report trigger failed ({resp.status_code}): {resp.text}"

    # Drain CaseActor's outbox so Create(VulnerabilityCase) reaches reporter.
    case_actor_id = _find_case_actor_id(owner_dl, case_id)
    assert (
        case_actor_id is not None
    ), f"Could not find CaseActor for case '{case_id}' in owner's DataLayer."
    _drain_case_actor_outbox(owner_iso, case_actor_id)

    # Reporter must have received the case replica before engage-case fires.
    # The reporter's own store, not the app's default-slug `dl`: the actor was
    # created under a per-test slug, and a store belongs to exactly one actor
    # (ADR-0071), so `dl` is a different (empty) database.
    reporter_dl = reporter_iso.store_for(reporter_actor_id)
    reporter_cases = reporter_dl.get_all("VulnerabilityCase")
    assert any(c["id_"] == case_id for c in reporter_cases), (
        f"Reporter did not receive a case replica for '{case_id}' after "
        f"CaseActor outbox drain.  The Create(VulnerabilityCase) path may "
        f"be broken."
    )

    # Owner triggers engage-case → Join(VulnerabilityCase) queued and
    # delivered to the CaseActor via the background task outbox drain.
    # The CaseActor runs EngageCaseBT (updates owner's RM → ACCEPTED) and
    # queues Announce(VulnerabilityCase) to all participants.
    resp = owner_tc.post(
        f"/api/v2/actors/{_actor_slug(owner_actor_id)}/trigger/engage-case",
        json={"case_id": case_id},
    )
    assert (
        resp.status_code == 202
    ), f"engage-case trigger failed ({resp.status_code}): {resp.text}"

    # Drain CaseActor's outbox so the Announce(VulnerabilityCase) reaches the
    # reporter.  EngageCaseBT queues the broadcast after updating RM state;
    # this delivery path makes the owner's CaseParticipant available in the
    # reporter's DataLayer (CBT-05-004, #572, #573).
    _drain_case_actor_outbox(owner_iso, case_actor_id)

    return case_id, owner_actor_id, reporter_actor_id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.spec("CBT-05-004")
class TestEngageCaseParticipantExpansion:
    """Integration regression tests for #572, #573, #574.

    Exercises the full ``engage-case`` trigger → outbox delivery →
    ``EngageCaseReceivedUseCase`` path using real DataLayer instances and
    the TestClient router between apps.  No use-cases, DataLayer methods, or
    outbox handler functions are mocked.

    AC-1: Reporter's DataLayer contains the owner's CaseParticipant record
    after receiving ``Join(VulnerabilityCase)`` (#572 send-side + #573
    receive-side).

    AC-2: Reporter's actor inbox queue is drained (``EngageCaseBT`` ran to
    completion; no timeout) (#574).
    """

    def test_engage_case_stores_owner_participant_in_reporter_dl(
        self, two_app_setup
    ):
        """AC-1: Reporter's DataLayer has owner's CaseParticipant after Join.

        Verifies end-to-end:
        - Outbound ``Join(VulnerabilityCase)`` carries expanded participant
          objects (``dl.hydrate()`` is responsible — #572 regression).
        - ``EngageCaseReceivedUseCase`` calls ``_store_embedded_participants``
          before running ``EngageCaseBT``, so the owner's ``CaseParticipant``
          is persisted in reporter's DataLayer (#573 regression).
        """
        owner_iso, reporter_iso, owner_tc, reporter_tc = two_app_setup

        case_id, owner_actor_id, reporter_actor_id = _bootstrap_and_engage(
            owner_iso,
            reporter_iso,
            owner_tc,
            reporter_tc,
            owner_slug="owner-pcr-572-ac1",
            reporter_slug="reporter-pcr-572-ac1",
        )

        participants_in_reporter_dl = list(
            reporter_iso.store_for(reporter_actor_id).list_objects(
                "CaseParticipant"
            )
        )
        owner_participant_ids = [
            getattr(p, "attributed_to", None)
            for p in participants_in_reporter_dl
        ]
        assert any(
            pid == owner_actor_id
            or (isinstance(pid, str) and owner_actor_id in pid)
            for pid in owner_participant_ids
        ), (
            f"Owner's CaseParticipant (attributed_to='{owner_actor_id}') "
            f"not found in reporter's DataLayer after receiving "
            f"Join(VulnerabilityCase) for case '{case_id}'.  "
            f"_store_embedded_participants may not have been called in "
            f"EngageCaseReceivedUseCase (#573), or participant expansion "
            f"was not performed on the outbound activity (#572).  "
            f"CaseParticipants found: "
            f"{[getattr(p, 'attributed_to', None) for p in participants_in_reporter_dl]!r}"
        )

    def test_engage_case_drains_reporter_inbox(self, two_app_setup):
        """AC-2: EngageCaseBT runs to completion (inbox queue drained).

        Verifies that ``EngageCaseReceivedUseCase`` completes without a BT
        timeout (#574): after the full sequence the reporter actor's inbox
        queue must be empty, confirming the inbox handler ran and dispatch
        completed.
        """
        owner_iso, reporter_iso, owner_tc, reporter_tc = two_app_setup

        case_id, owner_actor_id, reporter_actor_id = _bootstrap_and_engage(
            owner_iso,
            reporter_iso,
            owner_tc,
            reporter_tc,
            owner_slug="owner-pcr-572-ac2",
            reporter_slug="reporter-pcr-572-ac2",
        )

        # The reporter's id comes back from the bootstrap helper; scanning its
        # store for "the first Organization" was a guess that also happened to
        # read the wrong (default-slug) store.
        reporter_actor_dl = reporter_iso.store_for(reporter_actor_id)
        # No close(): this is the app's live store, and an in-memory store is
        # named, so disposing the engine destroys the database the app shares.
        pending = reporter_actor_dl.inbox_list()
        assert pending == [], (
            f"Reporter actor inbox queue is not empty after "
            f"Join(VulnerabilityCase) processing.  "
            f"EngageCaseBT may have failed or timed out (#574).  "
            f"Pending items: {pending!r}"
        )
