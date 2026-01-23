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
#  (“Third Party Software”). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

"""
Provides TODO writeme
"""
from urllib.parse import urljoin, urlparse
from uuid import uuid4


BASE_URL = "https://demo.vultron.local/"


def id_prefix(object_type: str) -> str:
    """Returns the ID prefix for a given object type."""

    return urljoin(BASE_URL, f"{object_type}/")


def make_id(object_type: str) -> str:
    """Generates a new ID for a given object type."""
    pfx = id_prefix(object_type)
    if not pfx.endswith("/"):
        pfx += "/"

    return urljoin(pfx, f"{uuid4()}")


def parse_id(object_id: str) -> dict[str, str]:
    """Parses an object ID into its prefix, type, and UUID components."""

    # if the object_id is a url, split it into parts:
    # after last slash is the object id
    # before that is the object type
    # and everything in front of that is the base url

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

    parsed = {
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
