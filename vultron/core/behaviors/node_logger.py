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

py_trees' typed-ports layer logs one line per port as a node registers its
blackboard keys.  Those lines restate the node class's declared ports on every
tree build, so Vultron nodes hand ``setup_ports`` the shared
:func:`port_wiring_logger` rather than their own (#4600).
"""

import logging

import py_trees.behaviour
from py_trees.common import Status

from vultron.core.models.refusal_wording import without_refusal_group


def node_logger(node: py_trees.behaviour.Behaviour) -> logging.Logger:
    """Return the stdlib logger for *node*, named after its class.

    Every node of one class shares the same logger, so a node that rebinds
    ``self.logger`` to this value and a helper that logs on that node's behalf
    write to the same place.
    """
    cls = type(node)
    return logging.getLogger(f"{cls.__module__}.{cls.__name__}")


def fail_with_reason(
    node: py_trees.behaviour.Behaviour, reason: str
) -> Status:
    """Record *reason* as *node*'s failure reason, log its facts; ``FAILURE``.

    *reason* becomes ``feedback_message``, which is what
    ``BTBridge.get_failure_reason`` reports (BT-13-001), so a reason worded
    as a refusal keeps its ``— REFUSED (IDs)`` group there.  The node's own
    line is DEBUG and drops that group: a node does not know whether its
    FAILURE is the delivery's verdict — a later Selector arm may admit the
    sender, or the reading may report the run ``SKIPPED`` — so the received
    runner, which does, logs the one ``REFUSED`` line (SL-03-002 to
    SL-03-004).

    Writes through :func:`node_logger`, so the line lands where the node's
    own ``self.logger`` lines land (SL-01-005).
    """
    node.feedback_message = reason
    node_logger(node).debug("%s: %s", node.name, without_refusal_group(reason))
    return Status.FAILURE


#: The logger py_trees' typed-ports layer writes to for Vultron nodes.
PORT_WIRING_LOGGER_NAME = "vultron.core.behaviors.port_wiring"


def port_wiring_logger() -> logging.Logger:
    """Return the logger to pass as ``setup_ports(logger=...)``.

    Port registration is wiring, not run-time state: one DEBUG line per port,
    identical on every build of the same node class, and in CI over half of
    every container's DEBUG output (#4600).  Routing it here lets the entry
    points keep it at INFO (:data:`vultron.logging_setup.STATIC_WIRING_LOGGERS`)
    while the rest of the BT stays at DEBUG; py_trees' port-conversion warnings
    still come through at WARNING.  To see the wiring, set this logger to DEBUG
    after the entry point has configured logging, which overwrites any earlier
    level.
    """
    return logging.getLogger(PORT_WIRING_LOGGER_NAME)
