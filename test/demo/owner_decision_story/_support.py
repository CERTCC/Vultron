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

"""The neutral cast and stand-in story the continuation tests share."""

import contextlib

from test.demo._helpers import mock_case, no_demo_banners, story_state
from vultron.demo.helpers import (
    coordinated_story,
    owner_decision_story,
)
from vultron.demo.helpers.coordinated_story import REPORTER
from vultron.demo.helpers.owner_decision_story import Part
from vultron.demo.helpers.story import StoryProp

#: A neutral cast, named for the part each plays rather than for either pair's
#: actors: the two-coordinator pair runs these continuations with C1, C2 and a
#: Vendor, the vendor-first pair with Vendor1, a Coordinator and Vendor2.
OWNER = Part("owner", "Owner")
JOINER = Part("joiner", "Joiner")
NEWCOMER = Part("newcomer", "Newcomer")

#: The join prop the pair's roster gate keeps and both continuations read:
#: each presupposes the joiner being an active participant (DEMOMA-13-003,
#: DEMOMA-14-010), so the module's state keeps it and two tests take it away.
JOINED: StoryProp[str] = StoryProp("test pair's join", str)

#: Every cast name a continuation of this module reaches.
CAST = (REPORTER, OWNER.name, JOINER.name, NEWCOMER.name)

#: The roster both continuations gate their newcomer's triage on.
SEATED = (REPORTER, OWNER.name, JOINER.name, NEWCOMER.name)


@contextlib.contextmanager
def no_banners():
    """Every module a fragment of this scenario reaches, patched once."""
    with no_demo_banners(owner_decision_story, coordinated_story):
        yield


def continuation_state(joined: bool = True):
    """A story state seating the neutral cast, on an open case.

    The join prop both continuations read is kept by default, because every
    test but the two about its absence runs past that read.
    """
    state = story_state(*CAST, case=mock_case())
    if joined:
        state.keep(JOINED, str(state.case.id_))
    return state
