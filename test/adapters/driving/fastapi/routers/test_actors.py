#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  (“Third Party Software”). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

# python
import pytest
from fastapi import status
from fastapi.encoders import jsonable_encoder

from vultron.adapters.utils import strip_id_prefix
from vultron.core.states.cs import CS_pxa, CS_vfd
from vultron.core.states.em import EM
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Create
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.case_status import (
    as_CaseStatus,
    as_ParticipantStatus,
)
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)
from vultron.adapters.driven.actor_hosts import canonical_actor_uri

_ACTOR_ID = "https://example.org/actors/alice"

# Ids used in action-rules and sub-route tests. The actor is hosted here, so
# its id is the URL that reaches it; the case and participant are plain objects
# and keep opaque urns.
_LOCAL_ACTOR_ID = canonical_actor_uri("participant-1")
_URN_CASE_ID = "urn:uuid:aaaaaaaa-0000-0000-0000-000000000003"
_URN_PARTICIPANT_ID = "urn:uuid:aaaaaaaa-0000-0000-0000-000000000004"


def _route_key(object_id: str) -> str:
    return strip_id_prefix(object_id)


@pytest.fixture
def urn_actor_dl():
    """The urn actor's own store — the one the route will open for it."""
    from vultron.adapters.driven.datalayer_sqlite import get_datalayer

    return get_datalayer(_LOCAL_ACTOR_ID, db_url="sqlite:///:memory:")


def test_created_actors_fixture_has_expected_count(created_actors):
    assert len(created_actors) == 6  # matches _actor_classes in conftest


def test_get_actors_list_returns_all_actors(client_actors, created_actors):
    resp = client_actors.get("/actors/")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == len(created_actors)


def test_get_actor_by_id_returns_actor_object(client_actors, created_actors):
    for actor in created_actors:
        resp = client_actors.get(f"/actors/{_route_key(actor.id_)}")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert isinstance(data, dict)
        assert "id" in data
        assert data["id"].endswith(actor.id_)


def test_get_actor_not_found_returns_404(client_actors):
    resp = client_actors.get("/actors/nonexistent-actor-id")
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_get_actor_inbox_returns_mailbox_structure(
    client_actors, created_actors
):
    for actor in created_actors:
        resp = client_actors.get(f"/actors/{_route_key(actor.id_)}/inbox")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert isinstance(data, dict)
        assert "items" in data
        assert isinstance(data["items"], list)


def test_post_activity_to_actor_inbox_accepted(client_actors, created_actors):
    for actor in created_actors:
        note = as_Note(content="This is a test note.")
        activity = as_Create(object_=note, actor=actor.id_)
        payload = jsonable_encoder(activity, exclude_none=True)
        resp = client_actors.post(
            f"/actors/{_route_key(actor.id_)}/inbox/", json=payload
        )
        assert resp.status_code == status.HTTP_202_ACCEPTED


def test_post_non_activity_to_actor_inbox_returns_422(
    client_actors, created_actors
):
    for actor in created_actors:
        note = as_Note(
            id_="urn:uuid:test-note", content="This is a test note."
        )
        payload = jsonable_encoder(note, exclude_none=True)
        resp = client_actors.post(
            f"/actors/{_route_key(actor.id_)}/inbox/", json=payload
        )
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_get_actor_profile_returns_discovery_fields(
    client_actors, created_actors
):
    for actor in created_actors:
        resp = client_actors.get(f"/actors/{_route_key(actor.id_)}/profile")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert "id" in data
        assert data["id"].endswith(actor.id_)
        assert "type" in data
        assert "inbox" in data
        assert "outbox" in data
        assert isinstance(data["inbox"], str), "inbox must be a URL string"
        assert isinstance(data["outbox"], str), "outbox must be a URL string"


def test_get_actor_profile_not_found_returns_404(client_actors):
    resp = client_actors.get("/actors/nonexistent-actor-id/profile")
    assert resp.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# IE-11: Activity Addressing — route-level HTTP responses
# ---------------------------------------------------------------------------


def test_post_inbox_returns_400_when_activity_addressed_to_other_actor(
    client_actors, created_actors
):
    """AC-1/IE-11-001: Activity whose addressing excludes receiving actor → 400."""
    actor = created_actors[0]
    other_id = created_actors[1].id_

    note = as_Note(content="not for you")
    activity = as_Create(object_=note, actor=other_id)
    activity.to = other_id  # explicitly addressed to a different actor

    payload = jsonable_encoder(activity, exclude_none=True)
    resp = client_actors.post(
        f"/actors/{_route_key(actor.id_)}/inbox/", json=payload
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST


def test_post_inbox_returns_202_when_activity_addressed_to_actor(
    client_actors, created_actors
):
    """AC-2/IE-11-001: Activity explicitly addressed to receiving actor → 202."""
    actor = created_actors[0]

    note = as_Note(content="this is for you")
    activity = as_Create(object_=note, actor=actor.id_)
    activity.to = actor.id_

    payload = jsonable_encoder(activity, exclude_none=True)
    resp = client_actors.post(
        f"/actors/{_route_key(actor.id_)}/inbox/", json=payload
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED


def test_post_inbox_returns_202_when_activity_has_no_addressing(
    client_actors, created_actors
):
    """AC-3/IE-11-002: Activity with absent addressing → Liberal Accept → 202."""
    actor = created_actors[0]

    note = as_Note(content="no addressing")
    activity = as_Create(object_=note, actor=actor.id_)
    # no to/cc/bto/bcc set

    payload = jsonable_encoder(activity, exclude_none=True)
    resp = client_actors.post(
        f"/actors/{_route_key(actor.id_)}/inbox/", json=payload
    )
    assert resp.status_code == status.HTTP_202_ACCEPTED


def test_get_actors_does_not_log_raw_records_at_info_level(
    client_actors, created_actors, caplog
):
    import logging

    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        resp = client_actors.get("/actors/")

    assert resp.status_code == status.HTTP_200_OK

    info_messages = [
        r.message for r in caplog.records if r.levelno == logging.INFO
    ]
    raw_dumps = [
        m for m in info_messages if m.startswith(("results:", "rec:"))
    ]
    assert (
        not raw_dumps
    ), f"Raw DB record dumps should not be logged at INFO level; found: {raw_dumps}"


def _seed_action_rules_data(dl):
    """Insert a minimal valid as_VulnerabilityCase / as_CaseParticipant pair."""
    participant = as_CaseParticipant(
        id_=_URN_PARTICIPANT_ID,
        attributed_to=_LOCAL_ACTOR_ID,
        context=_URN_CASE_ID,
        case_roles=[CVDRole.VENDOR],
        participant_statuses=[
            as_ParticipantStatus(
                context=_URN_CASE_ID,
                rm_state=RM.ACCEPTED,
                vfd_state=CS_vfd.VFd,
            )
        ],
    )
    dl.create(participant)

    case = as_VulnerabilityCase(
        id_=_URN_CASE_ID,
        name="Test Case",
        case_statuses=[
            as_CaseStatus(em_state=EM.ACTIVE, pxa_state=CS_pxa.Pxa)
        ],
    )
    case.add_participant(participant)
    dl.create(case)


def test_get_action_rules_returns_200_with_expected_fields(
    client_actors, urn_actor_dl
):
    """Actor/case endpoint returns all required state and action fields."""
    _seed_action_rules_data(urn_actor_dl)

    resp = client_actors.get(
        f"/actors/{_route_key(_LOCAL_ACTOR_ID)}/cases/"
        f"{_route_key(_URN_CASE_ID)}/action-rules"
    )
    assert resp.status_code == status.HTTP_200_OK

    body = resp.json()
    expected_keys = {
        "participant_id",
        "participant_actor_id",
        "case_id",
        "role",
        "rm_state",
        "em_state",
        "vfd_state",
        "pxa_state",
        "cs_state",
        "actions",
    }
    assert expected_keys.issubset(body.keys())
    assert body["case_id"] == _URN_CASE_ID
    assert body["participant_id"] == _URN_PARTICIPANT_ID
    assert body["participant_actor_id"] == _LOCAL_ACTOR_ID


def test_get_action_rules_case_not_found_returns_404(client_actors):
    """Missing case returns 404."""
    resp = client_actors.get(
        f"/actors/{_route_key(_LOCAL_ACTOR_ID)}/cases/"
        "urn:uuid:00000000-0000-0000-0000-000000000000/action-rules"
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_get_action_rules_actor_not_in_case_returns_404(
    client_actors, datalayer, urn_actor_dl
):
    """Actor outside the selected case returns 404."""
    _seed_action_rules_data(urn_actor_dl)

    resp = client_actors.get(
        "/actors/99999999-0000-0000-0000-000000000000/cases/"
        f"{_route_key(_URN_CASE_ID)}/action-rules"
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# POST /actors/ — actor creation (D5-1-G2)
# ---------------------------------------------------------------------------


class TestCreateActor:
    """Tests for ``POST /actors/`` idempotent actor creation endpoint."""

    def test_create_organization_returns_201(self, client_actors):
        payload = {"name": "TestOrg", "actor_type": "Organization"}
        resp = client_actors.post("/actors/", json=payload)
        assert resp.status_code == status.HTTP_201_CREATED
        data = resp.json()
        assert data["name"] == "TestOrg"
        assert data["type"] == "Organization"
        assert "id" in data

    def test_create_person_returns_201(self, client_actors):
        payload = {"name": "Alice", "actor_type": "Person"}
        resp = client_actors.post("/actors/", json=payload)
        assert resp.status_code == status.HTTP_201_CREATED
        data = resp.json()
        assert data["name"] == "Alice"
        assert data["type"] == "Person"

    def test_create_service_returns_201(self, client_actors):
        payload = {"name": "MyService", "actor_type": "Service"}
        resp = client_actors.post("/actors/", json=payload)
        assert resp.status_code == status.HTTP_201_CREATED
        data = resp.json()
        assert data["type"] == "Service"

    def test_create_application_returns_201(self, client_actors):
        payload = {"name": "MyApp", "actor_type": "Application"}
        resp = client_actors.post("/actors/", json=payload)
        assert resp.status_code == status.HTTP_201_CREATED
        data = resp.json()
        assert data["type"] == "Application"

    def test_create_group_returns_201(self, client_actors):
        payload = {"name": "MyGroup", "actor_type": "Group"}
        resp = client_actors.post("/actors/", json=payload)
        assert resp.status_code == status.HTTP_201_CREATED
        data = resp.json()
        assert data["type"] == "Group"

    def test_create_actor_default_type_is_organization(self, client_actors):
        payload = {"name": "DefaultTypeActor"}
        resp = client_actors.post("/actors/", json=payload)
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.json()["type"] == "Organization"

    def test_create_actor_with_custom_id(self, client_actors):
        custom_id = "http://finder:7999/api/v2/actors/finder-uuid"
        payload = {
            "name": "Finder",
            "actor_type": "Person",
            "id": custom_id,
        }
        resp = client_actors.post("/actors/", json=payload)
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.json()["id"] == custom_id

    def test_create_actor_idempotent_returns_200_on_second_call(
        self, client_actors
    ):
        custom_id = "http://vendor:7999/api/v2/actors/vendor-uuid"
        payload = {
            "name": "Vendor",
            "actor_type": "Organization",
            "id": custom_id,
        }
        first = client_actors.post("/actors/", json=payload)
        assert first.status_code == status.HTTP_201_CREATED

        second = client_actors.post("/actors/", json=payload)
        assert second.status_code == status.HTTP_200_OK
        assert second.json()["id"] == custom_id

    def test_idempotent_creation_returns_same_actor(self, client_actors):
        custom_id = "http://example.org/actors/alice"
        payload = {"name": "Alice", "actor_type": "Person", "id": custom_id}
        first = client_actors.post("/actors/", json=payload)
        second = client_actors.post("/actors/", json=payload)
        assert first.json()["id"] == second.json()["id"]
        assert first.json()["name"] == second.json()["name"]

    def test_created_actor_appears_in_list(self, client_actors):
        payload = {
            "name": "ListCheckActor",
            "actor_type": "Organization",
            "id": "http://example.org/actors/listcheck",
        }
        client_actors.post("/actors/", json=payload)
        resp = client_actors.get("/actors/")
        ids = [a["id"] for a in resp.json()]
        assert "http://example.org/actors/listcheck" in ids

    def test_a_bare_slug_is_expanded_to_the_url_that_serves_it(
        self, client_actors
    ):
        """A hosted actor's id is the URL that reaches it on this node.

        An actor is a process with API endpoints, so its id *is* its address:
        ``{base_url}/actors/{slug}``, with its inbox at ``{id}/inbox``. A client
        that supplies only a slug is therefore telling this node what to call the
        actor, and the node supplies the authority.

        This covers the bare-slug shape only. What happens to a client-supplied
        *absolute* id — including one under a foreign authority — is the separate
        question pinned by
        :meth:`test_a_foreign_absolute_id_is_adopted_verbatim`.
        """
        from vultron.adapters.driven.actor_hosts import canonical_actor_uri

        payload = {
            "name": "FetchableActor",
            "actor_type": "Organization",
            "id": "fetchable",
        }
        created = client_actors.post("/actors/", json=payload)
        assert created.status_code in (
            status.HTTP_200_OK,
            status.HTTP_201_CREATED,
        )
        expected_id = canonical_actor_uri("fetchable")
        assert created.json()["id"] == expected_id

        resp = client_actors.get("/actors/fetchable")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["id"] == expected_id

    def test_a_foreign_absolute_id_is_adopted_verbatim(self, client_actors):
        """Pins the shape that actually breaks — issue #2549.

        ``canonical_actor_uri`` returns any id carrying a scheme unchanged, so
        ``POST /actors/`` with an id under *another* authority creates a record
        here under that authority and opens a local store for it. That is
        deliberate for the peer-registration use it was built for — a peer's id is
        the URL outbound delivery posts to, so rewriting it into this node's
        namespace would turn a reachable peer into a local phantom (ADR-0072
        decision 5).

        It is not free, though: the store is keyed by the final path segment
        alone, so a peer whose URI ends in the same segment as a co-hosted actor
        shares that actor's store. Asserted here so the day the endpoint learns to
        distinguish "register a peer" from "create an actor I host", this test
        fails and says which behaviour changed rather than the change landing
        silently.
        """
        foreign_id = "http://elsewhere.test:7999/api/v2/actors/foreigner"
        created = client_actors.post(
            "/actors/",
            json={
                "name": "Foreigner",
                "actor_type": "Organization",
                "id": foreign_id,
            },
        )
        assert created.status_code == status.HTTP_201_CREATED
        assert created.json()["id"] == foreign_id, (
            "the authority is adopted as-is; if this now returns a local URI,"
            " #2549 was addressed and this test documents the old behaviour"
        )

        # And it is a *hosted* record: it comes back from this node's collection.
        listed = client_actors.get("/actors/")
        assert foreign_id in [a["id"] for a in listed.json()]

    @pytest.mark.parametrize("bad", ["/", "//"])
    def test_an_id_that_names_no_actor_is_rejected(self, client_actors, bad):
        """422, not 500, and no store minted for a phantom actor.

        ``"/"`` is not empty but names nothing. Before the guard in
        ``canonical_actor_uri`` it produced ``{base}/actors/``, whose final path
        segment is ``actors`` — a usable slug — so the node opened a store for an
        actor named after a path component and nothing downstream could tell.
        """
        resp = client_actors.post(
            "/actors/",
            json={"name": "Nameless", "actor_type": "Person", "id": bad},
        )
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


# ---------------------------------------------------------------------------
# Regression tests for #654: actor routes accept surrogate keys
# ---------------------------------------------------------------------------

_HTTP_URL_ACTOR_ID = "http://vendor:7999/api/v2/actors/alice"


def test_get_actor_by_final_path_segment_returns_actor(client_actors):
    """A hosted actor is addressed by the last segment of its own URL.

    Retitled from "surrogate key". There is no surrogate: the segment is simply
    the tail of the actor's id, and ``base_url + "actors/" + segment`` reassembles
    the id exactly (ADR-0072). The previous version stored an actor under a
    *foreign* authority and expected this node to return it, which conflated
    "an actor I know the address of" with "an actor I host".
    """
    from vultron.adapters.driven.actor_hosts import canonical_actor_uri
    from vultron.adapters.driven.datalayer_sqlite import get_datalayer
    from vultron.adapters.driven.db_record import object_to_record
    from vultron.wire.as2.vocab.base.objects.actors import as_Organization

    actor_id = canonical_actor_uri("vendor-with-path")
    actor = as_Organization(id_=actor_id, name="VendorActor")
    get_datalayer(actor_id, db_url="sqlite:///:memory:").create(
        object_to_record(actor)
    )

    resp = client_actors.get("/actors/vendor-with-path")
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["id"] == actor_id


def test_specific_actor_routes_not_shadowed_by_catch_all(
    client_actors, created_actors
):
    """Sub-routes like /{actor_id}/profile still resolve correctly."""
    for actor in created_actors:
        resp = client_actors.get(f"/actors/{_route_key(actor.id_)}/profile")
        assert resp.status_code == status.HTTP_200_OK
