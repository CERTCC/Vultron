#!/usr/bin/env python

#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
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
"""
Wire-layer object rehydration utilities.

``rehydrate`` converts a loosely-typed ``as_Object`` (or a string ID reference)
into the correct wire-vocabulary subclass.  Callers MUST pass the active
``DataLayer`` instance via the *dl* parameter so that string ID references can
be resolved without importing a concrete adapter.

**This package owns ID-to-object materialisation** (VM-06-007, ARCH-25-009;
ADR-0099).  See :func:`materialise_object_slots` for the rule and for why the
fabricated-stub behaviour it replaces is not reproduced.
"""

from vultron.wire.as2.rehydration.resolve import (
    MAX_REHYDRATION_DEPTH,
    rehydrate,
)
from vultron.wire.as2.rehydration.slots import (
    materialise,
    materialise_object_slots,
)

__all__ = [
    "MAX_REHYDRATION_DEPTH",
    "materialise",
    "materialise_object_slots",
    "rehydrate",
]
