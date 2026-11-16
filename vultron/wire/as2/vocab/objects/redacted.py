#!/usr/bin/env python
"""Wire registration of the ``Redacted`` marker (ADR-0193, MV-12).

The core class is the marker's only form (ARCH-25-003, ADR-0099).
Registering it in ``WIRE_TYPE_MAP`` declares ``Redacted`` a Vultron type term,
so ``wire-context`` writes its ``vultron:Redacted`` term
(``notes/vocabulary-registry.md`` § "4a. Declaring a Vultron extension term").
Registration opens no field to the marker: each field's own type still refuses
it until a preview type declares a field that accepts it (MV-12-002).
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

from vultron.core.models.redacted import Redacted
from vultron.wire.as2.vocab.base.registry import WIRE_TYPE_MAP

WIRE_TYPE_MAP["Redacted"] = Redacted
