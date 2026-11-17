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

"""The AS2 ``Collection`` and ``OrderedCollection`` as core holds them.

Core owns the AS2 base vocabulary (ADR-0208): these are the Activity
Vocabulary's collection types, with ``items`` and nothing Vultron adds, so a
generic core slot knows a received collection by its class, and the wire's
collection classes build on these.
"""

from typing import ClassVar, Literal

from pydantic import Field, PrivateAttr, model_validator

from vultron.core.models.as2_base import as2_base_class
from vultron.core.models.base import CoreObject
from vultron.core.models.base.core_object import CoreObjectOrIri


@as2_base_class
class Collection(CoreObject):
    """An AS2 ``Collection``: a list of objects or links, maybe ordered."""

    #: A collection is a container, not an act made at a moment
    #: (CLP-15-011).
    _received_without_published: ClassVar[bool] = True

    type_: Literal["Collection"] = Field(
        default="Collection",
        validation_alias="type",
        serialization_alias="type",
    )
    items: list[CoreObjectOrIri | None] = Field(default_factory=list)

    #: The ids of the items held, so :meth:`append` adds each object once.
    _ids: set[str] = PrivateAttr(default_factory=set)

    @model_validator(mode="after")
    def _populate_ids(self) -> Collection:
        for item in self.items:
            if item is None or isinstance(item, str):
                continue
            item_id = getattr(item, "id_", None)
            if item_id:
                self._ids.add(str(item_id))
        return self

    @property
    def totalItems(self) -> int:
        """How many items the collection holds (AS2 ``totalItems``)."""
        return len(self.items)

    def append(self, item: CoreObjectOrIri) -> None:
        """Add *item*, unless an object with its id is already held."""
        item_id = ""
        if not isinstance(item, str):
            raw_id = getattr(item, "id_", None)
            item_id = str(raw_id) if raw_id else ""
            if item_id and item_id in self._ids:
                return
        self.items.append(item)
        if item_id:
            self._ids.add(item_id)


@as2_base_class
class OrderedCollection(Collection):
    """An AS2 ``OrderedCollection``: a collection whose items keep an order."""

    # Narrowing a parent's Literal to a disjoint one is how a subclass
    # presents its own `type` (VM-03-002); mypy reads it as an incompatible
    # override.
    type_: Literal["OrderedCollection"] = Field(  # type: ignore[assignment]
        default="OrderedCollection",
        validation_alias="type",
        serialization_alias="type",
    )


__all__ = ["Collection", "OrderedCollection"]
