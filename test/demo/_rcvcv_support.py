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

"""The five-party stand-in story the RCVCV tests share."""

import contextlib

import vultron.demo.scenario.rcvcv_demo as demo
from test.demo._helpers import mock_case, no_demo_banners, story_state
from vultron.demo.helpers import coordinated_story, owner_decision_story
from vultron.demo.helpers.coordinated_story import REPORTER
from vultron.demo.scenario import rcvcv_fragments

#: The scenario's five cast names, in ``ROLES`` order.
CAST = (REPORTER, demo.C1, demo.V1, demo.C2, demo.V2)


@contextlib.contextmanager
def no_banners():
    """Every module a fragment of this scenario reaches, patched once."""
    with no_demo_banners(
        demo, rcvcv_fragments, coordinated_story, owner_decision_story
    ):
        yield


def five_party_state(joined: bool = True):
    """A story state seating all five, on an open case.

    C2's join is kept by default: the suggestion C2 makes reads it, because
    only a participant may suggest anyone (DEMOMA-19-009, #5535).
    """
    state = story_state(*CAST, case=mock_case())
    if joined:
        state.keep(rcvcv_fragments.C2_JOINED, str(state.case.id_))
    return state
