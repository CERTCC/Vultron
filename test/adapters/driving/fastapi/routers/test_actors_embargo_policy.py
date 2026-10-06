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
(EP-04-003).  It is a field of the actor's own profile record (EP-01-001,
EP-01-004) — the profile carries it inline on every ``Create(CaseProposal)``
the actor sends (CP-01-010) — so the tests assert what that record holds in
the actor's own store, not only what the response body says.
"""

from datetime import timedelta

import pytest
from fastapi import status

from vultron.adapters.driven.actor_hosts import canonical_actor_uri
from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    get_datalayer,
)
from vultron.core.models.actor import CoreActor
from vultron.core.models.embargo_policy import EmbargoPolicy
from vultron.core.services.embargo_duration import actor_default_duration

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


def _stored_profile(actor_id: str) -> CoreActor:
    record = _store_for(actor_id).read(actor_id)
    assert isinstance(record, CoreActor)
    return record


def _profile_policy(actor_id: str) -> EmbargoPolicy | None:
    """The policy the actor's stored profile carries inline (EP-01-004)."""
    return _stored_profile(actor_id).embargo_policy


def _policy_records(actor_id: str) -> list:
    """Free-standing ``EmbargoPolicy`` records in the actor's store."""
    return list(_store_for(actor_id).list_objects("EmbargoPolicy"))


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

        stored = _profile_policy(hosted_actor)
        assert stored is not None
        assert stored.preferred_duration == timedelta(days=30)
        # Part of the profile, not a separate object beside it (EP-01-001).
        assert _policy_records(hosted_actor) == []

    @pytest.mark.spec("EP-04-003")
    @pytest.mark.spec("CP-01-010")
    def test_the_published_policy_is_the_actor_default_shortest_wins_reads(
        self, client_actors, hosted_actor
    ):
        client_actors.put(_PATH, json={"preferred_duration": "P21D"})

        assert actor_default_duration(
            _stored_profile(hosted_actor)
        ) == timedelta(days=21)

    @pytest.mark.spec("EP-02-005")
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
        stored = _profile_policy(hosted_actor)
        assert stored is not None
        assert stored.preferred_duration == timedelta(days=45)
        assert _policy_records(hosted_actor) == []
        # One well-known record, overwritten — not a new one beside the old.
        assert second.json()["id"] == first.json()["id"]

    @pytest.mark.spec("EP-02-001")
    @pytest.mark.spec("EP-02-005")
    def test_the_published_policy_is_the_record_at_the_endpoint_url(
        self, client_actors, hosted_actor
    ):
        """The policy's id is the endpoint URL, in the profile as well."""
        resp = client_actors.put(_PATH, json={"preferred_duration": "P30D"})

        assert resp.json()["id"] == f"{hosted_actor}/embargo-policy"
        assert resp.json()["id"] == EmbargoPolicy.build_id(hosted_actor)
        profile = client_actors.get(f"/actors/{_SLUG}/profile").json()
        assert profile["embargoPolicy"]["id"] == resp.json()["id"]

    @pytest.mark.spec("EP-02-005")
    def test_a_publish_leaves_a_seeded_policy_record_unread(
        self, client_actors, hosted_actor
    ):
        """A free-standing record is not the actor's policy: only the profile
        field is, so a publish neither reads nor counts it (#4027)."""
        _store_for(hosted_actor).create(
            EmbargoPolicy(
                actor_id=hosted_actor,
                inbox=f"{hosted_actor}/inbox",
                preferred_duration=timedelta(days=7),
            )
        )

        resp = client_actors.put(_PATH, json={"preferred_duration": "P30D"})

        assert resp.status_code == status.HTTP_201_CREATED  # first publish
        stored = _profile_policy(hosted_actor)
        assert stored is not None
        assert stored.preferred_duration == timedelta(days=30)
        assert client_actors.get(_PATH).json()["preferredDuration"] == "P30D"

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
    @pytest.mark.spec("EP-01-001")
    def test_the_actor_profile_carries_the_policy_inline_after_publish(
        self, client_actors, hosted_actor
    ):
        before = client_actors.get(f"/actors/{_SLUG}/profile").json()
        assert "embargoPolicy" not in before

        published = client_actors.put(
            _PATH, json={"preferred_duration": "P30D"}
        ).json()

        profile = client_actors.get(f"/actors/{_SLUG}/profile").json()
        assert profile["embargoPolicy"] == published
        actor = client_actors.get(f"/actors/{_SLUG}").json()
        assert actor["embargoPolicy"] == published
        # The endpoint returns the record the profile carries (EP-02-002).
        assert client_actors.get(_PATH).json() == profile["embargoPolicy"]

    @pytest.mark.spec("HTTP-03-005")
    def test_an_actor_this_node_does_not_host_is_404(self, client_actors):
        resp = client_actors.put(
            "/actors/nobody-here/embargo-policy",
            json={"preferred_duration": "P30D"},
        )

        assert resp.status_code == status.HTTP_404_NOT_FOUND
        # Nothing was minted for the phantom actor.
        nobody = canonical_actor_uri("nobody-here")
        assert _store_for(nobody).read(nobody) is None
        assert _policy_records(nobody) == []

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
        assert _profile_policy(hosted_actor) is None

    @pytest.mark.spec("EP-01-005")
    @pytest.mark.spec("EP-02-005")
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

    def test_policy_records_beside_the_profile_are_not_shown(
        self, client_actors, hosted_actor
    ):
        """Records in the store that the profile does not carry are not the
        actor's policy: the store-wide scan is retired (#4027)."""
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

        assert resp.status_code == status.HTTP_404_NOT_FOUND

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


def _interleave_rival_writes(monkeypatch, rival, *, times: int) -> list[int]:
    """Land ``rival(store, expected, n)`` before each of the next *times* PUT writes.

    The rival writes the actor's profile between the PUT's read and its
    compare-and-set — the window a plain read-then-save left unguarded
    (#4102).  Returns the attempts it interleaved, in order.
    """
    real = SqliteDataLayer.save_if_unchanged
    interleaved: list[int] = []

    def rival_then_write(self, obj, expected):
        if len(interleaved) < times:
            interleaved.append(len(interleaved) + 1)
            rival(self, expected, interleaved[-1])
        return real(self, obj, expected)

    monkeypatch.setattr(SqliteDataLayer, "save_if_unchanged", rival_then_write)
    return interleaved


def _rename(store, profile: CoreActor, n: int) -> None:
    """A rival profile write that touches a field other than the policy."""
    store.save(profile.model_copy(update={"name": f"Renamed {n}"}))


def _rival_publish(store, profile: CoreActor, _n: int) -> None:
    """A rival publish of different terms, as a concurrent PUT would write."""
    store.save(
        type(profile).model_validate(
            {
                **dict(profile),
                "embargo_policy": EmbargoPolicy(
                    id_=EmbargoPolicy.build_id(profile.id_),
                    actor_id=profile.id_,
                    inbox=profile.inbox,
                    preferred_duration=timedelta(days=10),
                ),
            }
        )
    )


class TestConcurrentProfileWrite:
    """A publish rewrites the whole profile, so it must not overwrite a rival write."""

    @pytest.mark.spec("EP-02-004")
    def test_a_profile_write_inside_the_window_is_kept_beside_the_policy(
        self, client_actors, hosted_actor, monkeypatch
    ):
        interleaved = _interleave_rival_writes(monkeypatch, _rename, times=1)

        resp = client_actors.put(_PATH, json={"preferred_duration": "P30D"})

        assert interleaved == [1]
        assert resp.status_code == status.HTTP_201_CREATED
        profile = _stored_profile(hosted_actor)
        assert profile.name == "Renamed 1"
        assert profile.embargo_policy is not None
        assert profile.embargo_policy.preferred_duration == timedelta(days=30)

    @pytest.mark.spec("EP-02-004")
    def test_a_rival_publish_inside_the_window_makes_this_one_a_replace(
        self, client_actors, hosted_actor, monkeypatch
    ):
        """Whether a publish replaced one is read from the fresh profile."""
        interleaved = _interleave_rival_writes(
            monkeypatch, _rival_publish, times=1
        )

        resp = client_actors.put(_PATH, json={"preferred_duration": "P30D"})

        assert interleaved == [1]
        assert resp.status_code == status.HTTP_200_OK
        policy = _profile_policy(hosted_actor)
        assert policy is not None
        assert policy.preferred_duration == timedelta(days=30)

    @pytest.mark.spec("EP-02-004")
    def test_a_profile_changed_under_every_attempt_is_409_and_writes_nothing(
        self, client_actors, hosted_actor, monkeypatch
    ):
        interleaved = _interleave_rival_writes(monkeypatch, _rename, times=100)

        resp = client_actors.put(_PATH, json={"preferred_duration": "P30D"})

        assert resp.status_code == status.HTTP_409_CONFLICT
        detail = resp.json()["detail"]
        assert detail["status"] == status.HTTP_409_CONFLICT
        assert detail["error"] == "Conflict"
        assert hosted_actor in detail["message"]
        assert interleaved == [1, 2, 3]
        profile = _stored_profile(hosted_actor)
        assert profile.name == "Renamed 3"
        assert profile.embargo_policy is None
