#!/usr/bin/env python
"""
Wire-layer alias for CaseReference.

Per ADR-0099 detail 3: the core class is the canonical form.
The as_-prefixed names are retained for backward compatibility.
"""

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

from typing import TypeAlias

from vultron.core.models.case_reference import CaseReference
from vultron.wire.as2.vocab.base.links import ActivityStreamRef
from vultron.wire.as2.vocab.base.registry import WIRE_TYPE_MAP

# Backward-compatibility alias (ADR-0099 detail 3)
as_CaseReference = CaseReference

# Register core class in WIRE_TYPE_MAP so the parser admits it inline
WIRE_TYPE_MAP["CaseReference"] = CaseReference

as_CaseReferenceRef: TypeAlias = ActivityStreamRef[CaseReference]
