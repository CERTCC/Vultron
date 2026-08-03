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

"""Unit tests for seed_containers_fcvcv (DEMOMA-19-002)."""

import pytest
from fastapi.testclient import TestClient

from test.demo._helpers import make_client, make_testclient_call
from vultron.demo.helpers.seeding import seed_containers_fcvcv


@pytest.fixture(scope="module")
def base(client: TestClient) -> str:
    return str(client.base_url).rstrip("/") + "/api/v2"


@pytest.fixture(scope="module", autouse=True)
def patch_datalayer_call(client: TestClient, base: str):
    from _pytest.monkeypatch import MonkeyPatch
    from vultron.demo.utils import DataLayerClient

    mp = MonkeyPatch()
    try:
        mp.setattr(DataLayerClient, "call", make_testclient_call(client, base))
        yield
    finally:
        mp.undo()


class TestSeedContainersFcvcv:
    """seed_containers_fcvcv creates five actors and 20 cross-registrations."""

    def test_returns_five_actors(self, base: str):
        result = seed_containers_fcvcv(
            finder_client=make_client(base),
            c1_client=make_client(base),
            v1_client=make_client(base),
            c2_client=make_client(base),
            v2_client=make_client(base),
        )
        assert len(result) == 5

    def test_actor_names_and_types(self, base: str):
        finder, c1, v1, c2, v2 = seed_containers_fcvcv(
            finder_client=make_client(base),
            c1_client=make_client(base),
            v1_client=make_client(base),
            c2_client=make_client(base),
            v2_client=make_client(base),
        )
        assert finder.name == "Finder"
        assert c1.name == "Coordinator1"
        assert v1.name == "Vendor1"
        assert c2.name == "Coordinator2"
        assert v2.name == "VendorDeployer"

    def test_all_actors_have_ids(self, base: str):
        finder, c1, v1, c2, v2 = seed_containers_fcvcv(
            finder_client=make_client(base),
            c1_client=make_client(base),
            v1_client=make_client(base),
            c2_client=make_client(base),
            v2_client=make_client(base),
        )
        for actor in (finder, c1, v1, c2, v2):
            assert actor.id_ is not None

    def test_all_containers_know_all_peers(self, base: str):
        finder_client = make_client(base)
        c1_client = make_client(base)
        v1_client = make_client(base)
        c2_client = make_client(base)
        v2_client = make_client(base)
        seed_containers_fcvcv(
            finder_client=finder_client,
            c1_client=c1_client,
            v1_client=v1_client,
            c2_client=c2_client,
            v2_client=v2_client,
        )
        expected_names = {
            "Finder",
            "Coordinator1",
            "Vendor1",
            "Coordinator2",
            "VendorDeployer",
        }
        for label, client in [
            ("finder", finder_client),
            ("c1", c1_client),
            ("v1", v1_client),
            ("c2", c2_client),
            ("v2", v2_client),
        ]:
            actors = client.get_list("/actors/")
            names = {a.get("name") for a in actors if isinstance(a, dict)}
            assert (
                expected_names <= names
            ), f"{label} container missing peers: {expected_names - names}"

    def test_deterministic_ids_are_honored(self, base: str):
        finder_id = f"{base}/actors/finder-fcvcv-det"
        c1_id = f"{base}/actors/c1-fcvcv-det"
        v1_id = f"{base}/actors/v1-fcvcv-det"
        c2_id = f"{base}/actors/c2-fcvcv-det"
        v2_id = f"{base}/actors/v2-fcvcv-det"

        finder, c1, v1, c2, v2 = seed_containers_fcvcv(
            finder_client=make_client(base),
            c1_client=make_client(base),
            v1_client=make_client(base),
            c2_client=make_client(base),
            v2_client=make_client(base),
            reporter_actor_id=finder_id,
            c1_actor_id=c1_id,
            v1_actor_id=v1_id,
            c2_actor_id=c2_id,
            v2_actor_id=v2_id,
        )

        assert finder.id_ == finder_id
        assert c1.id_ == c1_id
        assert v1.id_ == v1_id
        assert c2.id_ == c2_id
        assert v2.id_ == v2_id

    def test_idempotent_second_call_succeeds(self, base: str):
        finder_id = f"{base}/actors/finder-idem"
        c1_id = f"{base}/actors/c1-idem"
        v1_id = f"{base}/actors/v1-idem"
        c2_id = f"{base}/actors/c2-idem"
        v2_id = f"{base}/actors/v2-idem"
        shared_kwargs = dict(
            finder_client=make_client(base),
            c1_client=make_client(base),
            v1_client=make_client(base),
            c2_client=make_client(base),
            v2_client=make_client(base),
            reporter_actor_id=finder_id,
            c1_actor_id=c1_id,
            v1_actor_id=v1_id,
            c2_actor_id=c2_id,
            v2_actor_id=v2_id,
        )
        first = seed_containers_fcvcv(**shared_kwargs)  # type: ignore[arg-type]
        second = seed_containers_fcvcv(**shared_kwargs)  # type: ignore[arg-type]
        for a, b in zip(first, second):
            assert a.id_ == b.id_
