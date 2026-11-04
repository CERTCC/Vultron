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


"""The bases every trigger request body shares.

``CaseTriggerRequest`` is the case-scoped base of the request-model family
(ADR-0110); ``_parse_optional_roles`` is the shared roles parser.
"""

from pydantic import BaseModel, ConfigDict

from vultron.core.models.base import UriString
from vultron.enums.roles import validate_roles


def _parse_optional_roles(value: object) -> object:
    """Route a trigger body's ``roles`` through :func:`validate_roles`.

    ``None`` stays ``None`` (no roles supplied).  Anything else is parsed as
    every other role path parses it, so a retired value such as ``"finder"``
    is refused with its ADR-0078 reason, in any case.
    """
    if value is None:
        return None
    return validate_roles(value, field_name="roles")


class CaseTriggerRequest(BaseModel):
    """
    Request body for case-level trigger endpoints.

    TRIG-03-001: Must include case_id to identify the target case.
    TRIG-03-002: Unknown fields are silently ignored (extra="ignore").
    """

    model_config = ConfigDict(extra="ignore")

    case_id: UriString
