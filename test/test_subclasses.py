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
"""Unit tests for :func:`vultron.subclasses.all_subclasses` (CS-22-001)."""

from vultron.subclasses import all_subclasses


class _Root:
    pass


class _Left(_Root):
    pass


class _Right(_Root):
    pass


class _Diamond(_Left, _Right):
    pass


class _Leaf(_Diamond):
    pass


def test_excludes_the_root() -> None:
    assert _Root not in all_subclasses(_Root)


def test_includes_direct_and_indirect_subclasses() -> None:
    assert all_subclasses(_Root) == {_Left, _Right, _Diamond, _Leaf}


def test_a_class_reached_through_two_parents_is_found_from_either() -> None:
    """``_Diamond`` sits under both ``_Left`` and ``_Right``."""
    assert all_subclasses(_Left) == {_Diamond, _Leaf}
    assert all_subclasses(_Right) == {_Diamond, _Leaf}


def test_a_leaf_has_no_subclasses() -> None:
    assert all_subclasses(_Leaf) == set()
