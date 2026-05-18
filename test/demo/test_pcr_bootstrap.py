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

"""Integration tests for PCR-07-006: full case-replica bootstrap sequence.

Verifies: CaseActor sends Announce(VulnerabilityCase) → participant creates
local replica → subsequent case-scoped activities route without deferral.

These tests exercise the full inbox dispatch path against a real in-memory
SQLite DataLayer — use cases are not mocked.  They are auto-marked as
``@pytest.mark.integration`` by the conftest hook in ``test/demo/``.

Coverage approach
-----------------
AC-1 tests (``TestBootstrapSequence.test_announce_creates_case_replica`` and
``test_case_fields_preserved_in_replica``) use a **two-app setup** where a
separate owner app creates a case by processing a submitted report and then
validates it.  Validation triggers the CaseActor to emit
``Announce(VulnerabilityCase)`` via the outbox, which is routed to the
participant app via ``_TestASGIRouter``.  This exercises the full
create-case → emit-Announce path, catching regressions where case creation
no longer sends the announcement (PCR-07-006).

AC-2 tests (``test_subsequent_case_scoped_activity_routes_without_deferral``)
seed the replica with a direct ``Announce`` (faster, sufficient for routing
coverage) and then verify both the absence of deferral *and* the presence of
the handler's side effect (note appended to ``replica.notes``).
"""

import pytest

from test.demo.conftest import _TestASGIRouter, create_isolated_actor_app
from vultron.adapters.driven.db_record import object_to_record
from vultron.core.models.pending_case_inbox import VultronPendingCaseInbox
from vultron.wire.as2.factories import (
    add_note_to_case_activity,
    announce_vulnerability_case_activity,
    rm_submit_report_activity,
)
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    VulnerabilityReport,
)

# ---------------------------------------------------------------------------
# Constants — all IDs use HTTP-routable URIs
# ---------------------------------------------------------------------------

# Base URLs for the two-app (AC-1) tests.
_OWNER_BASE = "http://owner-bootstrap.test"
_PARTICIPANT_BASE = "http://participant-bootstrap.test"

# Fixed IDs for the single-app (AC-2) seeding path.
_DIRECT_CASE_ID = "http://owner-bootstrap.test/api/v2/cases/pcr-07-006-ac2"
_DIRECT_CASE_ACTOR_ID = (
    "http://owner-bootstrap.test/api/v2/actors/case-actor-bootstrap"
)
_DIRECT_OWNER_ACTOR_ID = (
    "http://owner-bootstrap.test/api/v2/actors/owner-bootstrap"
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def participant_setup():
    """One isolated participant app for the AC-2 routing test.

    The case replica is seeded directly via a hand-crafted
    ``Announce(VulnerabilityCase)`` (fast, sufficient for routing coverage).
    The ``_TestASGIRouter`` is wired as the ASGI emitter fallback so that any
    outbound deliveries from the participant stay in-process.

    Yields:
        Tuple of (IsolatedActorApp, TestClient).
    """
    router = _TestASGIRouter()
    participant_isolated = create_isolated_actor_app(
        base_url=_PARTICIPANT_BASE,
        router=router,
    )
    with participant_isolated.client as participant_tc:
        emitter = getattr(participant_isolated.app.state, "emitter", None)
        if hasattr(emitter, "_http_fallback"):
            emitter._http_fallback = router  # type: ignore[assignment]
        yield participant_isolated, participant_tc
    participant_isolated.dl.close()


@pytest.fixture
def two_app_setup():
    """Owner app + participant app wired for end-to-end bootstrap delivery.

    Uses two isolated FastAPI app instances each with their own in-memory
    ``SqliteDataLayer``.  A shared ``_TestASGIRouter`` routes outbound
    deliveries between the apps in-process so the full
    outbox → inbox → inbox-handler chain is exercised.

    Lifecycle:
      1. Enters both TestClient contexts (triggers lifespan startup).
      2. Replaces each app's ``ASGIEmitter._http_fallback`` with the shared
         router so cross-app deliveries use ASGI transport instead of real
         HTTP.
      3. Yields the two ``IsolatedActorApp`` instances and their test clients.
      4. On teardown closes both DataLayers.

    Yields:
        Tuple of (owner_iso, participant_iso, owner_tc, participant_tc).
    """
    router = _TestASGIRouter()
    owner_iso = create_isolated_actor_app(
        base_url=_OWNER_BASE,
        router=router,
    )
    participant_iso = create_isolated_actor_app(
        base_url=_PARTICIPANT_BASE,
        router=router,
    )
    with owner_iso.client as owner_tc:
        with participant_iso.client as participant_tc:
            for iso in (owner_iso, participant_iso):
                emitter = getattr(iso.app.state, "emitter", None)
                if hasattr(emitter, "_http_fallback"):
                    emitter._http_fallback = router  # type: ignore[assignment]
            yield owner_iso, participant_iso, owner_tc, participant_tc
    owner_iso.dl.close()
    participant_iso.dl.close()


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


def _bootstrap_case_for_participant(
    owner_iso,
    participant_iso,
    owner_tc,
    participant_tc,
    owner_slug: str,
    participant_slug: str,
) -> str:
    """Set up a case on owner's app and deliver Announce to participant.

    Exercises the full bootstrap sequence for PCR-07-006 AC-1:

    1. Report and SubmitReport offer are seeded directly into owner's
       DataLayer (bypasses the inbox BT so only one BT runs).
    2. Owner validates the report (``trigger/validate-report``), creating
       a ``VulnerabilityCase`` and adding participant as a case participant.
    3. Owner's CaseActor emits ``Announce(VulnerabilityCase)`` to
       participant via the outbox → ``_TestASGIRouter`` → inbox chain.
    4. Participant's inbox handler processes the ``Announce``.

    Args:
        owner_iso: Owner's ``IsolatedActorApp``.
        participant_iso: Participant's ``IsolatedActorApp``.
        owner_tc: Owner's ``TestClient``.
        participant_tc: Participant's ``TestClient``.
        owner_slug: Short slug for the owner actor (last URL path segment).
        participant_slug: Short slug for the participant actor.

    Returns:
        The ``id_`` of the ``VulnerabilityCase`` created on owner's app.
    """
    owner_base_api = owner_iso.base_url + "/api/v2"
    participant_base_api = participant_iso.base_url + "/api/v2"

    owner_actor_id = _create_actor(
        owner_tc, owner_base_api, owner_slug, "Owner"
    )
    participant_actor_id = _create_actor(
        participant_tc, participant_base_api, participant_slug, "Participant"
    )

    # Register participant on owner's app so the router can deliver there.
    _create_actor(
        owner_tc, participant_base_api, participant_slug, "Participant"
    )

    # Seed the SubmitReport offer directly into owner's DataLayer.
    # This skips the inbox→SubmitReportReceivedUseCase BT path (which would
    # run a second BT on top of validate-report's BT, doubling test time).
    # The validate-report trigger only needs the offer + report present in
    # the DL; how they got there is irrelevant for PCR-07-006 coverage.
    report = VulnerabilityReport(
        attributed_to=participant_actor_id,
        name="PCR-07-006 bootstrap test report",
        content=(
            "A critical remote code execution vulnerability was discovered "
            "during integration testing for PCR-07-006."
        ),
    )
    offer = rm_submit_report_activity(
        report,
        actor=participant_actor_id,
        target=owner_actor_id,
        to=owner_actor_id,
    )
    owner_iso.dl.create(object_to_record(report))
    owner_iso.dl.create(object_to_record(offer))

    # Owner validates the report: creates a case and adds participant.
    # The trigger endpoint schedules outbox_handler which delivers the
    # Announce(VulnerabilityCase) to participant's inbox.
    resp = owner_tc.post(
        f"/api/v2/actors/{_actor_slug(owner_actor_id)}/trigger/validate-report",
        json={"offer_id": offer.id_},
    )
    assert (
        resp.status_code == 202
    ), f"validate-report trigger failed ({resp.status_code}): {resp.text}"

    # Retrieve the auto-generated case ID from owner's DataLayer.
    all_cases = owner_iso.dl.get_all("VulnerabilityCase")
    assert len(all_cases) >= 1, (
        "Expected at least one VulnerabilityCase in owner's DataLayer "
        "after validate-report, but none was found."
    )
    return all_cases[0]["id_"]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.spec("PCR-07-006")
class TestBootstrapSequence:
    """PCR-07-006: CaseActor Announce creates replica; routing follows.

    Three tests cover the acceptance criteria from the GitHub issue:

    - AC-1a: Announce creates a case replica with the correct ID.
    - AC-1b: The seeded replica preserves case fields from the Announce payload.
    - AC-2:  Subsequent case-scoped activity routes without deferral.
    """

    def test_announce_creates_case_replica(self, two_app_setup):
        """AC-1: Announce(VulnerabilityCase) creates a local replica.

        Exercises the full bootstrap sequence: participant submits a report →
        owner validates it → CaseActor emits ``Announce(VulnerabilityCase)``
        via the outbox → participant's inbox receives and processes the
        Announce.

        The participant's ``DataLayer`` must contain a local case replica
        after the full delivery chain completes (PCR-07-006 AC-1).  The actor
        inbox queue being drained confirms the inbox handler ran and dispatch
        completed, not just that the activity arrived.
        """
        owner_iso, participant_iso, owner_tc, participant_tc = two_app_setup

        assert participant_iso.dl.get_all("VulnerabilityCase") == [], (
            "Prerequisite: participant's DataLayer must have no cases before "
            "the bootstrap sequence begins."
        )

        case_id = _bootstrap_case_for_participant(
            owner_iso,
            participant_iso,
            owner_tc,
            participant_tc,
            owner_slug="owner-pcr-006-ac1",
            participant_slug="participant-pcr-006-ac1",
        )

        # The participant actor's inbox queue must be empty: the inbox handler
        # ran and processed the Announce (dispatch chain completed).
        participant_actor_id = (
            f"{_PARTICIPANT_BASE}/api/v2/actors/participant-pcr-006-ac1"
        )
        actor_dl = participant_iso.dl.clone_for_actor(participant_actor_id)
        assert actor_dl.inbox_list() == [], (
            "Participant actor's inbox queue was not drained after "
            "processing Announce(VulnerabilityCase).  The inbox handler "
            "may not have run (PCR-07-006 AC-1)."
        )

        replica = participant_iso.dl.read(case_id)
        assert replica is not None, (
            f"Expected VulnerabilityCase '{case_id}' in participant's "
            f"DataLayer after Announce(VulnerabilityCase) delivery, but "
            f"DataLayer has no record of it.  Bootstrap sequence may be "
            f"broken (PCR-07-006 AC-1)."
        )

    def test_case_fields_preserved_in_replica(self, two_app_setup):
        """AC-1 (fields): The seeded replica retains fields from the Announce.

        After the full bootstrap sequence, the case replica in participant's
        DataLayer must preserve the ``name`` of the case as set by the owner.
        """
        owner_iso, participant_iso, owner_tc, participant_tc = two_app_setup

        case_id = _bootstrap_case_for_participant(
            owner_iso,
            participant_iso,
            owner_tc,
            participant_tc,
            owner_slug="owner-pcr-006-fields",
            participant_slug="participant-pcr-006-fields",
        )

        replica = participant_iso.dl.read(case_id)
        assert replica is not None, (
            f"No VulnerabilityCase replica found for '{case_id}' in "
            "participant's DataLayer after bootstrap sequence."
        )

        owner_case = owner_iso.dl.read(case_id)
        expected_name = getattr(owner_case, "name", None)
        assert (
            expected_name is not None
        ), "Owner's case has no name — cannot verify field preservation."
        assert getattr(replica, "name", None) == expected_name, (
            f"Case replica name mismatch: expected {expected_name!r}, "
            f"got {getattr(replica, 'name', '<missing>')!r} "
            f"(PCR-07-006 AC-1 field preservation)."
        )

    def test_subsequent_case_scoped_activity_routes_without_deferral(
        self, participant_setup
    ):
        """AC-2: Case-scoped activity routes directly after replica exists.

        After the case replica is seeded via a direct ``Announce``, a
        subsequent ``Add(Note, context=case_id)`` delivered to the same inbox
        must be dispatched immediately — it must NOT be placed into
        ``VultronPendingCaseInbox`` (the pre-bootstrap deferral queue).

        Seeding the replica directly (rather than via the full owner →
        participant chain) is intentional: this test specifically covers the
        routing decision after a replica exists.  End-to-end emission coverage
        is provided by the AC-1 tests above.

        Two handler side-effects are asserted in addition to the non-deferral
        check:

        - The note's ID appears in the replica's ``notes`` list, confirming
          the ``AddNoteToCaseReceivedUseCase`` ran to completion.
        - The actor's inbox queue is drained, confirming the inbox handler
          dispatched the ``Add(Note)`` activity rather than silently dropping
          or re-queuing it.
        """
        participant_iso, participant_tc = participant_setup
        base = participant_iso.base_url + "/api/v2"

        actor_id = _create_actor(
            participant_tc, base, "pcr-006-ac2", "Participant"
        )

        # Seed the replica via a direct Announce.
        case = VulnerabilityCase(
            id_=_DIRECT_CASE_ID, name="PCR-07-006 Test Case"
        )
        announce = announce_vulnerability_case_activity(
            case,
            actor=_DIRECT_CASE_ACTOR_ID,
            context=_DIRECT_CASE_ID,
            to=[actor_id],
        )
        _post_to_inbox(participant_tc, _actor_slug(actor_id), announce)
        assert (
            participant_iso.dl.read(_DIRECT_CASE_ID) is not None
        ), "Prerequisite: case replica must exist before routing test."

        # Post a case-scoped Add(Note) with context = case_id.
        note = as_Note(name="Routing check note for PCR-07-006")
        note_activity = add_note_to_case_activity(
            note,
            target=case,
            actor=_DIRECT_OWNER_ACTOR_ID,
            context=_DIRECT_CASE_ID,
        )
        _post_to_inbox(participant_tc, _actor_slug(actor_id), note_activity)

        # Assert 1: The note activity must NOT have been deferred.
        pending_id = VultronPendingCaseInbox.build_id(_DIRECT_CASE_ID)
        pending = participant_iso.dl.read(pending_id)
        deferred = isinstance(pending, VultronPendingCaseInbox) and (
            note_activity.id_ in pending.activity_ids
        )
        assert not deferred, (
            f"Case-scoped activity '{note_activity.id_}' was placed in "
            f"VultronPendingCaseInbox even though case replica "
            f"'{_DIRECT_CASE_ID}' already exists. "
            f"Activity was incorrectly deferred (PCR-07-006 AC-2)."
        )

        # Assert 2: The note ID must appear in the replica's notes list,
        # confirming AddNoteToCaseReceivedUseCase ran to completion.
        replica = participant_iso.dl.read(_DIRECT_CASE_ID)
        assert replica is not None
        replica_note_ids = [
            getattr(n, "id_", n) if not isinstance(n, str) else n
            for n in getattr(replica, "notes", [])
        ]
        assert note.id_ in replica_note_ids, (
            f"Note '{note.id_}' not found in case replica notes "
            f"after Add(Note) was dispatched. "
            f"AddNoteToCaseReceivedUseCase may not have run "
            f"(PCR-07-006 AC-2). Replica notes: {replica_note_ids!r}"
        )

        # Assert 3: The actor's inbox queue must be drained, confirming
        # inbox_handler ran and dispatched the Add(Note) activity.
        actor_dl = participant_iso.dl.clone_for_actor(actor_id)
        assert actor_dl.inbox_list() == [], (
            f"Actor '{actor_id}' inbox queue was not drained after "
            f"Add(Note) was processed. The inbox handler may not have "
            f"run or may have re-queued the activity (PCR-07-006 AC-2)."
        )
