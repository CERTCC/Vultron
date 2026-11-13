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

"""``rm_transition_trigger`` names each edge of the RM transition function."""

import pytest

from vultron.core.states.rm import (
    RM,
    RM_Trigger,
    is_valid_rm_transition,
    rm_transition_trigger,
)


@pytest.mark.parametrize("source", list(RM))
@pytest.mark.parametrize("dest", list(RM))
def test_a_trigger_exactly_for_each_edge(source, dest):
    trigger = rm_transition_trigger(source, dest)
    assert (trigger is not None) == is_valid_rm_transition(source, dest)


def test_each_edge_names_its_own_trigger():
    assert rm_transition_trigger(RM.START, RM.RECEIVED) is RM_Trigger.RECEIVE
    assert rm_transition_trigger(RM.INVALID, RM.VALID) is RM_Trigger.VALIDATE
    assert rm_transition_trigger(RM.ACCEPTED, RM.DEFERRED) is RM_Trigger.DEFER
    assert rm_transition_trigger(RM.DEFERRED, RM.CLOSED) is RM_Trigger.CLOSE
