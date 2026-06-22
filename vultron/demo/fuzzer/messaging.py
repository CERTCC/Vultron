#!/usr/bin/env python
#  Copyright (c) 2023-2025 Carnegie Mellon University and Contributors.
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
"""Inbound messaging fuzzer nodes for the Vultron demo layer.

This module provides probabilistic stub ``py_trees`` behaviour nodes for the
inbound message handling workflow (``ReceiveMessagesBt``).  Each node
represents an external-dependency touchpoint that will eventually be replaced
by production logic.

Nodes are built on the probabilistic base types in
``vultron.demo.fuzzer.base`` and satisfy BT-16-003 (named integration-point
nodes with semantic docstrings) and BT-16-005 (automation-potential
categorization).

References
----------
- Source: ``vultron/bt/messaging/inbound/_behaviors/fuzzer.py``
- Spec: ``specs/behavior-tree-integration.yaml`` BT-16-003, BT-16-004, BT-16-005
- Notes: ``notes/bt-fuzzer-nodes-messaging.md``
"""

from __future__ import annotations

from vultron.demo.fuzzer.base import UniformSucceedFail


class FollowUpOnErrorMessage(UniformSucceedFail):
    """Attempt to send a follow-up inquiry when an error message is received.

    Semantic function:
        Action — when an unexpected or error message type is received,
        attempt to send a follow-up inquiry (GI message) to the sender
        to request clarification.  Implemented in the original source as
        a fallback containing a 50/50 random success and an
        ``EmitGI`` action; the net effect is stochastic success at
        p=0.50.

    Input category: System integration / Human analyst.

    Success probability: 0.50 (``UniformSucceedFail``).

    Automation potential: **High** — deterministic policy-driven GI
    message dispatch in response to error conditions; can be fully
    automated once the follow-up policy is defined.
    """
