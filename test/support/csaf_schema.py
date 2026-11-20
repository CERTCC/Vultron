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
"""A validator of the pinned CSAF 2.1 schema, for tests (CSAF-05-001).

Every schema the pinned root references is read from the pinned local copy,
so a test checks a document against the schema the repository pins, offline.
"""

import json
from functools import cache
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry
from referencing.jsonschema import DRAFT202012

from vultron.metadata.csaf.pin import PINNED_COPY_DIR, load_pin


@cache
def csaf_schema_validator() -> Draft202012Validator:
    """A validator of the pinned CSAF 2.1 schema, reading every schema it
    references from the pinned local copy."""
    pin = load_pin()
    # Every schema of the copy is read as draft 2020-12, the dialect the
    # CSAF meta-schema extends.
    resources = [
        (
            url,
            DRAFT202012.create_resource(
                json.loads((PINNED_COPY_DIR / path).read_bytes())
            ),
        )
        for url, path in pin.sources.items()
    ]
    registry: Registry[Any] = Registry().with_resources(resources)
    root = json.loads((PINNED_COPY_DIR / pin.root).read_bytes())
    return Draft202012Validator(
        root, registry=registry, format_checker=FormatChecker()
    )


def schema_errors(document: object) -> list[str]:
    """The message of each way *document* fails the pinned schema."""
    return [e.message for e in csaf_schema_validator().iter_errors(document)]


__all__ = ["csaf_schema_validator", "schema_errors"]
