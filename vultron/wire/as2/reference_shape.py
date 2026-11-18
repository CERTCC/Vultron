#!/usr/bin/env python
"""The shape of a typed reference: an ``id``, a ``type``, nothing more.

ADR-0198: the keys of a received inline object alone tell a typed reference
from a whole object (MV-10-011).  The predicate lives here, below the
vocabulary, so the vocabulary's own inbound validator can ask it
(CLP-15-011: a typed reference carries no time).  Every other reader takes
it from :mod:`vultron.wire.as2.typed_reference`, which re-exports it and
holds the rest of the reference's rules.
"""

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

from collections.abc import Mapping
from typing import Any

#: The keys a typed reference may carry: its ``id`` and ``type``, the JSON-LD
#: ``@context`` any object may cite, and an AS2 ``preview`` (MV-10-011).
TYPED_REFERENCE_KEYS: frozenset[str] = frozenset(
    {"@context", "id", "type", "preview"}
)


def is_typed_reference_shape(value: Mapping[str, Any]) -> bool:
    """Whether the received *value* is a typed reference (MV-10-011).

    An ``id``, a ``type``, and no other key but ``@context`` and ``preview``.
    The shape alone decides, whatever the type: a mapping with any other key
    is a whole object, which its class judges (ADR-0198).
    """
    return (
        "id" in value
        and "type" in value
        and set(value) <= TYPED_REFERENCE_KEYS
    )


__all__ = ["TYPED_REFERENCE_KEYS", "is_typed_reference_shape"]
