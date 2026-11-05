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

"""The one check a received body's text must pass in core (VM-08-002).

The parser seals the decoded body of an activity, which is always a JSON
object, as JSON text.  Every core model that carries that text (the event's
received evidence, the receiver's archive of it) refuses anything else with
:func:`require_json_object_text`, from a field validator.

:func:`received_body_digest` is the one definition of a sealed body's
fingerprint, used both where two deliveries under one id are compared
(IE-10-002) and where a refused message's body is given up for a receipt
stub that keeps only the fingerprint (ADR-0154).  Two callers of one
function, so a stub's hash and a delivery's digest are the same value and
can be compared without either side re-deriving it (CS-22-001).
"""

import hashlib
import json


def require_json_object_text(value: str, field: str) -> str:
    """Return *value* when it is the text of one JSON object.

    For a Pydantic field validator: a ``ValueError`` is what Pydantic reports
    as a validation error, where a ``TypeError`` would escape validation.

    Raises:
        ValueError: When *value* is not JSON text, or not that of an object.
    """
    try:
        decoded = json.loads(value)
    except ValueError as exc:
        raise ValueError(f"{field} is not JSON text (VM-08-002)") from exc
    if not isinstance(decoded, dict):
        raise ValueError(  # noqa: TRY004 - a ValueError, as Pydantic needs
            f"{field} is not the text of a JSON object (VM-08-002)"
        )
    return value


def received_body_digest(sealed_text: str) -> str:
    """The SHA-256 digest of a sealed received body's text.

    Taken over the text exactly as the parser sealed it, with no
    normalisation: a body re-serialized with another key order has another
    digest, which is what lets a reused id be told from a redelivery
    (IE-10-002), and what a receipt stub keeps in place of the body it gave
    up (ADR-0154).
    """
    return hashlib.sha256(sealed_text.encode("utf-8")).hexdigest()
