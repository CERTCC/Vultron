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

"""Each ``seed_containers*`` helper keeps its own INFO log wording.

The seven helpers share :func:`_seed_mesh`; :class:`_MeshLogStyle` keeps the
lines each one wrote before the seeding was shared, so the demo output does
not change.
"""

import logging
from collections.abc import Callable
from unittest.mock import MagicMock, patch

import pytest

from vultron.demo.helpers import seeding
from vultron.demo.helpers.seeding import actors as seeding_actors


def _fake_seed_actor(client, name, actor_type, actor_id):
    actor = MagicMock()
    actor.id_ = f"http://{name.lower()}/a"
    actor.name = name
    return actor


def _info_lines(
    caplog: pytest.LogCaptureFixture,
    seed: Callable[..., object],
    *client_names: str,
) -> list[str]:
    with (
        patch.object(
            seeding_actors, "seed_actor", side_effect=_fake_seed_actor
        ),
        patch.object(seeding_actors, "_own_actor", side_effect=lambda c, a: a),
        patch.object(seeding_actors, "seed_peer"),
        caplog.at_level(logging.INFO, logger=seeding_actors.__name__),
    ):
        seed(**{name: MagicMock(name=name) for name in client_names})
    return [
        r.getMessage()
        for r in caplog.records
        if r.name == seeding_actors.__name__ and r.levelno == logging.INFO
    ]


def test_seed_containers_logs_each_peer_registration(caplog):
    assert _info_lines(
        caplog, seeding.seed_containers, "reporter_client", "vendor_client"
    ) == [
        "Phase 1: creating local actors on each container...",
        "Reporter actor seeded on Reporter container: http://reporter/a",
        "Vendor actor seeded on Vendor container: http://vendor/a",
        "Phase 2: registering cross-container peers...",
        "Vendor peer registered on Reporter container: http://vendor/a",
        "Reporter peer registered on Vendor container: http://reporter/a",
    ]


def test_seed_containers_rcvv_logs_one_summary_line(caplog):
    assert _info_lines(
        caplog,
        seeding.seed_containers_rcvv,
        "reporter_client",
        "coordinator_client",
        "vendor_client",
        "vendor2_client",
    ) == [
        "Phase 1: creating local actors on each container...",
        "Reporter actor seeded: http://reporter/a",
        "Coordinator actor seeded: http://coordinator/a",
        "Vendor actor seeded: http://vendor/a",
        "Vendor2 actor seeded: http://vendor2/a",
        "Phase 2: registering cross-container peers...",
        "Every actor registered as a peer on the other containers",
    ]


def test_seed_containers_rcvcv_logs_one_line_per_container(caplog):
    assert _info_lines(
        caplog,
        seeding.seed_containers_rcvcv,
        "reporter_client",
        "c1_client",
        "v1_client",
        "c2_client",
        "v2_client",
    ) == [
        "Phase 1: creating local actors on each container...",
        "Reporter actor seeded: http://reporter/a",
        "C1 actor seeded: http://coordinator1/a",
        "V1 actor seeded: http://vendor/a",
        "C2 actor seeded: http://coordinator2/a",
        "V2 actor seeded: http://vendordeployer/a",
        "Phase 2: registering cross-container peers...",
        "C1, V1, C2, and V2 registered as peers on Reporter container",
        "Reporter, V1, C2, and V2 registered as peers on C1 container",
        "Reporter, C1, C2, and V2 registered as peers on V1 container",
        "Reporter, C1, V1, and V2 registered as peers on C2 container",
        "Reporter, C1, V1, and C2 registered as peers on V2 container",
    ]
