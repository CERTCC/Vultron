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
"""Call-out bundle for received-side status update authorization (RSH-01-002).

Provides :class:`StatusAuthorizationCallOutBundle` and the pre-built core
deterministic singleton :data:`STATUS_AUTHORIZATION_DETERMINISTIC`.  A
probabilistic STOCHASTIC singleton lives in the simulation/demo layer.

Ceiling/floor mapping:

- ``status_update_guard_factory`` — CaseOwnerApprovesStatusUpdate → AlwaysSucceed

The deterministic singleton approves all non-CASE_OWNER status updates,
which preserves the historical behavior of ``add_participant_status_tree``
before Seam 1 was introduced.  Production adapters (e.g. a human-in-the-loop
review queue) replace this factory via constructor injection.

Per RSH-01-002, ADR-0046.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import py_trees

from vultron.core.behaviors.call_out.nodes import AlwaysSucceed
from vultron.core.behaviors.call_out.protocol import CallOutBackendFactory


def _always_succeed(name: str) -> py_trees.behaviour.Behaviour:
    return AlwaysSucceed(name)


@dataclass(frozen=True)
class StatusAuthorizationCallOutBundle:
    """Call-out backend bundle for received-side status authorization (RSH-01-002).

    Fields map to the corresponding factory parameters on
    :func:`~vultron.core.behaviors.status.add_participant_status_tree.add_participant_status_bt`.

    ``status_update_guard_factory`` backs the ``CaseOwnerApprovesStatusUpdate``
    call-out node inside ``StatusUpdateGuard``.  When ``CheckIsCaseOwnerNode``
    already returns SUCCESS, this factory is never called (the Fallback's
    first child short-circuits).
    """

    status_update_guard_factory: CallOutBackendFactory = field(
        default=_always_succeed  # type: ignore[assignment]
    )


STATUS_AUTHORIZATION_DETERMINISTIC = StatusAuthorizationCallOutBundle()
"""Deterministic bundle: approves all non-CASE_OWNER status updates.

Preserves historical ``add_participant_status_tree`` behavior before
Seam 1 authorization was introduced (ADR-0046).
"""

__all__ = [
    "StatusAuthorizationCallOutBundle",
    "STATUS_AUTHORIZATION_DETERMINISTIC",
]
