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

"""The AS2 natural-language map, shared by both object roots (ARCH-25-008).

AS2 Core section 4.7 lets ``content``, ``name`` and ``summary`` arrive in a
map form, ``contentMap``, ``nameMap`` and ``summaryMap``: each a JSON object
from a language tag to the text in that language.  ``CoreObject`` and the wire
``as_Object`` declare all three with :func:`language_map_field`, so the parse
edge reads them instead of setting them aside (MV-11-001).
"""

from typing import Annotated, Any, TypeAlias

from pydantic import BeforeValidator, Field

from vultron.core.models._helpers import is_empty
from vultron.primitives import NonEmptyString


def absent_as_empty(value: object) -> object:
    """Read a ``null`` language map as an absent one, which is empty.

    A ``null`` value means the same as no value (VM-07-001), and every other
    AS2 property on the object roots admits ``null``, so a peer that writes
    ``"contentMap": null`` is read, not refused.  Only ``None`` is rewritten:
    a blank tag or text, or a value that is not an object, is still refused
    (CS-08-001, ARCH-25-024).
    """
    return {} if value is None else value


LanguageMap: TypeAlias = Annotated[
    dict[NonEmptyString, NonEmptyString], BeforeValidator(absent_as_empty)
]
"""A language tag mapped to the text in that language (AS2 Core section 4.7).

Both sides are "if present, then non-empty" (CS-08-001): a blank tag names no
language and a blank value is no text, so either refuses the object.  A
``null`` map is read as empty (:func:`absent_as_empty`).
"""


def language_map_field() -> Any:
    """Declare a :data:`LanguageMap` field: empty by default, omitted when empty.

    An empty map is a key the sender never sent, so a dump omits it, as
    ``CoreActor.assertion_method`` omits an empty key list.  Reading a dump
    without the key gives the empty default back, so it round-trips.
    """
    return Field(default_factory=dict, exclude_if=is_empty)


__all__ = ["LanguageMap", "absent_as_empty", "language_map_field"]
