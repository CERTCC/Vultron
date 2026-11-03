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

"""Cast names the coordinator-first story package's tests share."""

from vultron.demo.helpers.coordinated_story import (
    COORDINATOR,
    REPORTER,
    VENDOR,
)
from vultron.demo.helpers.story import StoryProp

#: The family's three fixed-role members, in seating order.
CAST = (REPORTER, COORDINATOR, VENDOR)

#: A character actor this family's continuations bring in mid-story: the second
#: Coordinator of ``rcvcv`` and the second Vendor of ``rcvv-embargo`` are both
#: seated under a name the shared opening never sees.
JOINER = "joiner"

#: A stand-in for the prop a caller hands ``invitee_joins_the_case``, where
#: the two-coordinator pair hands it ``SECOND_COORDINATOR_JOINED`` (#5535).
JOINED: StoryProp[str] = StoryProp("case the test joiner joined", str)
