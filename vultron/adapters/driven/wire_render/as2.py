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

Under one object model (ADR-0099 detail 1) a core object *is* its AS2 form:
rendering is the object's own
``model_dump(by_alias=True, exclude_none=True, mode="json")``.  The field
aliases and the JSON-LD ``@context`` both come from
:class:`~vultron.core.models.base.CoreObject`, so this adapter adds neither
and resolves no wire counterpart.

Raises :exc:`~vultron.errors.VultronValidationError` when the object is not a
``CoreObject`` — the one case with no AS2 spelling (ARCH-20-003).

This module lives under ``vultron/adapters/`` so that ``vultron/core/`` never
reaches a serialization choice on its own (ARCH-20-001, ADR-0063).

See also:
    - ``vultron/core/ports/wire_render.py`` — port Protocol
    - ``docs/adr/0063-wire-rendering-port-for-core-objects.md`` — ADR
    - ``notes/core-wire-rendering-port.md`` — design rationale

Per ``specs/architecture.yaml`` ARCH-20-001 through ARCH-20-004.
"""

from typing import Any

from vultron.core.models.base import CoreObject
from vultron.errors import VultronValidationError


class As2WireRenderAdapter:
    """Driven adapter that renders core domain objects as wire-shaped JSON.

    Implements :class:`~vultron.core.ports.wire_render.WireRenderPort`
    structurally (duck-typed via the Protocol).

    Stateless — instantiate once and reuse freely.
    """

    def render(self, obj: Any) -> dict[str, Any]:
        """Render a core domain object as wire-shaped JSON.

        Args:
            obj: A core domain model instance.

        Returns:
            ``obj.model_dump(by_alias=True, exclude_none=True, mode="json")``
            — camelCase keys plus ``@context``, ``None`` fields omitted, all
            values JSON-serializable (e.g. datetimes are ISO strings).

        Raises:
            :exc:`~vultron.errors.VultronValidationError`: When ``obj`` is not
                a :class:`~vultron.core.models.base.CoreObject` (ARCH-20-003).
        """
        # Gated on ``CoreObject``, not ``BaseModel``. ``isinstance(obj, BaseModel)``
        # asks "is this a Pydantic model", which is not the question — a core
        # record such as ``VultronOfferRecord`` is one, but carries neither the
        # alias generator nor ``@context``. Rendering it would emit
        # ``offer_id``/``report_id`` in snake_case with no context, and since
        # those keys are read back as ``offerId``/``reportId``, a record leaked
        # into a ledger snapshot would produce keys no reader finds — the
        # silent-drop failure ``wire_keys`` documents as "worse than failing".
        #
        # ``CoreObject`` is the type that guarantees AS2-representability, because
        # the generator and the ``@context`` serializer both live on it, and
        # ``test_promoted_core_classes_are_exactly_as2_representable`` holds every
        # subclass to it. So the port fails closed as ARCH-20-003 (MUST) requires.
        if not isinstance(obj, CoreObject):
            raise VultronValidationError(
                f"{type(obj).__name__!r} is not a CoreObject, so it has no AS2"
                " spelling for its fields. Rendering it would emit Python field"
                " names and omit @context (ARCH-20-003, VM-10-001)."
            )
        return obj.model_dump(by_alias=True, exclude_none=True, mode="json")
