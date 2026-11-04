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

"""The one object id minter (OID-01-004) and the id reader for mixed references."""

import uuid
from collections.abc import Mapping
from typing import (
    Any,
)

URN_UUID_PREFIX = "urn:uuid:"
"""The scheme and namespace every default minted object id starts with."""


def new_object_id(prefix: str | None = None) -> str:
    """Return a new, unique, full-URI object id: the one id minter (OID-01-004).

    Core models use it as their ``id_`` default factory, and the wire layer's
    ``generate_new_id`` is the same function, so every minted id has one form
    whichever layer mints it.  By default the id is ``urn:uuid:`` followed by
    a fresh version-4 UUID, a valid AS2 identifier that needs no server
    configuration (OID-01-001).  When *prefix* is given the UUID is appended
    to it after a ``/``, which yields HTTPS-style ids such as
    ``https://example.org/reports/{uuid}``; the caller owns *prefix*, which
    must itself be a full URI for the result to be one.

    An id *derived* from what an activity answers is not minted; it comes from
    :func:`vultron.core.models.activity_ids.derived_activity_id`.
    """
    minted = str(uuid.uuid4())
    if prefix is None:
        return f"{URN_UUID_PREFIX}{minted}"
    return f"{prefix}/{minted}"


def _as_id(obj: Any) -> str | None:
    """Return the ActivityStreams id of *obj* as a plain string.

    - If *obj* is ``None``, returns ``None``.
    - If *obj* has an ``id_`` attribute, returns ``obj.id_``.
    - If *obj* is a mapping (an inline object as stored, or as a received
      activity's read-only view hands it out), returns its ``id_`` or ``id``
      string, so an inline case is named by its URI rather than by the
      ``str()`` of the whole mapping.
    - Otherwise returns ``str(obj)``.

    This handles the mixed ``str | <wire-type>`` collections that arise when
    the DataLayer stores plain string IDs alongside rehydrated objects.
    """
    if obj is None:
        return None
    id_ = obj.get("id_") or obj.get("id") if isinstance(obj, Mapping) else None
    id_ = id_ or getattr(obj, "id_", None)
    if isinstance(id_, str):
        return id_
    return str(obj)
