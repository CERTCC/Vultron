#!/usr/bin/env python
"""
Provides classes representing ActivityStreams Vocabulary Link objects.
"""

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

from typing import ClassVar, Literal, TypeAlias, TypeVar

from pydantic import Field

from vultron.primitives import NonEmptyString
from vultron.wire.as2.vocab.base.base import as_Base
from vultron.wire.as2.vocab.base.utils import generate_new_id


class as_Link(as_Base):
    """A Link is an indirect, qualified reference to a resource identified by a URL.
    The fundamental model for links is established by [RFC5988].
    Many of the properties defined by the Activity Vocabulary allow values that are either instances of Object or a Link.
    When a Link is used, it establishes a qualified relation connecting the subject to the resource identified by the href property.
    Properties of the Link are properties of the reference as opposed to properties of the resource.
    Links are disjoint from the Object type.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-link>
    """

    #: Narrowed so the class registers under the ``type`` it presents
    #: (VM-03-002).
    type_: Literal["Link"] = Field(
        default="Link",
        validation_alias="type",
        serialization_alias="type",
    )
    #: A Link is not an Object, and AS2 gives it no id of its own.  One this
    #: process builds still takes a minted id; a received one that omits it
    #: keeps none (OID-01-013).
    _inbound_requires_id: ClassVar[bool] = False
    id_: NonEmptyString | None = Field(  # type: ignore[assignment]  # pyright: ignore[reportIncompatibleVariableOverride]
        default_factory=generate_new_id,
        validation_alias="id",
        serialization_alias="id",
    )
    width: int | None = None
    height: int | None = None
    #: AS2 ``rel`` is not functional: one relation type as a string, or
    #: several as an array (VOC ``rel``).
    rel: NonEmptyString | list[NonEmptyString] | None = None
    #: A Link names its resource by ``href`` (AS2 § 3.2): one without points
    #: nowhere, and one with a blank ``href`` points nowhere too (CS-08-001).
    #: Required whether received or built here, so an untyped dict in an
    #: object-or-link slot that fails its object class is refused rather than
    #: read as an empty Link (MV-04-005).
    href: NonEmptyString
    hreflang: NonEmptyString | None = None


class as_Mention(as_Link):
    """A specialized Link that represents an @mention (AS2 Vocabulary 3.2).

    A Link subtype, so a received one keeps its ``href`` and needs no ``id``.
    See definition in ActivityStreams Vocabulary
    <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-mention>
    """

    type_: Literal["Mention"] = Field(  # type: ignore[assignment]  # pyright: ignore[reportIncompatibleVariableOverride]
        default="Mention",
        validation_alias="type",
        serialization_alias="type",
    )


T_co = TypeVar("T_co", covariant=True)

# The IRI branch of every reference union is ``NonEmptyString`` (CS-08-001,
# CS-08-002): a blank string names no resource, so it is refused inbound rather
# than carried into the core and echoed on the way out.  Code that introspects
# these unions for their string branch must unwrap the ``Annotated``
# (``vultron.core.models._helpers.strip_annotated``) instead of testing
# ``is str``.

# an ActivityStreamRequiredRef is an object of type T_co, a Link, or a non-empty
# string (IRI)
ActivityStreamRequiredRef: TypeAlias = T_co | as_Link | NonEmptyString

# an ActivityStreamRef can be an object of type T_co, a Link, a non-empty string
# (IRI), or None (for optional fields)
ActivityStreamRef: TypeAlias = T_co | as_Link | NonEmptyString | None


def main():
    x = as_Link(href="https://example.org/")
    print(x.to_dict())
    print(x.to_json(indent=2))


if __name__ == "__main__":
    main()
