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
"""Wire-layer vocabulary for the case's preview (ADR-0205).

Per ARCH-25-003 (ADR-0099): :class:`CasePreview` is the canonical form.
``as_CasePreview`` is its wire alias, the ``preview`` of the typed case
reference a stub Invite carries as its ``object`` (MV-10-012).
"""

from vultron.core.models.case_preview import CasePreview
from vultron.wire.as2.vocab.base.registry import WIRE_TYPE_MAP

# Wire alias of the one class (ARCH-25-003, ADR-0099)
as_CasePreview = CasePreview

# Register the core class in WIRE_TYPE_MAP so the parser admits it inline
WIRE_TYPE_MAP["CasePreview"] = CasePreview

__all__ = ["as_CasePreview"]
