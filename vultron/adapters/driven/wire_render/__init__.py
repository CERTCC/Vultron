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

"""Adapter implementing
:class:`~vultron.core.ports.wire_render.WireRenderPort`.

Renders a core domain object to wire-shaped (camelCase) JSON without
the core layer importing from the wire layer (ARCH-01-001).

See also:
    - ``vultron/core/ports/wire_render.py`` — port Protocol
    - ``docs/adr/0063-wire-rendering-port-for-core-objects.md`` — ADR
"""

from .as2 import As2WireRenderAdapter

__all__ = ["As2WireRenderAdapter"]
