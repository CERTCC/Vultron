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
"""RM closure edges: ``R → C`` is permitted, ``V → C`` stays forbidden.

ADR-0114 adds the ``RECEIVED → CLOSED`` edge so a ``Reject`` sent from RM
*Received* is an ordinary transition (RMB-14-004, #4044), while *Valid*
keeps no close edge (VP-02-004).  The closure paths that ``RMClosureWriter``
walks (RMB-14-005) are pinned here against the transition table.  See
``notes/case-joining.md``.
"""

from itertools import pairwise

import pytest

from vultron.core.states.rm import (
    RM,
    RM_CLOSABLE,
    RM_CLOSURE_RUNGS,
    create_rm_machine,
    is_valid_rm_transition,
    rm_closure_path,
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


@pytest.mark.spec("RMB-14-003")
def test_rm_closable_names_exactly_the_close_edge_sources() -> None:
    """``RM_CLOSABLE`` is the set of states with a close edge: R, I, D, A."""
    machine = create_rm_machine()
    close_sources = {
        t.source
        for t in machine.get_transitions(trigger="close")
        if t.dest == RM.CLOSED
    }
    assert close_sources == set(RM_CLOSABLE)
    assert set(RM_CLOSABLE) == {
        RM.RECEIVED,
        RM.INVALID,
        RM.DEFERRED,
        RM.ACCEPTED,
    }
    for state in RM:
        assert is_valid_rm_transition(state, RM.CLOSED) is (
            state in RM_CLOSABLE
        ), state


@pytest.mark.spec("RMB-14-005")
@pytest.mark.parametrize("source", list(RM))
def test_rm_closure_path_is_a_chain_of_ordinary_transitions(
    source: RM,
) -> None:
    """Every closure path is a run of legal RM transitions ending at CLOSED."""
    path = rm_closure_path(source)
    if source == RM.CLOSED:
        assert path == ()
        return
    assert path[-1] == RM.CLOSED
    rungs = (source, *path)
    for prev, nxt in pairwise(rungs):
        assert is_valid_rm_transition(prev, nxt), (prev, nxt)
    assert set(path) <= set(RM_CLOSURE_RUNGS)


@pytest.mark.spec("RMB-14-005")
@pytest.mark.spec("VP-02-004")
def test_rm_closure_path_from_valid_passes_through_deferred() -> None:
    """A Leave from *Valid* is recorded as ``V → D → C``, never ``V → C``."""
    assert rm_closure_path(RM.VALID) == (RM.DEFERRED, RM.CLOSED)


@pytest.mark.spec("RMB-14-005")
@pytest.mark.parametrize("source", list(RM_CLOSABLE), ids=str)
def test_rm_closure_path_from_closable_state_is_one_step(source: RM) -> None:
    """From R, I, A or D a closure is the single transition to CLOSED."""
    assert rm_closure_path(source) == (RM.CLOSED,)
