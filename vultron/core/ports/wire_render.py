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

"""Driven port for rendering core domain objects as wire-shaped JSON.

Core code that needs wire-shaped (AS2 camelCase) JSON for a domain
object calls this port.  The adapter translates the core object to its
wire counterpart and returns the result of
``model_dump(by_alias=True, exclude_none=True)``.

Raises :exc:`~vultron.errors.VultronValidationError` when no wire
counterpart exists (ARCH-20-003).

See also:
    - ``vultron/adapters/driven/wire_render/as2.py`` — adapter
    - ``docs/adr/0063-wire-rendering-port-for-core-objects.md`` — ADR
    - ``notes/core-wire-rendering-port.md`` — design rationale

Per ``specs/architecture.yaml`` ARCH-20-001 through ARCH-20-004.
"""

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class WireRenderPort(Protocol):
    """Driven port for rendering core domain objects as wire-shaped JSON.

    A single-method port (matching the ``SyncActivityPort`` /
    ``ActivityEmitter`` style).  The adapter is the sole owner of
    wire-spelling knowledge; core code calls this port without importing
    from the wire layer (ARCH-01-001, ARCH-20-001).

    Per ``specs/architecture.yaml`` ARCH-20-001 through ARCH-20-004.
    """

    def render(self, obj: Any) -> dict[str, Any]:
        """Render a core domain object as wire-shaped JSON.

        Args:
            obj: A core domain model instance.

        Returns:
            A ``dict`` equivalent to
            ``as_X.from_core(obj).model_dump(by_alias=True, exclude_none=True)``
            — camelCase keys, ``None`` fields omitted.

        Raises:
            :exc:`~vultron.errors.VultronValidationError`: When ``obj``'s
                core type has no wire counterpart registered in the wire
                vocabulary, or when the wire counterpart does not implement
                ``from_core()`` (ARCH-20-003).
        """
        ...
