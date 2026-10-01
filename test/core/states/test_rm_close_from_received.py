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
"""RM closure edges: ``R → C`` is planned, ``V → C`` stays forbidden.

ADR-0114 adds the ``RECEIVED → CLOSED`` edge so a ``Reject`` sent from RM
*Received* is an ordinary transition (RMB-14-004, tracked by #4044), while
*Valid* keeps no close edge (VP-02-004).  See ``notes/case-joining.md``.
"""

import pytest

from vultron.core.states.rm import (
    RM,
    create_rm_machine,
    is_valid_rm_transition,
)


@pytest.mark.xfail(
    strict=True,
    reason=(
        "RMB-14-004: the RM transition function permits R -> C."
        " Tracked by #4044."
    ),
)
@pytest.mark.spec("RMB-14-004")
def test_rm_closes_from_received_but_not_from_valid() -> None:
    """``R → C`` joins ``I → C``, ``A → C`` and ``D → C``; ``V → C`` does not."""
    assert is_valid_rm_transition(RM.RECEIVED, RM.CLOSED)
    for source in (RM.INVALID, RM.ACCEPTED, RM.DEFERRED):
        assert is_valid_rm_transition(source, RM.CLOSED), source
    assert not is_valid_rm_transition(RM.VALID, RM.CLOSED)

    machine = create_rm_machine()
    machine.set_state(RM.RECEIVED)
    assert RM.CLOSED in {
        t.dest
        for trigger in machine.get_triggers(RM.RECEIVED)
        for t in machine.get_transitions(trigger, source=RM.RECEIVED)
    }


@pytest.mark.spec("VP-02-004")
def test_rm_never_closes_from_valid() -> None:
    """A participant at RM *Valid* cannot close; it engages or defers first.

    Neither the transition predicate nor the state machine offers a
    ``VALID → CLOSED`` edge, and every close edge that does exist leaves a
    state other than *Valid*.
    """
    assert not is_valid_rm_transition(RM.VALID, RM.CLOSED)

    machine = create_rm_machine()
    close_sources = {
        t.source
        for t in machine.get_transitions(trigger="close")
        if t.dest == RM.CLOSED
    }
    assert close_sources, "the RM machine must define some close edge"
    assert RM.VALID not in close_sources
    # V reaches C only by way of D (or A): V -> D -> C.
    assert is_valid_rm_transition(RM.VALID, RM.DEFERRED)
    assert is_valid_rm_transition(RM.DEFERRED, RM.CLOSED)
