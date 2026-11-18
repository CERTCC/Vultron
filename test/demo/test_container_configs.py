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

"""In-process containers hold their own configs, so #1876 fails here.

In #1876 the CaseActor seated the report receiver that proposed a case with
the CaseActor's *own* ``default_case_roles``.  Every in-process test passed,
because every node read one process-wide config, and four Docker scenarios
failed.  ADR-0133 fixed the read: the proposer states its roles on the
proposal (``proposerCaseRoles``, CP-01-013).  ADR-0206 makes the suite able
to find the next read of that shape: each in-process node holds the config
its container has (DEMOMA-01-007).

This module runs the reporter, vendor and case-actor containers in process
(:func:`test.demo.conftest.container_nodes`) and checks two things:

* the nodes hold their containers' configs, and the case-actor's case roles
  differ from the vendor's;
* the vendor is seated with its own roles, and the same run fails when the
  CaseActor is made to read its own config instead, as it did in #1876.
"""

from collections.abc import Iterator
from typing import Any

import pytest

from test.demo.conftest import StartContainers, submit_report_through_reporter
from vultron.config import AppConfig
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.use_cases.received.case_proposal import create as proposal
from vultron.demo.helpers.cast import (
    CASE_ACTOR,
    REPORTER_SLOT,
    VENDOR_SLOT,
    ContainerSlot,
)
from vultron.demo.recordings.runner import ScenarioNodes
from vultron.enums.roles import CVDRole

_SLOTS = (REPORTER_SLOT, VENDOR_SLOT, CASE_ACTOR)


def _base(slot: ContainerSlot) -> str:
    return slot.compose_url.removesuffix("/api/v2")


def _id(slot: ContainerSlot) -> str:
    return slot.actor_id(slot.compose_url)


@pytest.fixture
def containers(container_nodes: StartContainers) -> Iterator[ScenarioNodes]:
    """The rv cast, each actor created and in the others' address books."""
    nodes = container_nodes(*_SLOTS)
    actor_types = {
        REPORTER_SLOT: "Person",
        VENDOR_SLOT: "Organization",
        CASE_ACTOR: "Service",
    }
    for slot, actor_type in actor_types.items():
        client = nodes.clients[_base(slot)]
        resp = client.post(
            "/api/v2/actors/",
            json={"type": actor_type, "name": slot.name, "id": _id(slot)},
        )
        assert resp.status_code in (200, 201), resp.text
    # Each container's seed config lists the others as peers
    # (docker/seed-configs/), so each address book does here.
    for slot in _SLOTS:
        for peer, peer_type in actor_types.items():
            if peer is slot:
                continue
            resp = nodes.clients[_base(slot)].post(
                f"/api/v2/actors/{slot.name}/peers/",
                json={
                    "id": _id(peer),
                    "name": peer.name,
                    "actor_type": peer_type,
                },
            )
            assert resp.status_code in (200, 201), resp.text
    yield nodes


def _vendor_seat_on_the_case_actor(nodes: ScenarioNodes) -> CaseParticipant:
    """Report to the vendor and return the vendor's seat in the new case."""
    submit_report_through_reporter(
        nodes.clients[_base(REPORTER_SLOT)],
        _id(REPORTER_SLOT),
        _id(VENDOR_SLOT),
        report_name="Per-container config report",
        report_content="Checks whose case roles the CaseActor seats.",
    )
    store = nodes.apps[_base(CASE_ACTOR)].store_for(_id(CASE_ACTOR))
    seats = [
        p
        for p in store.list_objects("CaseParticipant")
        if isinstance(p, CaseParticipant)
        and str(p.attributed_to) == _id(VENDOR_SLOT)
    ]
    assert len(seats) == 1, (
        f"the CaseActor holds {len(seats)} seats for the vendor, not one; "
        "the proposal round trip did not create the case"
    )
    return seats[0]


def _assert_seated_with_its_own_roles(seat: CaseParticipant) -> None:
    """The proposer holds the roles it stated, plus CASE_OWNER (CP-01-013)."""
    assert CVDRole.VENDOR in seat.case_roles, (
        "the CaseActor seated the vendor without the VENDOR role its own "
        f"container declares; roles {seat.case_roles!r} (#1876, ADR-0133)"
    )
    assert CVDRole.CASE_OWNER in seat.case_roles


@pytest.mark.spec("DEMOMA-01-007")
def test_each_container_node_holds_its_containers_config(
    containers: ScenarioNodes,
) -> None:
    configs: dict[ContainerSlot, AppConfig] = {}
    for slot in _SLOTS:
        config = containers.apps[_base(slot)].config
        assert config is not None, f"the {slot.name} node holds no config"
        configs[slot] = config
    assert configs[VENDOR_SLOT].actor.default_case_roles == [CVDRole.VENDOR]
    assert configs[CASE_ACTOR].actor.default_case_roles == []
    assert configs[REPORTER_SLOT].actor.default_case_roles == []
    for slot, config in configs.items():
        assert config.server.base_url.rstrip("/") == slot.compose_url
        assert (
            str(config.actor.case_actor_service_url).rstrip("/")
            == CASE_ACTOR.compose_url
        )


@pytest.mark.spec("CP-01-013")
@pytest.mark.spec("DEMOMA-01-007")
def test_the_case_actor_seats_the_proposer_with_its_stated_roles(
    containers: ScenarioNodes,
) -> None:
    _assert_seated_with_its_own_roles(
        _vendor_seat_on_the_case_actor(containers)
    )


@pytest.mark.spec("DEMOMA-01-007")
def test_a_case_actor_reading_its_own_roles_fails_in_process(
    containers: ScenarioNodes, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Re-create the #1876 read and show the check above fails on it.

    The CaseActor is made to seat the proposer from its own
    ``default_case_roles`` instead of ``proposerCaseRoles``.  With one
    process-wide config holding the vendor's roles this passed; with each
    node holding its container's config it must not.
    """
    real_tree = proposal.create_case_proposal_received_tree

    def tree_seating_from_own_config(*args: Any, **kwargs: Any) -> Any:
        from vultron.config import load_actor_config

        # Read inside the CaseActor's app, so this is the CaseActor's config.
        kwargs["proposer_case_roles"] = load_actor_config().default_case_roles
        return real_tree(*args, **kwargs)

    monkeypatch.setattr(
        proposal,
        "create_case_proposal_received_tree",
        tree_seating_from_own_config,
    )

    seat = _vendor_seat_on_the_case_actor(containers)
    with pytest.raises(AssertionError, match="#1876"):
        _assert_seated_with_its_own_roles(seat)
