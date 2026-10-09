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

"""Unit tests for seed_containers_rcvv (DEMOMA-21)."""

from unittest.mock import MagicMock, patch

from vultron.demo.helpers import seeding


def _seed() -> tuple[tuple, MagicMock, dict]:
    clients = {
        name: MagicMock(name=name)
        for name in ("reporter", "coordinator", "vendor", "vendor2")
    }

    def fake_seed_actor(client, name, actor_type, actor_id):
        actor = MagicMock()
        actor.id_ = f"http://{name.lower()}:7999/api/v2/actors/{name.lower()}"
        actor.name = name
        return actor

    with (
        patch.object(seeding, "seed_actor", side_effect=fake_seed_actor),
        patch.object(seeding, "_own_actor", side_effect=lambda c, a: a),
        patch.object(seeding, "seed_peer") as peer,
    ):
        result = seeding.seed_containers_rcvv(
            reporter_client=clients["reporter"],
            coordinator_client=clients["coordinator"],
            vendor_client=clients["vendor"],
            vendor2_client=clients["vendor2"],
        )
    return result, peer, clients


class TestSeedContainersRcvv:
    def test_returns_the_four_actors_in_role_order(self):
        (reporter, coordinator, vendor, vendor2), _, _ = _seed()
        assert [a.name for a in (reporter, coordinator, vendor, vendor2)] == [
            "Reporter",
            "Coordinator",
            "Vendor1",
            "Vendor2",
        ]

    def test_every_actor_is_a_peer_on_every_other_container(self):
        result, peer, clients = _seed()
        registrations = {
            (
                c.kwargs["client"],
                c.kwargs["local_actor_id"],
                c.kwargs["peer_id"],
            )
            for c in peer.call_args_list
        }
        assert len(peer.call_args_list) == 12
        for client, local in zip(clients.values(), result, strict=True):
            for other in result:
                expected = (client, local.id_, other.id_)
                assert (expected in registrations) == (other is not local)
