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

"""The one minter of new object ids, shared by the core and wire layers.

Every new object id is minted here (OID-01-004), so every minted id has one
form: a ``urn:uuid:`` URI, a valid AS2 identifier that needs no server
configuration (OID-01-001).  It lives under ``vultron/core/models/`` because
both layers may import that package (ARCH-22-001): core models use
:func:`new_object_id` as their ``id_`` default factory, and the wire layer's
``generate_new_id`` is a thin alias of it.

An id *derived* from what an activity answers is not minted; it comes from
:func:`vultron.core.models.activity_ids.derived_activity_id`.
"""

import uuid

URN_UUID_PREFIX = "urn:uuid:"
"""The scheme and namespace every default minted id starts with."""


def new_object_id(prefix: str | None = None) -> str:
    """Return a new, unique, full-URI object id.

    By default the id is ``urn:uuid:`` followed by a fresh version-4 UUID.
    When *prefix* is given the UUID is appended to it after a ``/``, which
    yields HTTPS-style ids such as ``https://example.org/reports/{uuid}``.
    The caller owns *prefix*; it must itself be a full URI for the result to
    be one (OID-01-001).

    Args:
        prefix: An optional URI the UUID is appended to, without a trailing
            ``/``.

    Returns:
        The new id.
    """
    minted = str(uuid.uuid4())
    if prefix is None:
        return f"{URN_UUID_PREFIX}{minted}"
    return f"{prefix}/{minted}"
