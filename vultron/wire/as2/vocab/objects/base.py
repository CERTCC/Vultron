#!/usr/bin/env python
"""
Provides a base class for all Vultron ActivityStreams Objects.
"""

#  Copyright (c) 2023-2025 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  (“Third Party Software”). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

from typing import Any, ClassVar, TypeAlias

from vultron.wire.as2.vocab.base.enums import VocabNamespace
from vultron.wire.as2.vocab.base.links import ActivityStreamRef
from vultron.wire.as2.vocab.base.objects.base import as_Object


class VultronAS2Object(as_Object):
    """Base class for all Vultron ActivityStreams Objects.

    Subclasses represent specific Vultron wire-format object types and MUST
    implement :meth:`from_core` (and SHOULD implement :meth:`to_core`) with
    a narrowed type signature, e.g.::

        @classmethod
        def from_core(cls, core_obj: VultronReport) -> "VulnerabilityReport":
            ...

    **``_field_map`` contract**: If a subclass wire type uses different field
    names than the corresponding core domain type, declare the mapping as::

        _field_map: ClassVar[dict[str, str]] = {"domain_field": "wire_field"}

    The default :meth:`from_core` implementation applies ``_field_map``
    renames before calling :func:`~pydantic.BaseModel.model_validate`, so
    subclasses with no name differences can inherit the default without
    override.

    ``to_core`` always raises :exc:`NotImplementedError` at this level;
    subclasses that have a meaningful reverse mapping SHOULD override it.
    """

    _vocab_ns: ClassVar[VocabNamespace] = VocabNamespace.VULTRON
    _field_map: ClassVar[dict[str, str]] = {}

    @classmethod
    def from_core(cls, core_obj: Any) -> "VultronAS2Object":
        """Create a wire object from a core domain object.

        The default implementation performs a JSON round-trip::

            data = core_obj.model_dump(mode="json")
            # apply _field_map renames (domain key → wire key)
            cls.model_validate(data)

        Subclasses MUST narrow the ``core_obj`` parameter type.  Override
        this method when simple field-rename mapping via ``_field_map`` is
        insufficient.

        Args:
            core_obj: A core domain model instance (Pydantic ``BaseModel``
                subclass).

        Returns:
            A new instance of this wire type populated from ``core_obj``.
        """
        data: dict[str, Any] = core_obj.model_dump(mode="json")
        for domain_field, wire_field in cls._field_map.items():
            if domain_field in data:
                data[wire_field] = data.pop(domain_field)
        return cls.model_validate(data)

    def to_core(self) -> Any:
        """Convert this wire object to a core domain object.

        Subclasses that have a well-defined reverse mapping SHOULD override
        this method and return the appropriate core domain type.

        The ``_field_map`` contract is the inverse of :meth:`from_core`:
        wire field names map to domain field names.  Subclass overrides
        should apply the reverse mapping before calling
        ``CoreType.model_validate(data)``.

        Raises:
            NotImplementedError: Always — no generic reverse mapping exists
                at the wire base level.
        """
        raise NotImplementedError(
            f"{type(self).__name__}.to_core() is not implemented. "
            "Override this method in the subclass."
        )


VultronObjectRef: TypeAlias = ActivityStreamRef[VultronAS2Object]
