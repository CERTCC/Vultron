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

"""``GET`` and ``PUT /actors/{actor_id}/embargo-policy`` (EP-02, #3972).

A published policy is the actor default shortest-wins reads at case creation
(EP-04-003), so the tests assert what ``owner_embargo_policies`` sees in the
actor's own store, not only what the response body says.
"""

from datetime import timedelta

import pytest
from fastapi import status

from vultron.adapters.driven.actor_hosts import canonical_actor_uri
from vultron.adapters.driven.datalayer_sqlite import get_datalayer
from vultron.core.models.embargo_policy import EmbargoPolicy
from vultron.core.services.embargo_duration import (
    owner_embargo_policies,
    select_actor_default,
)

_SLUG = "policy-vendor"
_PATH = f"/actors/{_SLUG}/embargo-policy"


@pytest.fixture
def hosted_actor(client_actors) -> str:
    """Create the actor the policy routes are exercised against; return its id."""
    resp = client_actors.post(
        "/actors/",
        json={
            "name": "Policy Vendor",
            "actor_type": "Organization",
            "id": _SLUG,
        },
    )
    assert resp.status_code in (status.HTTP_200_OK, status.HTTP_201_CREATED)
    return str(resp.json()["id"])


def _store_for(actor_id: str):
    """The store the route wrote to — the same in-memory one the override opens."""
    return get_datalayer(actor_id, db_url="sqlite:///:memory:")


class TestPutEmbargoPolicy:
    @pytest.mark.spec("EP-01-004")
    @pytest.mark.spec("HTTP-03-002")
    def test_first_publish_creates_the_policy_in_the_actors_own_store(
        self, client_actors, hosted_actor
    ):
        resp = client_actors.put(_PATH, json={"preferred_duration": "P30D"})

        assert resp.status_code == status.HTTP_201_CREATED
        body = resp.json()
        assert body["type"] == "EmbargoPolicy"
        assert body["actorId"] == hosted_actor
        assert body["inbox"] == f"{hosted_actor}/inbox"
        assert body["preferredDuration"] == "P30D"

        stored = owner_embargo_policies(_store_for(hosted_actor), hosted_actor)
        assert [p.preferred_duration for p in stored] == [timedelta(days=30)]

    @pytest.mark.spec("EP-04-003")
    @pytest.mark.spec("EP-04-010")
    def test_the_published_policy_is_the_actor_default_shortest_wins_reads(
        self, client_actors, hosted_actor
    ):
        client_actors.put(_PATH, json={"preferred_duration": "P21D"})

        store = _store_for(hosted_actor)
        assert select_actor_default(
            owner_embargo_policies(store, hosted_actor)
        ) == timedelta(days=21)

    @pytest.mark.spec("HTTP-03-001")
    def test_replace_returns_200_and_leaves_exactly_one_policy(
        self, client_actors, hosted_actor
    ):
        first = client_actors.put(_PATH, json={"preferred_duration": "P30D"})
        second = client_actors.put(
            _PATH, json={"preferred_duration": "P45D", "notes": "revised"}
        )

        assert first.status_code == status.HTTP_201_CREATED
        assert second.status_code == status.HTTP_200_OK
        assert second.json()["preferredDuration"] == "P45D"
        assert second.json()["notes"] == "revised"
        stored = owner_embargo_policies(_store_for(hosted_actor), hosted_actor)
        assert [p.preferred_duration for p in stored] == [timedelta(days=45)]
        assert second.json()["id"] != first.json()["id"]

    @pytest.mark.spec("EP-01-003")
    def test_optional_bounds_are_carried(self, client_actors, hosted_actor):
        resp = client_actors.put(
            _PATH,
            json={
                "preferred_duration": "P30D",
                "minimum_duration": "P7D",
                "maximum_duration": "P90D",
            },
        )

        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.json()["minimumDuration"] == "P7D"
        assert resp.json()["maximumDuration"] == "P90D"

    @pytest.mark.spec("EP-02-002")
    def test_the_actor_profile_lists_the_policy_url_after_publish(
        self, client_actors, hosted_actor
    ):
        before = client_actors.get(f"/actors/{_SLUG}/profile").json()
        assert "embargoPolicy" not in before

        client_actors.put(_PATH, json={"preferred_duration": "P30D"})

        profile = client_actors.get(f"/actors/{_SLUG}/profile").json()
        assert profile["embargoPolicy"] == f"{hosted_actor}/embargo-policy"
        actor = client_actors.get(f"/actors/{_SLUG}").json()
        assert actor["embargoPolicy"] == f"{hosted_actor}/embargo-policy"

    @pytest.mark.spec("HTTP-03-005")
    def test_an_actor_this_node_does_not_host_is_404(self, client_actors):
        resp = client_actors.put(
            "/actors/nobody-here/embargo-policy",
            json={"preferred_duration": "P30D"},
        )

        assert resp.status_code == status.HTTP_404_NOT_FOUND
        # Nothing was minted for the phantom actor.
        nobody = canonical_actor_uri("nobody-here")
        assert owner_embargo_policies(_store_for(nobody), nobody) == []

    @pytest.mark.spec("HTTP-03-009")
    @pytest.mark.parametrize(
        "bad",
        [
            {"preferred_duration": "P2W"},  # weeks (DUR-02-002)
            {"preferred_duration": "P1M"},  # calendar month
            {"preferred_duration": "thirty days"},
            {"preferred_duration": 42},  # not a duration string
            {"preferred_duration": "P30D", "minimum_duration": "P1Y"},
            {},  # preferred_duration is required (EP-01-002)
            {"preferred_duration": "P30D", "notes": ""},  # CS-08
        ],
        ids=["weeks", "month", "prose", "int", "min-year", "empty", "blank"],
    )
    def test_a_malformed_body_is_422_not_500(
        self, client_actors, hosted_actor, bad
    ):
        resp = client_actors.put(_PATH, json=bad)

        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert (
            owner_embargo_policies(_store_for(hosted_actor), hosted_actor)
            == []
        )

    @pytest.mark.spec("EP-01-005")
    def test_a_body_cannot_publish_in_another_actors_name(
        self, client_actors, hosted_actor
    ):
        """``actor_id`` and ``inbox`` come from the path actor, never the body."""
        resp = client_actors.put(
            _PATH,
            json={
                "preferred_duration": "P30D",
                "actor_id": "https://elsewhere.test/actors/imposter",
            },
        )

        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


class TestGetEmbargoPolicy:
    @pytest.mark.spec("EP-02-001")
    @pytest.mark.spec("HTTP-09-002")
    def test_returns_the_published_policy_as_as2_json(
        self, client_actors, hosted_actor
    ):
        client_actors.put(_PATH, json={"preferred_duration": "P30D"})

        resp = client_actors.get(_PATH)

        assert resp.status_code == status.HTTP_200_OK
        assert resp.headers["content-type"].startswith(
            "application/activity+json"
        )
        assert resp.json()["type"] == "EmbargoPolicy"
        assert resp.json()["actorId"] == hosted_actor
        assert resp.json()["preferredDuration"] == "P30D"

    @pytest.mark.spec("HTTP-03-005")
    def test_nothing_published_is_404_naming_the_actor(
        self, client_actors, hosted_actor
    ):
        resp = client_actors.get(_PATH)

        assert resp.status_code == status.HTTP_404_NOT_FOUND
        assert hosted_actor in resp.json()["detail"]
        assert "embargo policy" in resp.json()["detail"]

    def test_unknown_actor_is_404(self, client_actors):
        resp = client_actors.get("/actors/nobody-here/embargo-policy")

        assert resp.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.spec("EP-04-010")
    def test_shows_the_policy_shortest_wins_would_use(
        self, client_actors, hosted_actor
    ):
        """Several stored policies (a seeded store, say): the shortest is shown,
        the same choice ``select_actor_default`` makes."""
        store = _store_for(hosted_actor)
        for days in (60, 14, 30):
            store.create(
                EmbargoPolicy(
                    actor_id=hosted_actor,
                    inbox=f"{hosted_actor}/inbox",
                    preferred_duration=timedelta(days=days),
                )
            )

        resp = client_actors.get(_PATH)

        assert resp.json()["preferredDuration"] == "P14D"

    def test_another_actors_policy_in_the_store_is_not_this_actors(
        self, client_actors, hosted_actor
    ):
        """A record naming a different actor never answers for this one (#3753)."""
        _store_for(hosted_actor).create(
            EmbargoPolicy(
                actor_id="https://elsewhere.test/actors/other",
                inbox="https://elsewhere.test/actors/other/inbox",
                preferred_duration=timedelta(days=3),
            )
        )

        resp = client_actors.get(_PATH)

        assert resp.status_code == status.HTTP_404_NOT_FOUND
