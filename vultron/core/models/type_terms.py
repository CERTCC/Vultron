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

"""The type names a received body's ``type`` value carries, for core readers.

A received body is kept verbatim (VM-08-002), and the case ledger records it
as the entry's ``payloadSnapshot``, so a body whose ``type`` is an AS2 list
(``["Foo", "Join"]``) reaches core readers as a list (ADR-0196).  Core cannot
ask the wire vocabulary which term is most specific (ARCH-01-001); the parse
edge already refused a list it cannot resolve (VM-03-006).  A core reader
therefore asks whether the body *names* a given type: membership in
:func:`type_terms`, never equality with the raw value.  The module sits in
``core/models`` so the wire edge reads a list's terms by the same rule
(ARCH-22-001).
"""

from collections.abc import Collection, Mapping
from typing import Any


def type_terms(value: object) -> tuple[str, ...]:
    """The non-blank type names *value* carries, in order.

    A string is one term, a list contributes its string items, and anything
    else carries none.
    """
    items = [value] if isinstance(value, str) else value
    if not isinstance(items, list):
        return ()
    return tuple(t for t in items if isinstance(t, str) and t.strip())


def body_type_terms(body: Mapping[str, Any]) -> tuple[str, ...]:
    """The type names a body dict carries under ``type`` (or ``type_``)."""
    return type_terms(body.get("type") or body.get("type_"))


def names_type(value: object, names: Collection[str]) -> bool:
    """Whether *value*, a ``type`` value, names any type in *names*."""
    return any(term in names for term in type_terms(value))


def first_named(value: object, names: Collection[str]) -> str | None:
    """The first term of *value* that is in *names*, or ``None``."""
    return next((t for t in type_terms(value) if t in names), None)
