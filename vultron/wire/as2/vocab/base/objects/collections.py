#!/usr/bin/env python
"""This module provides activitystreams collection objects"""

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

from typing import List, Literal, Set, TypeAlias

from pydantic import Field, PrivateAttr, model_validator

from vultron.wire.as2.vocab.base.links import ActivityStreamRef
from vultron.wire.as2.vocab.base.objects.base import as_Object, as_ObjectRef


class as_Collection(as_Object):
    """A collection is a list of objects. The items in the list MAY be ordered.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-collection>

    Vultron uses collections only as an actor's ``inbox``/``outbox`` endpoint
    (ActivityPub publishes them as addresses), so the AS2 paging properties
    (``current``, ``first``, ``last``, ``CollectionPage``) are not modelled.
    """

    #: Narrowed so the class registers under the ``type`` it presents
    #: (VM-03-002); without it ``set_type_from_class_name`` still emits
    #: ``"Collection"`` but nothing registers, and a wire lookup falls through
    #: to the core map (ISSUE-3242).
    type_: Literal["Collection"] = Field(
        default="Collection",
        validation_alias="type",
        serialization_alias="type",
    )
    items: List[as_ObjectRef | None] = Field(default_factory=list)

    _ids: Set[str] = PrivateAttr(
        default_factory=set
    )  # tracks id_ URIs for duplicate detection

    @model_validator(mode="after")
    def _populate_ids(self) -> "as_Collection":
        for item in self.items:
            if item is None or isinstance(item, str):
                continue
            item_id = getattr(item, "id_", None)
            if item_id:
                self._ids.add(str(item_id))
        return self

    @property
    def totalItems(self):
        return len(self.items)

    def append(self, item: as_ObjectRef) -> None:
        if not isinstance(item, str):
            raw_id = getattr(item, "id_", None)
            item_id = str(raw_id) if raw_id else ""
            if item_id and item_id in self._ids:
                return
        else:
            item_id = ""
        self.items.append(item)
        if item_id:
            self._ids.add(item_id)


as_CollectionRef: TypeAlias = ActivityStreamRef[as_Collection]


class as_OrderedCollection(as_Collection):
    """A collection that has its items explicitly ordered. The items in the list are assumed to always be in the same order.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-orderedcollection>
    """

    # Narrowing a parent's Literal to a disjoint one is how a subclass presents
    # its own `type` (VM-03-002); mypy reads it as an incompatible override.
    type_: Literal["OrderedCollection"] = Field(  # type: ignore[assignment]
        default="OrderedCollection",
        validation_alias="type",
        serialization_alias="type",
    )


as_OrderedCollectionRef: TypeAlias = ActivityStreamRef[as_OrderedCollection]


def main():
    from vultron.wire.as2.vocab.base.utils import print_object_examples

    print_object_examples()


if __name__ == "__main__":
    main()
