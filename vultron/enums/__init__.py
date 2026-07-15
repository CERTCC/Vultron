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

"""Bottom-of-stack neutral enumeration layer.

Enumerations that must be importable by ``vultron/core/``, ``vultron/config/``,
and ``vultron/adapters/`` without creating circular imports live here.

This package MUST NOT import from ``vultron.core``, ``vultron.config``,
or ``vultron.adapters``.  It is a pure enumeration layer with no domain logic
dependencies.

Per ``docs/adr/0031-vultron-enums-neutral-layer.md``.
"""

from vultron.enums.roles import CVDRole, serialize_roles, validate_roles

__all__ = ["CVDRole", "serialize_roles", "validate_roles"]
