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

"""The cast and story state the vendor-first story package's tests share."""

from test.demo._helpers import mock_case, story_state
from vultron.demo.helpers import vendor_story as family
from vultron.demo.helpers.coordinated_story import REPORTER
from vultron.demo.helpers.story import StoryState

#: The two members the shared opening seats, in ``seed_containers`` order.
SEATED = (REPORTER, family.VENDOR)


def family_state(*extra: str) -> StoryState:
    """A story state seating the two the opening seeds, plus *extra*.

    The roster prop is kept, because every fragment of the family reads it
    before it acts (DEMOCI-01-011) and only the tests about its absence run
    without it.
    """
    state = story_state(*SEATED, *extra, case=mock_case())
    state.keep(family.THE_VENDORS_CASE, str(state.case.id_))
    return state
