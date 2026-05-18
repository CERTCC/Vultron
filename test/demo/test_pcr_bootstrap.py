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
"""

import pytest

from test.demo.conftest import _TestASGIRouter, create_isolated_actor_app
from vultron.core.models.pending_case_inbox import VultronPendingCaseInbox
from vultron.wire.as2.factories import (
    add_note_to_case_activity,
    announce_vulnerability_case_activity,
)
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase

# ---------------------------------------------------------------------------
# Constants — all IDs use HTTP-routable URIs
# ---------------------------------------------------------------------------

_BOOTSTRAP_CASE_ID = "http://owner-bootstrap.test/api/v2/cases/pcr-07-006"
_CASE_ACTOR_ID = (
    "http://owner-bootstrap.test/api/v2/actors/case-actor-bootstrap"
)
_OWNER_ACTOR_ID = "http://owner-bootstrap.test/api/v2/actors/owner-bootstrap"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def participant_setup():
    """One isolated app acting as the Participant receiving the Announce.

    Uses ``create_isolated_actor_app`` to give the participant its own
    in-memory ``SqliteDataLayer``.  The ``_TestASGIRouter`` is wired as the
    ASGI emitter fallback so that any outbound deliveries from the participant
    stay in-process instead of making real HTTP calls.

    Yields:
        Tuple of (IsolatedActorApp, TestClient).
    """
    router = _TestASGIRouter()
    participant_isolated = create_isolated_actor_app(
        base_url="http://participant-bootstrap.test",
        router=router,
    )
    with participant_isolated.client as participant_tc:
        emitter = getattr(participant_isolated.app.state, "emitter", None)
        if hasattr(emitter, "_http_fallback"):
            emitter._http_fallback = router  # type: ignore[assignment]
        yield participant_isolated, participant_tc
    participant_isolated.dl.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_participant_actor(client, base: str, slug: str) -> str:
    """Create an Organization actor on *client* and return its full ID."""
    actor_id = f"{base}/actors/{slug}"
    resp = client.post(
        "/api/v2/actors/",
        json={
            "type": "Organization",
            "name": "Participant",
            "id": actor_id,
        },
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

    def test_announce_creates_case_replica(self, participant_setup):
        """AC-1: Announce(VulnerabilityCase) creates a local replica.

        After a CaseActor delivers ``Announce(VulnerabilityCase)`` to a
        participant's inbox, the participant's DataLayer must contain a local
        case replica with the correct case ID (PCR-07-006).
        """
        participant_iso, participant_tc = participant_setup
        base = participant_iso.base_url + "/api/v2"

        actor_id = _create_participant_actor(
            participant_tc, base, "pcr-006-ac1"
        )

        # Confirm the case does not yet exist in the participant's DataLayer.
        assert participant_iso.dl.read(_BOOTSTRAP_CASE_ID) is None

        case = VulnerabilityCase(
            id_=_BOOTSTRAP_CASE_ID, name="PCR-07-006 Test Case"
        )
        announce = announce_vulnerability_case_activity(
            case,
            actor=_CASE_ACTOR_ID,
            context=_BOOTSTRAP_CASE_ID,
            to=[actor_id],
        )
        _post_to_inbox(participant_tc, _actor_slug(actor_id), announce)

        replica = participant_iso.dl.read(_BOOTSTRAP_CASE_ID)
        assert replica is not None, (
            f"Expected VulnerabilityCase '{_BOOTSTRAP_CASE_ID}' in "
            f"participant's DataLayer after Announce(VulnerabilityCase), "
            f"but DataLayer has no record of it. "
            f"Bootstrap sequence may be broken (PCR-07-006)."
        )

    def test_case_fields_preserved_in_replica(self, participant_setup):
        """AC-1 (fields): The seeded replica retains fields from the Announce.

        Verifies that the ``name`` from the Announce payload is preserved in
        the local case replica.
        """
        participant_iso, participant_tc = participant_setup
        base = participant_iso.base_url + "/api/v2"

        actor_id = _create_participant_actor(
            participant_tc, base, "pcr-006-fields"
        )
        case = VulnerabilityCase(
            id_=_BOOTSTRAP_CASE_ID, name="PCR-07-006 Test Case"
        )
        announce = announce_vulnerability_case_activity(
            case,
            actor=_CASE_ACTOR_ID,
            context=_BOOTSTRAP_CASE_ID,
            to=[actor_id],
        )
        _post_to_inbox(participant_tc, _actor_slug(actor_id), announce)

        replica = participant_iso.dl.read(_BOOTSTRAP_CASE_ID)
        assert replica is not None
        assert getattr(replica, "name", None) == "PCR-07-006 Test Case", (
            f"Case replica name mismatch: expected 'PCR-07-006 Test Case', "
            f"got {getattr(replica, 'name', '<missing>')!r}"
        )

    def test_subsequent_case_scoped_activity_routes_without_deferral(
        self, participant_setup
    ):
        """AC-2: Case-scoped activity routes directly after replica exists.

        After the case replica is seeded via Announce, a subsequent
        ``Add(Note, context=case_id)`` delivered to the same inbox must be
        dispatched immediately — it must NOT be placed into
        ``VultronPendingCaseInbox`` (the pre-bootstrap deferral queue).
        """
        participant_iso, participant_tc = participant_setup
        base = participant_iso.base_url + "/api/v2"

        actor_id = _create_participant_actor(
            participant_tc, base, "pcr-006-ac2"
        )

        # Seed the replica via Announce.
        case = VulnerabilityCase(
            id_=_BOOTSTRAP_CASE_ID, name="PCR-07-006 Test Case"
        )
        announce = announce_vulnerability_case_activity(
            case,
            actor=_CASE_ACTOR_ID,
            context=_BOOTSTRAP_CASE_ID,
            to=[actor_id],
        )
        _post_to_inbox(participant_tc, _actor_slug(actor_id), announce)
        assert (
            participant_iso.dl.read(_BOOTSTRAP_CASE_ID) is not None
        ), "Prerequisite: case replica must exist before routing test."

        # Post a case-scoped Add(Note) with context = case_id.
        note = as_Note(name="Routing check note for PCR-07-006")
        note_activity = add_note_to_case_activity(
            note,
            target=case,
            actor=_OWNER_ACTOR_ID,
            context=_BOOTSTRAP_CASE_ID,
        )
        _post_to_inbox(participant_tc, _actor_slug(actor_id), note_activity)

        # The note activity must NOT have been deferred to the pending queue.
        pending_id = VultronPendingCaseInbox.build_id(_BOOTSTRAP_CASE_ID)
        pending = participant_iso.dl.read(pending_id)
        deferred = isinstance(pending, VultronPendingCaseInbox) and (
            note_activity.id_ in pending.activity_ids
        )
        assert not deferred, (
            f"Case-scoped activity '{note_activity.id_}' was placed in "
            f"VultronPendingCaseInbox even though case replica "
            f"'{_BOOTSTRAP_CASE_ID}' already exists. "
            f"Activity was incorrectly deferred (PCR-07-006 AC-2)."
        )
