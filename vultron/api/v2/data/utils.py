#!/usr/bin/env python

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

"""
Provides TODO writeme
"""
from urllib.parse import urljoin
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
    if not object_id.startswith(BASE_URL):
        raise ValueError("Invalid object ID format")

    relative_id = object_id[len(BASE_URL) :]
    parts = relative_id.split("/")

    if len(parts) != 2:
        raise ValueError("Invalid object ID format")

    parsed = {
        "base_url": BASE_URL,
        "object_type": parts[0],
        "object_id": parts[1],
    }

    return parsed
