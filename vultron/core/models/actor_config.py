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

"""Neutral actor configuration model for BT nodes and adapters.

Provides :class:`ActorConfig`: a minimal Pydantic model that carries CVD-role
defaults for the local actor without importing from the demo or adapter layers.

Per specs/configuration.yaml CFG-07-001 and CFG-07-002.
"""

from pydantic import BaseModel, Field, field_serializer, field_validator

from vultron.core.states.roles import CVDRoles


class ActorConfig(BaseModel):
    """Minimal, layer-neutral configuration for the local actor.

    Carries the CVD roles the local actor assumes when creating or owning
    a ``VulnerabilityCase``.  BT nodes use this to parameterize participant
    creation without importing from the demo or adapter layers (CFG-07-001).

    Attributes:
        default_case_roles: CVD roles assigned to the local actor when it
            creates or receives ownership of a ``VulnerabilityCase``.
            Defaults to an empty list; ``CVDRoles.CASE_OWNER`` is always
            appended at participant-creation time (BTND-05-002).
    """

    default_case_roles: list[CVDRoles] = Field(default_factory=list)

    @field_serializer("default_case_roles")
    def _serialize_default_case_roles(
        self, value: list[CVDRoles]
    ) -> list[str]:
        return [
            role.name if role.name is not None else str(role) for role in value
        ]

    @field_validator("default_case_roles", mode="before")
    @classmethod
    def _validate_default_case_roles(cls, value: list) -> list:
        if isinstance(value, list) and value and isinstance(value[0], str):
            return [CVDRoles[name] for name in value]
        return value
