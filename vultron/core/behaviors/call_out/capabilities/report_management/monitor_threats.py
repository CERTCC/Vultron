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
"""Core capability declarations for ``report_management.monitor_threats``.

Each class declares one named capability's blackboard contract as typed
ports (BT-18-012).  Its simulation node, in
``vultron.demo.fuzzer.report_management.monitor_threats``,
subclasses the declaration rather than restating it (BT-18-021).
"""

from __future__ import annotations

from vultron.core.behaviors.call_out.capability import (
    RetrieverCapability,
)


class MonitorAttacksCapability(RetrieverCapability):
    """Monitor threat-intelligence feeds for active attacks on the vulnerability.

    Blackboard contract (BT-18-001):
      Input keys:  (none — queries TI feeds and SIEM for attack signals)
      Output keys: (none — binary result only, per BT-18-006)
      Refusal keys: call_out_refusal_reason: str  (no only)

    Store-held answer (BT-18-039): **can**, in part — the case's
    attacks-observed bit (``A``) records attacks the case already knows of,
    so a tree that places this Retriever reads that bit first and asks only
    while it is unset.  No core tree places it today.
    """


class MonitorExploitsCapability(RetrieverCapability):
    """Monitor threat-intelligence feeds for public exploits of the vulnerability.

    Blackboard contract (BT-18-001):
      Input keys:  (none — queries exploit databases and TI platforms)
      Output keys: (none — binary result only, per BT-18-006)
      Refusal keys: call_out_refusal_reason: str  (no only)

    Store-held answer (BT-18-039): **can**, in part — the case's
    exploit-public bit (``X``) records a public exploit the case already
    knows of, so a tree that places this Retriever reads that bit first and
    asks only while it is unset.  No core tree places it today.
    """


class MonitorPublicReportsCapability(RetrieverCapability):
    """Monitor public sources for disclosure of the vulnerability.

    Blackboard contract (BT-18-001):
      Input keys:  (none — scans public news feeds, mailing lists, social media)
      Output keys: (none — binary result only, per BT-18-006)
      Refusal keys: call_out_refusal_reason: str  (no only)

    Store-held answer (BT-18-039): **can**, in part — the case's
    public-awareness bit (``P``) records a disclosure the case already
    knows of, so a tree that places this Retriever reads that bit first and
    asks only while it is unset.  No core tree places it today.
    """


__all__ = [
    "MonitorAttacksCapability",
    "MonitorExploitsCapability",
    "MonitorPublicReportsCapability",
]
