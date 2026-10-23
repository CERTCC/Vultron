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
"""Shared base for call-out bundles: guard every factory field (BT-18-011).

:class:`CallOutBundle` is the mixin base every ``<Domain>CallOutBundle`` frozen
dataclass inherits from. Its ``__post_init__`` wraps each call-out factory field
with :func:`~vultron.core.behaviors.call_out.guard.guard_call_out_factory`, so
the node any bundle field produces is guarded against a ``Status.RUNNING``
return (BT-18-011) — whether it is a core DETERMINISTIC default or an
implementer-injected backend supplied via a bundle field.

Applying the guard here, at the single point where every bundle is constructed,
means no tree-builder call site changes: a call site that does
``bundle.some_factory("NodeName")`` transparently receives a guard-wrapped node.
The demo STOCHASTIC singletons instantiate these same core bundle dataclasses,
so they are covered too.
"""

from __future__ import annotations

import dataclasses
from typing import cast

from vultron.core.behaviors.call_out.guard import guard_call_out_factory
from vultron.core.behaviors.call_out.protocol import CallOutBackendFactory


class CallOutBundle:
    """Mixin base that guards every call-out factory field (BT-18-011).

    Every concrete bundle is a ``@dataclass(frozen=True)`` whose fields are all
    :class:`~vultron.core.behaviors.call_out.protocol.CallOutBackendFactory`
    callables. ``__post_init__`` replaces each with its guarded equivalent.
    Because :func:`guard_call_out_factory` is idempotent, a factory that has
    already been guarded (e.g. one bundle's field passed into another bundle's
    constructor) is left unchanged.
    """

    def __post_init__(self) -> None:
        for f in dataclasses.fields(self):  # type: ignore[arg-type]
            value = getattr(self, f.name)
            if callable(value):
                # Frozen dataclass: bypass the assignment guard deliberately.
                object.__setattr__(
                    self,
                    f.name,
                    guard_call_out_factory(cast(CallOutBackendFactory, value)),
                )


__all__ = ["CallOutBundle"]
