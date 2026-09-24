#!/usr/bin/env python
"""This module provides base activity classes"""

#  Copyright (c) 2025 Carnegie Mellon University and Contributors.
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

from pydantic import Field

from vultron.core.models.actor import CoreActor
from vultron.core.models.base import CoreObject
from vultron.wire.as2.vocab.base.links import as_Link
from vultron.wire.as2.vocab.base.objects.actors import as_ActorRef
from vultron.wire.as2.vocab.base.objects.base import as_Object
from vultron.wire.as2.enums import as_ObjectType as O_type


class as_Activity(as_Object):
    """https://www.w3.org/TR/activitystreams-vocabulary/#dfn-activity
    An Activity is a subtype of Object that describes some form of action that may happen, is
    currently happening, or has already happened. The Activity type itself serves as an abstract
    base type for all types of activities. It is important to note that an Activity is not a
    representation of a currently executing process, but rather a statement about that process.
    For example, a person walking down the street is not an Activity unless they are posting a
    picture of themselves walking down the street. The Activity in that case would be the posting
    of the picture, not the person walking down the street.
    """

    type_: str = Field(
        default=O_type.ACTIVITY,
        validation_alias="type",
        serialization_alias="type",
    )

    # All four slots admit a core object, not just ``actor``.
    #
    # Widening only ``actor`` (and ``as_ObjectRef``, for ``object_``) left
    # ``target``/``origin``/``instrument`` declaring a wire-only union while the
    # adapters put promoted core classes in them.  A value outside its declared
    # union escapes in both directions: outbound, Pydantic emits
    # ``PydanticSerializationUnexpectedValue`` and ships a payload shaped by the
    # wrong schema; inbound, a payload from an unmodified peer is refused. That is
    # what made every recipient answer ``422`` to ``Create(VulnerabilityCase)`` and
    # never seed the case replica (ADR-0041, PCR-01-003).
    #
    # The type errors this produced on the subclass overrides were suppressed with
    # ``# type: ignore[assignment]`` rather than fixed, which is why mypy and
    # pyright stayed green while the wire protocol did not work. Widening here is
    # what lets those suppressions be deleted: a subclass narrowing
    # ``target`` to ``VulnerabilityCase | as_Link | str | None`` is now a genuine
    # narrowing of this union rather than an incompatible override.
    actor: as_ActorRef | CoreActor
    target: as_Object | as_Link | str | CoreObject | None = None
    origin: as_Object | as_Link | str | CoreObject | None = None
    instrument: as_Object | as_Link | str | CoreObject | None = None
    result: as_Object | as_Link | str | None = None

    def description(self):
        raise NotImplementedError


def main():
    x = as_Activity(actor="https://example.org/actor")
    print(x.to_json(indent=2))


if __name__ == "__main__":
    main()
