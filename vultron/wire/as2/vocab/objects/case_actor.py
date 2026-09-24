#!/usr/bin/env python
"""
Wire-layer alias for CaseActor.

Per ADR-0099 detail 3: the core class is the canonical form.
The as_-prefixed name is retained for backward compatibility.
"""

#  Copyright (c) 2025 Carnegie Mellon University and Contributors.
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

from vultron.core.models.case_actor import CaseActor

# Backward-compatibility alias (ADR-0099 detail 3).  Not registered in
# WIRE_TYPE_MAP: a CaseActor emits ``type: "Service"``, and that key belongs to
# VultronService (VM-01-008, #2982).
as_CaseActor = CaseActor
