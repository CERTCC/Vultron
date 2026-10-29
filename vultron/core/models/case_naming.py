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

"""The acts that name their case rather than carry it (AKM-03-004, ADR-0165).

A participant's ``Join``, ``Ignore`` and ``Leave`` of a case and the
ownership-transfer ``Offer`` carry the case as a typed reference, an inline
object with only its ``id`` and ``type``.  Their receivers hold the case, so a
case in one of these slots is never a source of records.  Shared by the wire
parse edge, which admits a case reference only there, and the replica's
case-copy reflection, which copies nothing out of such a case.
"""

#: The activity types whose ``object`` names a case without carrying it.
CASE_NAMING_ACTIVITY_TYPES: frozenset[str] = frozenset(
    {"Join", "Ignore", "Leave", "Offer"}
)

__all__ = ["CASE_NAMING_ACTIVITY_TYPES"]
