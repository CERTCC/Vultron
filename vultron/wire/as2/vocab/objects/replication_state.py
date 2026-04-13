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
"""Wire-layer vocabulary registration for :class:`VultronReplicationState`.

The canonical class definition lives in
:mod:`vultron.core.models.replication_state`.  This module re-exports it and
registers it in the wire-layer vocabulary under ``"ReplicationState"`` so that
DataLayer round-trips reconstruct the object correctly.

Spec: SYNC-04-001, SYNC-04-002.
"""

from vultron.core.models.replication_state import (  # noqa: F401
    VultronReplicationState,
)
from vultron.wire.as2.vocab.base.registry import VOCABULARY

VOCABULARY["ReplicationState"] = VultronReplicationState

__all__ = ["VultronReplicationState"]
