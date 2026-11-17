#!/usr/bin/env python

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

"""The AS2 collection types on the wire.

Core owns them (ADR-0208): ``as_Collection`` and ``as_OrderedCollection``
are aliases of the core classes, as ADR-0099 made the domain types, and the
wire registers them under the ``type`` values a received body names.
"""

from typing import TypeAlias

from vultron.core.models.collection import Collection, OrderedCollection
from vultron.wire.as2.vocab.base.links import ActivityStreamRef
from vultron.wire.as2.vocab.base.registry import WIRE_TYPE_MAP
from vultron.wire.as2.vocab.base.utils import print_object_examples

#: Vultron uses collections only as an actor's ``inbox``/``outbox`` endpoint
#: (ActivityPub publishes them as addresses), so the AS2 paging properties
#: (``current``, ``first``, ``last``, ``CollectionPage``) are not modelled.
as_Collection = Collection
as_OrderedCollection = OrderedCollection

# Registered in WIRE_TYPE_MAP by hand, as an aliased core class is
# (ADR-0099), so the parser admits each inline by its ``type``.
WIRE_TYPE_MAP["Collection"] = Collection
WIRE_TYPE_MAP["OrderedCollection"] = OrderedCollection

as_CollectionRef: TypeAlias = ActivityStreamRef[as_Collection]
as_OrderedCollectionRef: TypeAlias = ActivityStreamRef[as_OrderedCollection]


def main():
    print_object_examples()


if __name__ == "__main__":
    main()
