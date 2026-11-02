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
"""RM edges a duplicate report takes: through *Valid*, then deferred.

A duplicate report passes through RM *Valid* (VP-02-023), and a Participant
may then defer it in favor of the original report (VP-02-036).  The *Valid*
to *Deferred* edge is what makes that deferral an ordinary RM transition.
"""

import pytest

from vultron.core.states.rm import (
    RM,
    RM_Trigger,
    create_rm_machine,
    is_valid_rm_transition,
)


@pytest.mark.spec("VP-02-036")
def test_a_valid_report_can_be_deferred() -> None:
    """``defer`` takes a report from *Valid* straight to *Deferred*."""
    assert is_valid_rm_transition(RM.VALID, RM.DEFERRED)

    machine = create_rm_machine()
    defer_edges = {
        (t.source, t.dest)
        for t in machine.get_transitions(trigger=RM_Trigger.DEFER)
    }
    assert (RM.VALID, RM.DEFERRED) in defer_edges
