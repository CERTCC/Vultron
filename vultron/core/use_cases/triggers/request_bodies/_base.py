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
(ADR-0110); ``_parse_optional_roles`` is the shared roles parser and
``refuse_authority_roles`` the shared authority-role check (CM-20-009).
"""

from pydantic import BaseModel, ConfigDict

from vultron.core.models.base import UriString
from vultron.enums.roles import (
    CVDRole,
    describe_authority_roles,
    validate_roles,
)


def refuse_authority_roles(roles: list[CVDRole]) -> list[CVDRole]:
    """Return *roles*, refusing a request that offers an authority role.

    No suggestion, invitation or role Offer confers ``CASE_MANAGER`` or
    ``CASE_OWNER``, and the CASE_MANAGER refuses one that names either
    (CM-20-008, CM-33-003), so a trigger never builds it (CM-20-009).

    Raises:
        ValueError: *roles* names an authority role.
    """
    named = describe_authority_roles(roles)
    if named is not None:
        raise ValueError(f"the request names {named} (CM-20-009)")
    return roles


def _parse_optional_roles(value: object) -> object:
    """Route a trigger body's ``roles`` through :func:`validate_roles`.

    ``None`` stays ``None`` (no roles supplied).  Anything else is parsed as
    every other role path parses it, so a former value such as ``"finder"``
    is refused as an invalid role, in any case (ADR-0175).  The roles name
    an invitee's, so an authority role is refused too (CM-20-009).
    """
    if value is None:
        return None
    return refuse_authority_roles(validate_roles(value, field_name="roles"))


class CaseTriggerRequest(BaseModel):
    """
    Request body for case-level trigger endpoints.

    TRIG-03-001: Must include case_id to identify the target case.
    TRIG-03-002: Unknown fields are silently ignored (extra="ignore").
    """

    model_config = ConfigDict(extra="ignore")

    case_id: UriString
