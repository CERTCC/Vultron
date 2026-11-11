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
"""Probabilistic fuzzer node for participant suggestion (ADR-0186).

The node stands in for a participant suggester in fuzz runs.  It answers
*yes* with an empty list of suggestions, the type-conformant synthetic value
BT-18-003 asks for; a demo scenario that needs real suggestions answers the
port with a static adapter over a declared candidate table instead
(BT-24-007).

References
----------
- Spec: ``specs/behavior-tree-integration.yaml`` BT-16-003, BT-18-003, BT-24
"""

from __future__ import annotations

from vultron.core.behaviors.call_out.capabilities.participant_suggestion import (
    SuggestParticipantsCapability,
)
from vultron.demo.fuzzer.base import AlmostAlwaysSucceed


class SuggestParticipants(SuggestParticipantsCapability, AlmostAlwaysSucceed):
    """Suggest the parties a case is missing, each with a role and a reason.

    Simulates :class:`SuggestParticipantsCapability`, whose ports are its
    blackboard contract (BT-18-021).

    Semantic function:
        Retriever — a suggester reads the reports' content and the current
        participants and names the vendors, coordinators and others the
        report implicates but the case lacks.  Modeled as almost always
        answering, because a lookup service is usually reachable; its *yes*
        names nobody.

    Input category: External data (vendor and product directories, CSAF
    product trees, past cases).

    Success probability: 0.90 (``AlmostAlwaysSucceed``).

    Automation potential: **High** for vendors named in the report and its
    attachments; **Medium** for parties implied only by the affected
    products' supply chain.
    """


__all__ = ["SuggestParticipants"]
