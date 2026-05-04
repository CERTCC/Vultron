#!/usr/bin/env python

#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
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

"""Adapter-layer utilities for ActivityStreams object ID generation and parsing.

These utilities are used by driven adapters (e.g., TinyDB DataLayer) and
driving adapters (e.g., demo scripts) to create and inspect URL- and
URN-based object IDs.  They do not belong in the core domain layer because
they depend on the wire-format ID conventions (HTTP URLs and ``urn:uuid:``
URNs) rather than on domain concepts.
"""

import re
from typing import TypedDict
from urllib.parse import urljoin, urlparse
from uuid import uuid4

from vultron.config import get_config

BASE_URL = get_config().server.base_url

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
_URN_UUID_PREFIX = "urn:uuid:"


class ParsedObjectId(TypedDict):
    base_url: str
    object_type: str | None
    object_id: str


def id_prefix(object_type: str) -> str:
    """Returns the ID prefix for a given object type."""

    return urljoin(BASE_URL, f"{object_type}/")


def make_id(object_type: str) -> str:
    """Generates a new ID for a given object type."""
    pfx = id_prefix(object_type)
    if not pfx.endswith("/"):
        pfx += "/"

    return urljoin(pfx, f"{uuid4()}")


def parse_id(object_id: str) -> ParsedObjectId:
    """Parses an object ID into its prefix, type, and UUID components.

    Handles both HTTPS-URL form (``https://example.org/Type/uuid``) and
    ``urn:uuid:`` form (``urn:uuid:uuid``).  For ``urn:uuid:`` IDs the
    returned ``object_type`` is ``None`` and ``object_id`` is the bare UUID
    portion.
    """
    if object_id.startswith(_URN_UUID_PREFIX):
        bare_uuid = object_id[len(_URN_UUID_PREFIX) :]
        return {
            "base_url": _URN_UUID_PREFIX,
            "object_type": None,
            "object_id": bare_uuid,
        }

    # HTTPS or other URL form
    parsed_url = urlparse(object_id)

    path_parts = parsed_url.path.lstrip("/").split("/")

    # if the last part is empty (trailing slash), we can ignore it here
    if path_parts[-1] == "":
        path_parts.pop(-1)

    obj_id = path_parts.pop(-1)
    if len(path_parts) == 0:
        obj_type = None
    else:
        obj_type = path_parts.pop(-1)

    # if there is anything left in path_parts, that is part of the base url path
    base_path = "/".join(path_parts)
    base_url = (
        f"{parsed_url.scheme}://{parsed_url.netloc}/{base_path}/"
        if base_path
        else f"{parsed_url.scheme}://{parsed_url.netloc}/"
    )

    parsed: ParsedObjectId = {
        "base_url": base_url,
        "object_type": obj_type,
        "object_id": obj_id,
    }

    return parsed


def strip_id_prefix(object_id: str) -> str:
    """Strips the prefix from an object ID, returning only the UUID part."""
    try:
        parsed = parse_id(object_id)
        return parsed["object_id"]
    except ValueError:
        return object_id
