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

"""Demo helpers take the CaseActor identity from configuration only (CP-08-009).

``case_actor_id_for_report`` and ``seed_case_participants_for_demo`` once fell back
to this node's own ``server.base_url`` when no CaseActor service URL was
configured. In a multi-container topology that names a CaseActor no container
hosts, so each helper now raises an error naming
``VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL`` instead (#5378).
"""

from collections.abc import Iterator
from unittest.mock import MagicMock

import pytest
from pytest import MonkeyPatch

from vultron.config.app import reload_config
from vultron.demo.helpers.seeding import seed_case_participants_for_demo
from vultron.demo.utils import case_actor_id_for_report
from vultron.errors import DemoCaseActorUnconfiguredError

_SERVER_BASE = "http://this-node.test/api/v2"
_CASE_ACTOR_BASE = "http://case-actor.test/api/v2"
_ENV = "VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL"


@pytest.fixture
def node_env() -> Iterator[MonkeyPatch]:
    """Give the node a server base URL, and restore the config afterwards."""
    mp = MonkeyPatch()
    try:
        mp.setenv("VULTRON_SERVER__BASE_URL", _SERVER_BASE)
        yield mp
    finally:
        mp.undo()
        reload_config()


@pytest.fixture
def unconfigured(node_env: MonkeyPatch) -> None:
    """A node with a server base URL but no CaseActor service URL."""
    node_env.delenv(_ENV, raising=False)
    reload_config()


@pytest.mark.spec("CP-08-009")
class TestCaseActorUrlRequired:
    def test_case_actor_id_for_report_raises_when_unconfigured(
        self, unconfigured: None
    ) -> None:
        with pytest.raises(DemoCaseActorUnconfiguredError, match=_ENV):
            case_actor_id_for_report("https://example.org/reports/r1")

    def test_seeding_raises_before_any_write_when_unconfigured(
        self, unconfigured: None
    ) -> None:
        """The seeder fails before it writes the vendor or reporter record."""
        dl = MagicMock(name="dl")
        with pytest.raises(DemoCaseActorUnconfiguredError, match=_ENV):
            seed_case_participants_for_demo(
                "https://example.org/cases/c1",
                "https://example.org/actors/vendor",
                "https://example.org/actors/reporter",
                None,
                dl,
            )
        assert dl.mock_calls == []

    def test_identity_follows_the_configured_url_not_the_server_base(
        self, node_env: MonkeyPatch
    ) -> None:
        node_env.setenv(_ENV, _CASE_ACTOR_BASE)
        reload_config()
        case_actor_id = case_actor_id_for_report("")
        assert case_actor_id == f"{_CASE_ACTOR_BASE}/actors/case-actor"
        assert not case_actor_id.startswith(_SERVER_BASE)
