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


"""Tests of :mod:`vultron.demo.scenario.rcvcv_demo.cast` (DEMOMA-19, #5825).

The scenario seats C1 and V1 under the family's role names, so one copy of the
shared opening serves ``rcv`` and ``rcvcv`` alike, and keeps its own names on
the command line and in the devlogs the invariant harness reads.
"""

import pytest

import vultron.demo.scenario.rcvcv_demo as demo
from vultron.demo.helpers.coordinated_story import (
    COORDINATOR,
    REPORTER,
    VENDOR,
)


class TestRcvcvCast:
    """The cast names, the seats and the devlogs names."""

    def test_c1_and_v1_are_seated_under_the_family_role_names(self):
        """One copy of the opening serves ``rcv`` and ``rcvcv`` alike."""
        assert demo.C1 == COORDINATOR
        assert demo.V1 == VENDOR
        # The devlogs and the CLI keep the scenario's own names (DEMOMA-19-018).
        assert [role.name for role in demo.ROLES][:3] == [
            "reporter",
            "c1",
            "v1",
        ]

    @pytest.mark.spec("DEMOMA-19-018")
    def test_the_devlog_names_are_the_scenario_role_names(self):
        """``reporter``, ``c1``, ``v1``, ``c2``, ``v2`` — not cast names.

        C1 and V1 are seated under the family's role names, so the dump has
        to translate them back: the harness loads ``devlogs/rcvcv/c1``.
        """
        assert demo.DEVLOG_REPLICAS == (
            ("reporter", REPORTER),
            ("c1", demo.C1),
            ("v1", demo.V1),
            ("c2", demo.C2),
            ("v2", demo.V2),
        )
