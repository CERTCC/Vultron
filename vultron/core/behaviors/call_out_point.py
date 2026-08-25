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
"""Backward-compatible re-export of :class:`CallOutBackendFactory`.

The canonical Protocol definition now lives in
:mod:`vultron.core.behaviors.call_out.protocol`, co-located with the
deterministic call-out nodes and the ``<DOMAIN>_DETERMINISTIC`` bundle
singletons (ADR-0025 corrected layering).  This module re-exports it so that
existing ``from vultron.core.behaviors.call_out_point import
CallOutBackendFactory`` imports keep working.

New code SHOULD import from ``vultron.core.behaviors.call_out`` instead.

References
----------
- ADR-0025: ``docs/adr/0025-call-out-point-abstraction-layer.md``
- Spec: ``specs/behavior-tree-integration.yaml`` BT-18-004, BT-23-004
"""

from __future__ import annotations

# Backward-compatible re-export shim.  The canonical definition now lives in
# ``vultron.core.behaviors.call_out.protocol`` alongside the deterministic
# nodes and DETERMINISTIC bundle singletons (ADR-0025 corrected layering).
# Existing imports of ``CallOutBackendFactory`` from this module continue to
# resolve to the same object.
from vultron.core.behaviors.call_out.protocol import CallOutBackendFactory

__all__ = ["CallOutBackendFactory"]
