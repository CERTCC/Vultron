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

"""Feedback messages for a BT node composed without a dependency it needs.

A received handler raises on these rather than refusing the sender (#2255).
"""

DATALAYER_UNAVAILABLE = "DataLayer not available"
DATALAYER_OR_ACTOR_UNAVAILABLE = "DataLayer or actor_id not available"
TRIGGER_FACTORY_UNAVAILABLE = "trigger_activity_factory not available"
WIRE_RENDER_PORT_UNAVAILABLE = (
    "wire_render_port not available; core cannot render the AS2 shape itself"
    " (ARCH-20-001)"
)
# The received event was not placed on the blackboard (``activity=`` omitted
# from ``execute_with_setup``): the intake node cannot record what arrived.
ACTIVITY_UNAVAILABLE = "received activity not available"
WIRING_UNAVAILABLE_MESSAGES = frozenset(
    {
        DATALAYER_UNAVAILABLE,
        DATALAYER_OR_ACTOR_UNAVAILABLE,
        TRIGGER_FACTORY_UNAVAILABLE,
        WIRE_RENDER_PORT_UNAVAILABLE,
        ACTIVITY_UNAVAILABLE,
    }
)
