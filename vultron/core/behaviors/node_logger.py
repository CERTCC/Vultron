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

"""Resolve the stdlib logger a behavior-tree node logs through.

A plain ``py_trees`` node's ``logger`` attribute is ``py_trees.logging.Logger``,
not a :class:`logging.Logger`: it is not part of the standard logging hierarchy,
and its level methods take a single pre-rendered message. A literal template
with lazy positional arguments (SL-01-005) therefore raises ``TypeError`` when
handed to it. Vultron nodes log through the stdlib logger this module returns
instead, named ``<module>.<class>`` after the node's class.
"""

import logging

import py_trees.behaviour


def node_logger(node: py_trees.behaviour.Behaviour) -> logging.Logger:
    """Return the stdlib logger for *node*, named after its class.

    Every node of one class shares the same logger, so a node that rebinds
    ``self.logger`` to this value and a helper that logs on that node's behalf
    write to the same place.
    """
    cls = type(node)
    return logging.getLogger(f"{cls.__module__}.{cls.__name__}")
