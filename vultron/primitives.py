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
by both ``vultron/core/`` and ``vultron/wire/``.  They live here so that
wire-layer modules can import them without creating ``vultron.core.models``
imports (ARCH-22-001).

This module MUST NOT import from ``vultron.core``, ``vultron.config``,
``vultron.wire``, or ``vultron.adapters``.
"""

import re
from typing import Annotated

from pydantic import AfterValidator


def _non_empty(v: str) -> str:
    if not v.strip():
        raise ValueError("must be a non-empty string")
    return v


NonEmptyString = Annotated[str, AfterValidator(_non_empty)]

_URI_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+\-.]*:[^\s]")


def _valid_uri(v: str) -> str:
    if not _URI_SCHEME_RE.match(v):
        raise ValueError("must be a URI (e.g. urn:uuid:... or https://...)")
    return v


UriString = Annotated[NonEmptyString, AfterValidator(_valid_uri)]

__all__ = ["NonEmptyString", "UriString"]
