#!/usr/bin/env python

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

"""Exhaustive tests for the vfd/pxa monotone-forward predicates.

:func:`~vultron.core.states.cs.is_monotonic_vfd_forward` and
:func:`~vultron.core.states.cs.is_monotonic_pxa_forward` are the weaker
companions to the adjacency checks: a peer may report a state several steps
ahead of the one the receiver holds (a vendor that became aware, readied and
deployed a fix between two status updates reports ``vfd → VFD`` in one
message), and that is monotone but not an adjacent transition.

They are the acceptance rule for the ``vfd`` and ``pxa`` dimensions of a
received ``ParticipantStatus`` (RSH-05), so every ordered pair of states is
covered here rather than the handful the adjudication tests happen to exercise.

Both state groups are tuples of independent one-way latches, so the expected
answer is a *strict superset* test over the set-components: monotone forward iff
``dest`` sets at least one component that ``source`` had not set and un-sets
none.  Expressing the oracle as a bitmask subset test keeps it independent of
the position-wise component comparison the implementation uses.
"""

import itertools

import pytest

from vultron.core.states.cs import (
    CS_pxa,
    CS_vfd,
    is_monotonic_pxa_forward,
    is_monotonic_vfd_forward,
)

# ---------------------------------------------------------------------------
# Oracle
# ---------------------------------------------------------------------------


def _latch_bits(member: CS_vfd | CS_pxa) -> int:
    """Encode a state's set components as a bitmask.

    Each component of a ``VfdState``/``PxaState`` is a two-valued ``StrEnum``
    whose "set" value is spelled with an uppercase letter (``V``, ``F``, ``D``;
    ``P``, ``X``, ``A``).  The member *name* carries exactly that information,
    so the mask is read off the name rather than the ``NamedTuple``.
    """
    return sum(
        1 << index
        for index, letter in enumerate(member.name)
        if letter.isupper()
    )


def _expected_monotonic_forward(
    source: CS_vfd | CS_pxa, dest: CS_vfd | CS_pxa
) -> bool:
    """``dest`` is a strict superset of ``source``'s set components."""
    source_bits, dest_bits = _latch_bits(source), _latch_bits(dest)
    return source_bits != dest_bits and (source_bits & ~dest_bits) == 0


# ---------------------------------------------------------------------------
# vfd
# ---------------------------------------------------------------------------


class TestIsMonotonicVfdForward:
    ALL = list(CS_vfd)

    @pytest.mark.parametrize(
        "source,dest",
        list(itertools.product(list(CS_vfd), repeat=2)),
        ids=lambda m: m.name,
    )
    def test_every_ordered_pair(self, source, dest):
        assert is_monotonic_vfd_forward(
            source, dest
        ) is _expected_monotonic_forward(source, dest)

    @pytest.mark.parametrize("state", ALL, ids=lambda m: m.name)
    def test_equality_is_not_forward(self, state):
        """A status confirmation advances nothing; callers test equality."""
        assert is_monotonic_vfd_forward(state, state) is False

    @pytest.mark.parametrize(
        "source,dest",
        [
            (CS_vfd.vfd, CS_vfd.Vfd),
            (CS_vfd.Vfd, CS_vfd.VFd),
            (CS_vfd.VFd, CS_vfd.VFD),
        ],
        ids=["vfd->Vfd", "Vfd->VFd", "VFd->VFD"],
    )
    def test_adjacent_steps_are_forward(self, source, dest):
        assert is_monotonic_vfd_forward(source, dest) is True

    @pytest.mark.parametrize(
        "source,dest",
        [
            (CS_vfd.vfd, CS_vfd.VFd),
            (CS_vfd.vfd, CS_vfd.VFD),
            (CS_vfd.Vfd, CS_vfd.VFD),
        ],
        ids=["vfd->VFd", "vfd->VFD", "Vfd->VFD"],
    )
    def test_multi_step_jumps_are_forward(self, source, dest):
        """The whole point: adjacency is too strict for a peer's snapshot."""
        assert is_monotonic_vfd_forward(source, dest) is True

    @pytest.mark.parametrize(
        "source,dest",
        [
            (CS_vfd.VFD, CS_vfd.VFd),
            (CS_vfd.VFd, CS_vfd.Vfd),
            (CS_vfd.Vfd, CS_vfd.vfd),
            (CS_vfd.VFD, CS_vfd.vfd),
        ],
        ids=["VFD->VFd", "VFd->Vfd", "Vfd->vfd", "VFD->vfd"],
    )
    def test_regressions_are_refused(self, source, dest):
        assert is_monotonic_vfd_forward(source, dest) is False

    def test_forward_pair_count(self):
        """4 states on a single chain → 6 strictly-forward ordered pairs."""
        forward = [
            (s, d)
            for s, d in itertools.product(self.ALL, repeat=2)
            if is_monotonic_vfd_forward(s, d)
        ]
        assert len(forward) == 6

    def test_relation_is_antisymmetric(self):
        for s, d in itertools.product(self.ALL, repeat=2):
            if is_monotonic_vfd_forward(s, d):
                assert not is_monotonic_vfd_forward(d, s)


# ---------------------------------------------------------------------------
# pxa
# ---------------------------------------------------------------------------


class TestIsMonotonicPxaForward:
    ALL = list(CS_pxa)

    @pytest.mark.parametrize(
        "source,dest",
        list(itertools.product(list(CS_pxa), repeat=2)),
        ids=lambda m: m.name,
    )
    def test_every_ordered_pair(self, source, dest):
        assert is_monotonic_pxa_forward(
            source, dest
        ) is _expected_monotonic_forward(source, dest)

    @pytest.mark.parametrize("state", ALL, ids=lambda m: m.name)
    def test_equality_is_not_forward(self, state):
        assert is_monotonic_pxa_forward(state, state) is False

    @pytest.mark.parametrize(
        "source,dest",
        [
            (CS_pxa.pxa, CS_pxa.Pxa),
            (CS_pxa.pxa, CS_pxa.pXa),
            (CS_pxa.pxa, CS_pxa.pxA),
            (CS_pxa.pxa, CS_pxa.PXA),
            (CS_pxa.Pxa, CS_pxa.PXa),
            (CS_pxa.pXa, CS_pxa.PXA),
        ],
        ids=[
            "pxa->Pxa",
            "pxa->pXa",
            "pxa->pxA",
            "pxa->PXA",
            "Pxa->PXa",
            "pXa->PXA",
        ],
    )
    def test_independent_latches_may_set_in_any_combination(
        self, source, dest
    ):
        """P/X/A are mutually independent, so any newly-set subset is forward."""
        assert is_monotonic_pxa_forward(source, dest) is True

    @pytest.mark.parametrize(
        "source,dest",
        [
            (CS_pxa.Pxa, CS_pxa.pxa),
            (CS_pxa.PxA, CS_pxa.PXa),
            (CS_pxa.PXA, CS_pxa.pxa),
            (CS_pxa.PXa, CS_pxa.pXA),
        ],
        ids=["Pxa->pxa", "PxA->PXa", "PXA->pxa", "PXa->pXA"],
    )
    def test_any_component_regression_refuses_the_whole_move(
        self, source, dest
    ):
        """``PXa → pXA`` sets A but un-sets P — one latch reopening is enough."""
        assert is_monotonic_pxa_forward(source, dest) is False

    def test_forward_pair_count(self):
        """3 independent latches → 3**3 subset pairs, minus the 2**3 equal."""
        forward = [
            (s, d)
            for s, d in itertools.product(self.ALL, repeat=2)
            if is_monotonic_pxa_forward(s, d)
        ]
        assert len(forward) == 3**3 - 2**3

    def test_relation_is_antisymmetric(self):
        for s, d in itertools.product(self.ALL, repeat=2):
            if is_monotonic_pxa_forward(s, d):
                assert not is_monotonic_pxa_forward(d, s)

    def test_relation_is_transitive(self):
        for a, b, c in itertools.product(self.ALL, repeat=3):
            if is_monotonic_pxa_forward(a, b) and is_monotonic_pxa_forward(
                b, c
            ):
                assert is_monotonic_pxa_forward(a, c)
