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

"""AS2 adapter implementing
:class:`~vultron.core.ports.wire_render.WireRenderPort`.

Translates a core domain object to its wire-layer counterpart via:

1. Vocabulary lookup — ``WIRE_TYPE_MAP.get(type(obj).__name__)``
2. Wire-counterpart guard — ``issubclass(wire_cls, VultronAS2Object)``
3. ``wire_cls.from_core(obj)``
4. ``model_dump(by_alias=True, exclude_none=True, mode="json")``

Raises :exc:`~vultron.errors.VultronValidationError` when the core type
has no wire counterpart or the counterpart does not extend
:class:`~vultron.wire.as2.vocab.objects.base.VultronAS2Object`
(ARCH-20-003).

This module lives under ``vultron/adapters/`` so that ``vultron/core/``
never imports from the wire layer (ARCH-01-001, ARCH-01-004).

See also:
    - ``vultron/core/ports/wire_render.py`` — port Protocol
    - ``docs/adr/0063-wire-rendering-port-for-core-objects.md`` — ADR
    - ``notes/core-wire-rendering-port.md`` — design rationale

Per ``specs/architecture.yaml`` ARCH-20-001 through ARCH-20-004.
"""

from typing import Any

from vultron.errors import VultronValidationError
from vultron.wire.as2.vocab.base.registry import WIRE_TYPE_MAP
from vultron.wire.as2.vocab.objects.base import VultronAS2Object


class As2WireRenderAdapter:
    """Driven adapter that renders core domain objects as wire-shaped JSON.

    Implements :class:`~vultron.core.ports.wire_render.WireRenderPort`
    structurally (duck-typed via the Protocol).

    Stateless — instantiate once and reuse freely.
    """

    def render(self, obj: Any) -> dict[str, Any]:
        """Render a core domain object as wire-shaped JSON.

        Looks up the wire counterpart in ``WIRE_TYPE_MAP`` by
        ``type(obj).__name__``, verifies it is a
        :class:`~vultron.wire.as2.vocab.objects.base.VultronAS2Object`
        (the only class with ``from_core()``), then returns the camelCase
        dict.

        Args:
            obj: A core domain model instance.

        Returns:
            ``wire_cls.from_core(obj).model_dump(by_alias=True,
            exclude_none=True, mode="json")`` — camelCase keys, ``None``
            fields omitted, all values JSON-serializable (e.g. datetimes
            are ISO strings).

        Raises:
            :exc:`~vultron.errors.VultronValidationError`: When ``obj``'s
                type is not in the wire vocabulary or the wire counterpart
                does not extend ``VultronAS2Object`` (ARCH-20-003).
        """
        type_name = type(obj).__name__
        wire_cls = WIRE_TYPE_MAP.get(type_name)

        if wire_cls is None or not issubclass(wire_cls, VultronAS2Object):
            raise VultronValidationError(
                f"No wire counterpart for core type {type_name!r}."
            )

        return wire_cls.from_core(obj).model_dump(
            by_alias=True, exclude_none=True, mode="json"
        )
