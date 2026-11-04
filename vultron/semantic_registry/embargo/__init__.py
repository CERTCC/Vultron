"""Embargo-domain semantic registry entries.

Each submodule holds one contiguous slice of the original dispatch order;
``ENTRIES`` concatenates them in that order (more specific patterns first).
"""

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

from vultron.semantic_registry._entry import SemanticEntry

from . import case_event, decision, invitation, record

ENTRIES: list[SemanticEntry] = (
    case_event.ENTRIES + invitation.ENTRIES + decision.ENTRIES + record.ENTRIES
)
