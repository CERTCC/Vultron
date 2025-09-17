#!/usr/bin/env python
"""This module provides
# TODO replace me
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

from dataclasses import dataclass, field
from typing import List, Optional

from dataclasses_json import LetterCase, dataclass_json

from vultron.as_vocab.base import activitystreams_object
from vultron.as_vocab.base.objects.base import as_Object


@activitystreams_object
@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class as_Collection(as_Object):
    """A collection is a list of objects. The items in the list MAY be ordered.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-collection>
    """

    items: Optional[List[as_Object]] = field(default_factory=list, repr=True)
    current: Optional[int] = field(default=0, repr=True)

    # # implement a way to ignore duplicates
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

    def append(self, item: as_Object):
        if not self._duplicates and not item.as_id in self._ids:
            self.items.append(item)
            self._ids.add(item.as_id)


@activitystreams_object
@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class as_OrderedCollection(as_Collection):
    """A collection that has its items explicitly ordered. The items in the list are assumed to always be in the same order.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-orderedcollection>
    """


@activitystreams_object
@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class as_CollectionPage(as_Collection):
    """A subset of items from a Collection.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-collectionpage>
    """

    prev: Optional[as_Collection] = None
    next: Optional[as_Collection] = None
    partOf: Optional[as_Collection] = None
    startIndex = None


@activitystreams_object
@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class as_OrderedCollectionPage(as_OrderedCollection, as_CollectionPage):
    """A subset of items from an OrderedCollection.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-orderedcollectionpage>
    """


def main():
    from vultron.as_vocab.base.utils import print_object_examples

    print_object_examples()


if __name__ == "__main__":
    main()
