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

from typing import List, TypeAlias

from pydantic import Field

from vultron.as_vocab.base.links import ActivityStreamRef
from vultron.as_vocab.base.objects.base import as_Object, as_ObjectRef
from vultron.as_vocab.base.registry import activitystreams_object


@activitystreams_object
class as_Collection(as_Object):
    """A collection is a list of objects. The items in the list MAY be ordered.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-collection>
    """

    items: List[as_ObjectRef | None] = Field(default_factory=list)
    current: int | None = 0

    # TODO implement a way to ignore duplicates
    # _ids: Set[as_Object] = field(default_factory=set, repr=False)
    # _duplicates: bool = field(default=False, repr=False)

    @property
    def first(self):
        return self.items[0]

    @property
    def last(self):
        return self.items[-1]

    @property
    def totalItems(self):
        return len(self.items)

    def append(self, item: as_ObjectRef):
        # if not self._duplicates and item.as_id not in self._ids:
        self.items.append(item)
        # self._ids.add(item.as_id)


as_CollectionRef: TypeAlias = ActivityStreamRef[as_Collection]


@activitystreams_object
class as_OrderedCollection(as_Collection):
    """A collection that has its items explicitly ordered. The items in the list are assumed to always be in the same order.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-orderedcollection>
    """


as_OrderedCollectionRef: TypeAlias = ActivityStreamRef[as_OrderedCollection]


@activitystreams_object
class as_CollectionPage(as_Collection):
    """A subset of items from a Collection.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-collectionpage>
    """

    prev: as_Collection | None = None
    next: as_Collection | None = None
    part_of: as_Collection | None = None


as_CollectionPageRef: TypeAlias = ActivityStreamRef[as_CollectionPage]


@activitystreams_object
class as_OrderedCollectionPage(as_OrderedCollection, as_CollectionPage):
    """A subset of items from an OrderedCollection.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-orderedcollectionpage>
    """

    start_index: as_CollectionPage | None = None


asOrderedCollectionPageRef: TypeAlias = ActivityStreamRef[
    as_OrderedCollectionPage
]


def main():
    from vultron.as_vocab.base.utils import print_object_examples

    print_object_examples()


if __name__ == "__main__":
    main()
