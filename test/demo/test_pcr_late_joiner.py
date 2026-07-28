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

"""Integration tests for PCR-07-007: late-joiner sequence.

Verifies: case owner invites a late-joining participant → late-joiner accepts
→ CaseActor emits ``Announce(VulnerabilityCase)`` → late-joiner creates a
local case replica that includes them as a participant.

These tests exercise the full invite/accept/Announce dispatch path using real
in-memory SQLite DataLayer instances — use cases are not mocked.  They are
auto-marked as ``@pytest.mark.integration`` by the conftest hook in
``test/demo/``.

Coverage approach
-----------------
Both test methods in ``TestLateJoinerSequence`` run the complete
``_run_late_joiner_sequence`` helper:

1. A reporter submits a ``SubmitReport`` offer to the owner's inbox
   (``create_receive_report_case_tree`` BT creates the case and the
   CaseActor).
2. The owner validates the report (``trigger/validate-report``), which
   triggers ``create_validate_report_tree`` and causes the CaseActor to
   emit ``Create(VulnerabilityCase)`` to the reporter via the outbox.
3. The owner triggers ``invite-actor-to-case`` for the late-joiner actor.
   Per PCR-08-007, the ``Invite`` is placed in the **CaseActor's** outbox
   and drained explicitly here, delivering it to the late-joiner's inbox.
4. The late-joiner triggers ``accept-case-invite``.  The outbox drain
   delivers the ``Accept`` to the owner's inbox; the owner processes it via
   ``AcceptInviteActorToCaseReceivedUseCase``, adds the late-joiner as a
   participant, and queues ``Announce(VulnerabilityCase)`` in the *CaseActor's*
   outbox.
5. The CaseActor's outbox is drained via the real ``outbox_handler`` so the
   Announce dispatch is exercised end-to-end (routing, recipient extraction,
   OX-08-001 validation) before delivery to the late-joiner's inbox.

AC-1 (``test_late_joiner_receives_case_replica``) asserts that a replica
exists in late-joiner's DataLayer after the full sequence.

AC-2 (``test_late_joiner_appears_as_participant``) asserts that the
late-joiner's actor ID appears in ``replica.actor_participant_index`` with a
non-empty participant ID, and that the corresponding participant list entry
is present in ``replica.case_participants``.
"""

import asyncio

import pytest

from test.demo.conftest import _TestASGIRouter, create_isolated_actor_app
from vultron.adapters.driving.fastapi.outbox_handler import outbox_handler
from vultron.wire.as2.factories import rm_submit_report_activity
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

# ---------------------------------------------------------------------------
# Constants — all IDs use HTTP-routable URIs
# ---------------------------------------------------------------------------

_OWNER_BASE = "http://owner-late-joiner.test"
_REPORTER_BASE = "http://reporter-late-joiner.test"
_LATE_JOINER_BASE = "http://late-joiner.test"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def three_app_setup(monkeypatch):
    """Owner app + reporter app + late-joiner app wired for end-to-end delivery.

    Uses three isolated FastAPI app instances each with their own in-memory
    ``SqliteDataLayer``.  A shared ``_TestASGIRouter`` routes outbound
    deliveries between the apps in-process so the full
    outbox → inbox → inbox-handler chain is exercised without real HTTP.

    Lifecycle:
      1. Patches ``VULTRON_SERVER__BASE_URL`` to ``{_OWNER_BASE}/api/v2`` so
         that ``CreateCaseActorNode`` generates a routable CaseActor ID (e.g.
         ``http://owner-late-joiner.test/api/v2/actors/case-actor-…``).
         Without this the default ``http://localhost:7999`` is used, which
         lacks the ``/api/v2/`` prefix and gets a 404 from the owner's ASGI
         app (its routes are at ``/api/v2/actors/…``).
      2. Enters all three TestClient contexts (triggers lifespan startup).
      3. Replaces each app's ``ASGIEmitter._http_fallback`` with the shared
         router so cross-app deliveries use ASGI transport.
      4. Configures the module-level ``_default_emitter`` to the shared
         router so trigger-endpoint ``outbox_handler`` calls route through
         ASGI instead of making real HTTP requests.
      5. Registers the patched ``base_url`` with the router pointing to the
         owner's app so that CaseActor deliveries are routed correctly.
      6. Yields the three ``IsolatedActorApp`` instances and their clients.
      7. On teardown restores the previous default emitter, closes DLs, and
         reloads config to remove the patched env var.

    Yields:
        Tuple of (owner_iso, reporter_iso, late_joiner_iso,
                  owner_tc, reporter_tc, late_joiner_tc).
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

    router = _TestASGIRouter()
    owner_iso = create_isolated_actor_app(base_url=_OWNER_BASE, router=router)
    reporter_iso = create_isolated_actor_app(
        base_url=_REPORTER_BASE, router=router
    )
    late_joiner_iso = create_isolated_actor_app(
        base_url=_LATE_JOINER_BASE, router=router
    )

    # Register the patched base_url with the router so CaseActor deliveries
    # (whose IDs now use http://owner-late-joiner.test/api/v2) route to
    # the owner's ASGI app.
    config_base_url = get_config().server.base_url.rstrip("/")
    router.register(config_base_url, owner_iso.app)

    # Save and replace the module-level default emitter so outbox_handler
    # calls from trigger endpoints use the router instead of
    # DemoHttpDeliveryAdapter (real HTTP with retry backoff).
    previous_emitter = get_default_emitter()
    configure_default_emitter(router)  # type: ignore[arg-type]

    with owner_iso.client as owner_tc:
        with reporter_iso.client as reporter_tc:
            with late_joiner_iso.client as late_joiner_tc:
                for iso in (owner_iso, reporter_iso, late_joiner_iso):
                    emitter = getattr(iso.app.state, "emitter", None)
                    if hasattr(emitter, "_http_fallback"):
                        emitter._http_fallback = router  # type: ignore[assignment]
                yield (
                    owner_iso,
                    reporter_iso,
                    late_joiner_iso,
                    owner_tc,
                    reporter_tc,
                    late_joiner_tc,
                )

    # Restore previous emitter to avoid polluting other tests.
    configure_default_emitter(previous_emitter)  # type: ignore[arg-type]
    owner_iso.dl.close()
    reporter_iso.dl.close()
    late_joiner_iso.dl.close()
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


def _bootstrap_case(
    owner_iso,
    reporter_iso,
    owner_tc,
    reporter_tc,
    owner_slug: str,
    reporter_slug: str,
) -> str:
    """Set up a case on owner's app by having reporter submit a report.

    Exercises the full bootstrap sequence for PCR-07-007 prerequisites:

    1. Reporter submits a ``SubmitReport`` offer to owner's inbox, which
       triggers ``create_receive_report_case_tree`` and creates the
       preliminary ``VulnerabilityCase`` with CaseActor.
    2. Owner validates the report (``trigger/validate-report``), which
       triggers ``create_validate_report_tree`` and causes the CaseActor to
       emit ``Create(VulnerabilityCase)`` to the reporter (the existing
       case participant).

    Args:
        owner_iso: Owner's ``IsolatedActorApp``.
        reporter_iso: Reporter's ``IsolatedActorApp``.
        owner_tc: Owner's ``TestClient``.
        reporter_tc: Reporter's ``TestClient``.
        owner_slug: Short slug for the owner actor.
        reporter_slug: Short slug for the reporter actor.

    Returns:
        The ``id_`` of the ``VulnerabilityCase`` created on owner's app.
    """
    owner_base_api = owner_iso.base_url + "/api/v2"
    reporter_base_api = reporter_iso.base_url + "/api/v2"

    owner_actor_id = _create_actor(
        owner_tc, owner_base_api, owner_slug, "Owner"
    )
    reporter_actor_id = _create_actor(
        reporter_tc, reporter_base_api, reporter_slug, "Reporter"
    )

    # Register reporter on owner's app so the router can deliver there.
    _create_actor(owner_tc, reporter_base_api, reporter_slug, "Reporter")

    report = as_VulnerabilityReport(
        attributed_to=reporter_actor_id,
        name="PCR-07-007 late-joiner test report",
        content=(
            "A critical remote code execution vulnerability was discovered "
            "during integration testing for PCR-07-007."
        ),
    )
    offer = rm_submit_report_activity(
        report,
        actor=reporter_actor_id,
        target=owner_actor_id,
        to=owner_actor_id,
    )
    _post_to_inbox(owner_tc, _actor_slug(owner_actor_id), offer)

    all_cases = owner_iso.dl.get_all("VulnerabilityCase")
    assert len(all_cases) >= 1, (
        "Expected at least one VulnerabilityCase in owner's DataLayer "
        "after SubmitReport delivery.  The create_receive_report_case_tree "
        "BT may not have run."
    )
    case_id: str = all_cases[0]["id_"]

    resp = owner_tc.post(
        f"/api/v2/actors/{_actor_slug(owner_actor_id)}"
        "/trigger/validate-report",
        json={"offer_id": offer.id_},
    )
    assert (
        resp.status_code == 202
    ), f"validate-report trigger failed ({resp.status_code}): {resp.text}"

    return case_id


def _find_case_actor_id_in_dl(dl, case_id: str) -> str | None:
    """Scan ``dl`` for a CaseActor (Service) whose context matches *case_id*.

    ``VultronCaseActor`` objects are stored with ``type_="Service"`` and
    ``context=case_id``.  This helper mirrors the legacy-path fallback in
    the production ``_find_case_actor_id`` function.

    Args:
        dl: A ``DataLayer`` instance (typically the owner's).
        case_id: The ID of the ``VulnerabilityCase`` to match.

    Returns:
        The ``id_`` of the CaseActor, or ``None`` if not found.
    """
    for service in dl.list_objects("Service"):
        if getattr(service, "context", None) == case_id:
            return str(service.id_)
    return None


def _drain_case_actor_outbox(owner_iso, case_actor_id: str) -> None:
    """Drain the CaseActor's outbox via the real outbox_handler.

    After ``AcceptInviteActorToCaseReceivedUseCase`` processes an Accept, it
    calls ``_emit_announce_case()`` which queues ``Announce(VulnerabilityCase)``
    in the **CaseActor's** outbox (not the owner's or late-joiner's).  The
    background task triggered by ``trigger/accept-case-invite`` drains the
    accepting actor's outbox only, so the CaseActor's outbox must be drained
    explicitly in tests.

    Uses the real ``outbox_handler`` (the same code path as a trigger
    endpoint) so that recipient extraction, ``to:`` field validation
    (OX-08-001), and emitter routing are all exercised end-to-end.  The
    configured default emitter (the shared ``_TestASGIRouter``) routes the
    ``Announce`` to the late-joiner's app via ASGI.

    Args:
        owner_iso: Owner's ``IsolatedActorApp`` (contains the CaseActor's
            outbox queue and the activity objects).
        case_actor_id: Full ID of the CaseActor.
    """
    case_actor_dl = owner_iso.dl.clone_for_actor(case_actor_id)
    try:
        asyncio.run(outbox_handler(case_actor_id, case_actor_dl, owner_iso.dl))
    finally:
        case_actor_dl.close()


def _run_late_joiner_sequence(
    owner_iso,
    reporter_iso,
    late_joiner_iso,
    owner_tc,
    reporter_tc,
    late_joiner_tc,
    owner_slug: str,
    reporter_slug: str,
    lj_slug: str,
) -> tuple[str, str]:
    """Execute the full invite → accept → Announce sequence.

    Steps:
      1. Bootstrap the case (reporter submits report, owner validates).
      2. Create the late-joiner actor on both the late-joiner's and owner's
         apps (owner's app must know the invitee for invite dispatch).
      3. Owner triggers ``invite-actor-to-case``; the outbox drain delivers
         the ``Invite`` to late-joiner's inbox.
      4. Late-joiner retrieves the invite ID from their DataLayer.
      5. Late-joiner triggers ``accept-case-invite``; the outbox drain
         delivers the ``Accept`` to owner's inbox.  Owner processes it and
         queues ``Announce(VulnerabilityCase)`` in the CaseActor's outbox.
      6. CaseActor's outbox is drained via ``outbox_handler``; ``Announce`` is
         delivered to late-joiner's inbox via the configured emitter.

    Args:
        owner_iso: Owner's ``IsolatedActorApp``.
        reporter_iso: Reporter's ``IsolatedActorApp``.
        late_joiner_iso: Late-joiner's ``IsolatedActorApp``.
        owner_tc: Owner's ``TestClient``.
        reporter_tc: Reporter's ``TestClient``.
        late_joiner_tc: Late-joiner's ``TestClient``.
        owner_slug: Short slug for the owner actor.
        reporter_slug: Short slug for the reporter actor.
        lj_slug: Short slug for the late-joiner actor.

    Returns:
        Tuple of (case_id, lj_actor_id).
    """
    # Step 1: bootstrap the case
    case_id = _bootstrap_case(
        owner_iso,
        reporter_iso,
        owner_tc,
        reporter_tc,
        owner_slug=owner_slug,
        reporter_slug=reporter_slug,
    )

    # Step 2: create late-joiner actor on late-joiner's app
    lj_base_api = late_joiner_iso.base_url + "/api/v2"
    lj_actor_id = _create_actor(
        late_joiner_tc, lj_base_api, lj_slug, "LateJoiner"
    )

    # Register late-joiner on owner's app so SvcInviteActorToCaseUseCase
    # can resolve the invitee from owner's DataLayer.
    _create_actor(owner_tc, lj_base_api, lj_slug, "LateJoiner")

    # Step 3: owner triggers invite-actor-to-case
    resp = owner_tc.post(
        f"/api/v2/actors/{owner_slug}/trigger/invite-actor-to-case",
        json={"case_id": case_id, "invitee_id": lj_actor_id},
    )
    assert resp.status_code == 202, (
        f"invite-actor-to-case trigger failed ({resp.status_code}): "
        f"{resp.text}"
    )

    # PCR-08-007: SvcInviteActorToCaseUseCase now places the Invite in the
    # CaseActor's outbox (not the owner's), so drain it explicitly here.
    # The background task triggered by the invite endpoint only drains the
    # owner's outbox; the CaseActor's outbox must be processed separately.
    case_actor_id = _find_case_actor_id_in_dl(owner_iso.dl, case_id)
    assert case_actor_id is not None, (
        f"Could not find CaseActor for case '{case_id}' in owner's "
        f"DataLayer.  CreateCaseActorNode may not have run during "
        f"create_receive_report_case_tree."
    )
    _drain_case_actor_outbox(owner_iso, case_actor_id)

    # Step 4: retrieve invite_id from late-joiner's DataLayer
    invites = late_joiner_iso.dl.list_objects("Invite")
    assert len(invites) >= 1, (
        "Expected at least one Invite in late-joiner's DataLayer after "
        "owner triggered invite-actor-to-case.  The Invite may not have "
        "been delivered to late-joiner's inbox."
    )
    invite_id = invites[0].id_

    # Step 5: late-joiner triggers accept-case-invite
    resp = late_joiner_tc.post(
        f"/api/v2/actors/{lj_slug}/trigger/accept-case-invite",
        json={"invite_id": invite_id},
    )
    assert resp.status_code == 202, (
        f"accept-case-invite trigger failed ({resp.status_code}): "
        f"{resp.text}"
    )

    # Step 6: drain CaseActor's outbox via real outbox_handler
    # Announce(VulnerabilityCase) is routed to late-joiner via the
    # configured default emitter (_TestASGIRouter).
    _drain_case_actor_outbox(owner_iso, case_actor_id)

    return case_id, lj_actor_id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.spec("PCR-07-007")
class TestLateJoinerSequence:
    """PCR-07-007: Late-joiner receives case replica after invite/accept.

    Two tests cover the acceptance criteria from the GitHub issue:

    - AC-1: Late-joiner's DataLayer contains a case replica after the full
      invite → accept → Announce sequence.
    - AC-2: The late-joiner's actor ID appears in the replica's
      ``actor_participant_index``.
    """

    def test_late_joiner_receives_case_replica(self, three_app_setup):
        """AC-1: Announce(VulnerabilityCase) creates a local replica.

        Exercises the full invite/accept/Announce sequence: owner invites
        the late-joiner → late-joiner accepts → owner processes the Accept
        and the CaseActor emits ``Announce(VulnerabilityCase)`` → the Announce
        is delivered to the late-joiner's inbox.

        The late-joiner's ``DataLayer`` must contain a local case replica
        after the full delivery chain completes (PCR-07-007 AC-1).  The actor
        inbox queue being drained confirms the inbox handler ran and dispatch
        completed, not just that the activity arrived.
        """
        (
            owner_iso,
            reporter_iso,
            late_joiner_iso,
            owner_tc,
            reporter_tc,
            late_joiner_tc,
        ) = three_app_setup

        assert late_joiner_iso.dl.get_all("VulnerabilityCase") == [], (
            "Prerequisite: late-joiner's DataLayer must have no cases before "
            "the late-joiner sequence begins."
        )

        case_id, lj_actor_id = _run_late_joiner_sequence(
            owner_iso,
            reporter_iso,
            late_joiner_iso,
            owner_tc,
            reporter_tc,
            late_joiner_tc,
            owner_slug="owner-pcr-007-ac1",
            reporter_slug="reporter-pcr-007-ac1",
            lj_slug="late-joiner-pcr-007-ac1",
        )

        # The late-joiner actor's inbox queue must be empty: the inbox handler
        # ran and processed the Announce (dispatch chain completed).
        lj_actor_dl = late_joiner_iso.dl.clone_for_actor(lj_actor_id)
        try:
            assert lj_actor_dl.inbox_list() == [], (
                "Late-joiner actor's inbox queue was not drained after "
                "processing Announce(VulnerabilityCase).  The inbox handler "
                "may not have run (PCR-07-007 AC-1)."
            )
        finally:
            lj_actor_dl.close()

        replica = late_joiner_iso.dl.read(case_id)
        assert replica is not None, (
            f"Expected VulnerabilityCase '{case_id}' in late-joiner's "
            f"DataLayer after Announce(VulnerabilityCase) delivery, but "
            f"DataLayer has no record of it.  The late-joiner bootstrap "
            f"sequence may be broken (PCR-07-007 AC-1)."
        )

    def test_late_joiner_appears_as_participant(self, three_app_setup):
        """AC-2: Late-joiner appears as participant in their case replica.

        After the full invite/accept/Announce sequence, the case replica in
        late-joiner's DataLayer must include the late-joiner's actor ID in
        ``actor_participant_index``.  This confirms that
        ``AcceptInviteActorToCaseReceivedUseCase`` added the late-joiner as
        a participant before emitting the Announce, and that the full case
        (with updated participant index) was delivered and stored
        (PCR-07-007 AC-2).
        """
        (
            owner_iso,
            reporter_iso,
            late_joiner_iso,
            owner_tc,
            reporter_tc,
            late_joiner_tc,
        ) = three_app_setup

        case_id, lj_actor_id = _run_late_joiner_sequence(
            owner_iso,
            reporter_iso,
            late_joiner_iso,
            owner_tc,
            reporter_tc,
            late_joiner_tc,
            owner_slug="owner-pcr-007-ac2",
            reporter_slug="reporter-pcr-007-ac2",
            lj_slug="late-joiner-pcr-007-ac2",
        )

        replica = late_joiner_iso.dl.read(case_id)
        assert replica is not None, (
            f"No VulnerabilityCase replica found for '{case_id}' in "
            "late-joiner's DataLayer after the late-joiner sequence."
        )

        participant_index = getattr(replica, "actor_participant_index", {})
        assert lj_actor_id in participant_index, (
            f"Late-joiner actor '{lj_actor_id}' not found in case replica "
            f"actor_participant_index.  Expected the Announce to carry the "
            f"updated case (with late-joiner as participant) so that "
            f"AnnounceVulnerabilityCaseReceivedUseCase seeds the replica "
            f"with full participant data (PCR-07-007 AC-2).  "
            f"Participant index: {participant_index!r}"
        )

        participant_id = participant_index[lj_actor_id]
        assert participant_id, (
            f"actor_participant_index['{lj_actor_id}'] is empty — the "
            f"participant ID was not recorded (PCR-07-007 AC-2)."
        )

        participant_ids_in_list = [
            getattr(p, "id_", p) if not isinstance(p, str) else p
            for p in getattr(replica, "case_participants", [])
        ]
        assert participant_id in participant_ids_in_list, (
            f"Participant '{participant_id}' for late-joiner "
            f"'{lj_actor_id}' appears in actor_participant_index but is "
            f"missing from case_participants list — the replica is "
            f"inconsistent (PCR-07-007 AC-2).  "
            f"case_participants IDs: {participant_ids_in_list!r}"
        )
