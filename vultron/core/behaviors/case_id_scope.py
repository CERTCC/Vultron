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

"""Seed a node's ``/case_id`` port with a case a tree knows at build time.

A node that some tree hands its case only at tick time reads ``case_id`` from
its declared ``/case_id`` input port in every tree, never also from a
constructor argument (BTND-01-006, BTND-01-007).  A tree that *does* know the
case when it is built seeds that port instead: :func:`with_case_id` is the
interim key seeder (:func:`~vultron.core.behaviors.act_key_scope.with_act_keys`)
called for ``/case_id`` alone.  It writes the case for the node's own tick
and puts back whatever the key held before (BTND-10-005, ADR-0089).

The close-out Task (#6593) deletes this module with the seeder.
"""

import py_trees

from vultron.core.behaviors.act_key_scope import (
    seeded_value,
    unscoped,
    with_act_keys,
)
from vultron.core.behaviors.act_keys import CASE_ID

__all__ = ["seeded_case_id", "unscoped", "with_case_id"]


def with_case_id(
    node: py_trees.behaviour.Behaviour, case_id: str | None
) -> py_trees.behaviour.Behaviour:
    """*node* with its ``/case_id`` port seeded to *case_id*, when there is one.

    A tree that names no case at build time passes ``None`` (or ``""``) and
    gets *node* back unwrapped: the node then reads the ``/case_id`` an
    earlier node of the same execution published, or its documented
    tick-time resolution step.
    """
    return with_act_keys(node, {CASE_ID: case_id})


def seeded_case_id(node: py_trees.behaviour.Behaviour) -> str | None:
    """The case a seeding scope directly above *node* seeds, or ``None``.

    For code that reads which case a tree hands a node at build time.
    """
    value = seeded_value(node, CASE_ID)
    return value if isinstance(value, str) else None
