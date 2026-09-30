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

"""Branch-neutral string primitive types for Vultron.

``NonEmptyString`` and ``UriString`` are Pydantic annotated type aliases used
by both ``vultron/core/`` and ``vultron/wire/``.  They live here because they
are not domain models: they are shared string primitives, and a module that both
branches need belongs below both.

Note the original reason has expired. They were relocated to avoid creating
``vultron.core.models`` imports from wire, which ARCH-22-001 then forbade; that
prohibition is repealed by ADR-0099 and wire may now name core model types
directly. The relocation still stands on the reason above.

This module MUST NOT import from ``vultron.core``, ``vultron.config``,
``vultron.wire``, or ``vultron.adapters``.
"""

import re
from typing import Annotated

from pydantic import AfterValidator

_BLANK_MESSAGE = "must be a non-empty string"


def is_blank_string(value: str) -> bool:
    """True when *value* is empty or whitespace-only.

    The project's one predicate for "blank" (CS-08-001, "if present, then
    non-empty"): ``NonEmptyString``, :func:`require_non_empty` and the wire
    layer's ``is_blank`` all decide through it, so a guard that catches ``""``
    cannot miss ``"   "`` one character over.
    """
    return not value.strip()


def _non_empty(v: str) -> str:
    if is_blank_string(v):
        raise ValueError(_BLANK_MESSAGE)
    return v


NonEmptyString = Annotated[str, AfterValidator(_non_empty)]


def require_non_empty(value: str, field_name: str) -> str:
    """Return *value* if it is non-blank, else raise ``ValueError`` naming the field.

    The plain-function form of ``NonEmptyString`` for the few core records that
    are stdlib dataclasses rather than Pydantic models (CS-08-001 reaches them
    too, but an ``Annotated`` validator does not).  Call it from
    ``__post_init__``.
    """
    if is_blank_string(value):
        raise ValueError(f"{field_name} {_BLANK_MESSAGE}")
    return value


_URI_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+\-.]*:[^\s]")


def _valid_uri(v: str) -> str:
    if not _URI_SCHEME_RE.match(v):
        raise ValueError("must be a URI (e.g. urn:uuid:... or https://...)")
    return v


UriString = Annotated[NonEmptyString, AfterValidator(_valid_uri)]

__all__ = [
    "NonEmptyString",
    "UriString",
    "is_blank_string",
    "require_non_empty",
]
