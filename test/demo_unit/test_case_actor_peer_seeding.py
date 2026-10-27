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


"""The demos seed the CaseActor's address book with every actor (ADR-0159).

The CaseActor carries each participant it names as it holds it: a seeded peer
as its profile, an actor known only by URI as an id-and-type reference
(AKM-05-005).  The demo reset clears its address book, so every scenario
seeds it again through its ``seed_containers*`` call.
"""

import ast
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vultron.demo.helpers import seeding
from vultron.wire.as2.vocab.base.objects.actors import (
    as_Actor,
    as_Organization,
    as_Person,
)

_CA_BASE = "http://case-actor:7999/api/v2"
_SCENARIOS = Path(seeding.__file__).parent.parent / "scenario"


def _ca_client() -> MagicMock:
    client = MagicMock()
    client.base_url = _CA_BASE
    return client


@pytest.mark.spec("AKM-05-005")
def test_every_seeded_actor_is_registered_with_the_case_actor():
    actors = [
        as_Person(id_="http://reporter:7999/api/v2/actors/r", name="Reporter"),
        as_Organization(
            id_="http://vendor:7999/api/v2/actors/v", name="Vendor"
        ),
    ]
    with patch.object(seeding, "seed_peer") as seed_peer:
        seeding.seed_case_actor_peers(_ca_client(), actors)

    assert [call.kwargs for call in seed_peer.call_args_list] == [
        {
            "client": seed_peer.call_args_list[0].kwargs["client"],
            "local_actor_id": f"{_CA_BASE}/actors/case-actor",
            "peer_id": actor.id_,
            "name": actor.name,
            "actor_type": type_,
        }
        for actor, type_ in zip(
            actors, ["Person", "Organization"], strict=True
        )
    ]


def test_no_case_actor_client_registers_nothing():
    with patch.object(seeding, "seed_peer") as seed_peer:
        seeding.seed_case_actor_peers(None, [as_Actor(id_="http://x/a")])
    seed_peer.assert_not_called()


def test_a_nameless_actor_is_refused():
    with (
        patch.object(seeding, "seed_peer"),
        pytest.raises(ValueError, match="no name"),
    ):
        seeding.seed_case_actor_peers(
            _ca_client(), [as_Actor(id_="http://x/a")]
        )


def _seed_calls(path: Path) -> list[ast.Call]:
    tree = ast.parse(path.read_text())
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id.startswith("seed_containers")
    ]


def test_the_ratchet_sees_scenario_seed_calls():
    """A zero-target ratchet passes vacuously, so the scan must find calls."""
    assert sum(len(_seed_calls(p)) for p in _SCENARIOS.glob("*.py")) > 0


@pytest.mark.spec("AKM-05-005")
@pytest.mark.parametrize(
    "path", sorted(_SCENARIOS.glob("*.py")), ids=lambda p: p.stem
)
def test_every_scenario_seeds_the_case_actor_address_book(path: Path):
    """Each ``seed_containers*`` call hands over the case-actor client."""
    for call in _seed_calls(path):
        keywords = {kw.arg for kw in call.keywords}
        assert "case_actor_client" in keywords, (
            f"{path.name}:{call.lineno} seeds its containers without the"
            " CaseActor's address book (seed_case_actor_peers)"
        )
