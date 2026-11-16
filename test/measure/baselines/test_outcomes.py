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

"""The walk started where a case stands, and the ends it can still reach (ADR-0182)."""

from fractions import Fraction

from vultron.core.states.cs import CS_d, CS_pxa, CS_vf
from vultron.core.states.em import EM
from vultron.core.states.rm import RM
from vultron.measure.baselines import (
    ONE_VENDOR_MODEL,
    EmbargoEnd,
    Event,
    EventKind,
    JointState,
    StartedAt,
    VendorPath,
    frequency,
    ordering,
    reachable_ends,
)

_E, _P = Event(EventKind.EMBARGO_START), Event(EventKind.P)
_EX_OWN = Event(EventKind.EXIT_OWN_TERMS)
_DONE = VendorPath(RM.CLOSED, CS_vf.VF, CS_d.D)


def test_a_walk_started_at_the_models_start_is_the_models_walk():
    query = ordering(_E, _P)
    started = StartedAt(ONE_VENDOR_MODEL, ONE_VENDOR_MODEL.initial)
    assert frequency(started, query) == frequency(ONE_VENDOR_MODEL, query)


def test_walks_started_at_one_state_of_one_model_are_equal():
    state = ONE_VENDOR_MODEL.initial
    assert StartedAt(ONE_VENDOR_MODEL, state) == StartedAt(
        ONE_VENDOR_MODEL, state
    )
    assert hash(StartedAt(ONE_VENDOR_MODEL, state)) == hash(
        StartedAt(ONE_VENDOR_MODEL, state)
    )
    assert StartedAt(ONE_VENDOR_MODEL, state) != state


def test_an_active_embargo_ends_on_its_own_terms_one_time_in_five():
    """Five steps settle it: ``P``, ``X``, ``A``, an own-terms exit and
    another exit; a revision only delays them."""
    state = JointState((_DONE,), CS_pxa.pxa, EM.ACTIVE)
    started = StartedAt(ONE_VENDOR_MODEL, state)
    assert frequency(started, ordering(_EX_OWN, _P)) == Fraction(1, 5)


def test_the_reachable_ends_are_found_from_where_the_walk_starts():
    active = StartedAt(
        ONE_VENDOR_MODEL, JointState((_DONE,), CS_pxa.pxa, EM.ACTIVE)
    )
    query = ordering(_EX_OWN, _P)
    assert reachable_ends(active, query) == {frozenset(), frozenset({0})}
    ended = StartedAt(
        ONE_VENDOR_MODEL,
        JointState((_DONE,), CS_pxa.PXA, EM.EXITED, EmbargoEnd.THREAT_SIGNAL),
    )
    assert reachable_ends(ended, query) == {frozenset()}


def test_an_end_missing_a_given_event_is_not_reachable():
    ended = StartedAt(
        ONE_VENDOR_MODEL,
        JointState((_DONE,), CS_pxa.PXA, EM.EXITED, EmbargoEnd.THREAT_SIGNAL),
    )
    assert reachable_ends(ended, ordering(_P, _P, given=[_EX_OWN])) == set()
