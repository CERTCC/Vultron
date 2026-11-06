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

"""Cast names and shared stubs the coordinator-first story tests share."""

from collections.abc import Iterator
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

from vultron.demo.helpers.coordinated_story import (
    COORDINATOR,
    REPORTER,
    VENDOR,
    continuations,
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


@contextmanager
def patched_rejection_polls() -> Iterator[SimpleNamespace]:
    """Stub every container read ``vendor_rejects_invite`` makes.

    The fragment gates its participant checks on the ``Reject`` reaching the
    CASE_MANAGER's ledger.  Against the ``MagicMock`` stores ``story_state``
    builds, that gate's poll runs to the end of its budget — 20 s — and then
    fails inside the ``demo_gate``, which swallows it and skips the three
    nested reads.  So a test that leaves them real pays 20 s to reach the same
    state it would have reached at once (#5597).

    Tests about what the fragment *decides* stub them and ignore the mocks; the
    one test about which client each read goes through inspects them (#1876).
    """
    with (
        patch.object(
            continuations, "wait_for_semantic_type_in_ledger"
        ) as ledger,
        patch.object(continuations, "wait_for_case_participants") as roster,
        patch.object(
            continuations, "wait_for_participant_rm_state"
        ) as rm_wait,
        patch.object(
            continuations, "_check_participant_rm_state_in"
        ) as rm_check,
    ):
        yield SimpleNamespace(
            ledger=ledger, roster=roster, rm_wait=rm_wait, rm_check=rm_check
        )
