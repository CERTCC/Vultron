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

"""Actor policy configuration model.

Provides :class:`ActorConfig`: a minimal Pydantic model that carries CVD-role
defaults for the local actor without importing from the demo or adapter layers.

``ActorConfig`` imports ``CVDRole`` from ``vultron.enums.roles`` (not from
``vultron.core``) to satisfy the neutral-module constraint on
``vultron/config/``.

Per ``specs/configuration.yaml`` CFG-07-001, CFG-07-002, CFG-07-005, CFG-07-006.
"""

from pydantic import (
    BaseModel,
    Field,
    HttpUrl,
    field_serializer,
    field_validator,
)

from vultron.enums.roles import CVDRole, serialize_roles, validate_roles


class ActorConfig(BaseModel):
    """Minimal, layer-neutral configuration for the local actor.

    Carries the CVD roles the local actor assumes when creating or owning
    a ``VulnerabilityCase``.  BT nodes use this to parameterize participant
    creation without importing from the demo or adapter layers (CFG-07-001).

    Attributes:
        default_case_roles: CVD roles assigned to the local actor when it
            creates or receives ownership of a ``VulnerabilityCase``.
            Defaults to an empty list; ``CVDRole.CASE_OWNER`` is always
            appended at participant-creation time (BTND-05-002).
        auto_create_case: When ``True`` (default), create a
            ``VulnerabilityCase`` immediately on ``Offer(Report)`` receipt
            per ADR-0015 (Option 4).  When ``False``, defer case creation so
            the receiver can send a pre-case ACK (``Read(Offer(Report))``)
            before deciding to accept or reject (ADR-0015 Option 3;
            CM-15-001, issue #1133).
        case_actor_service_url: Base URL of the dedicated CaseActor service
            (e.g. ``http://case-actor:7999/api/v2``).  Required for any actor
            whose BT may run the ``engage-case`` path.  When ``None``,
            ``ResolveCaseActorUrlsNode`` returns ``FAILURE`` with a clear
            error message (CP-08-001, CP-08-002).
    """

    default_case_roles: list[CVDRole] = Field(default_factory=list)
    auto_create_case: bool = Field(
        default=True,
        description=(
            "When True (default), create a VulnerabilityCase immediately on "
            "Offer(Report) receipt per ADR-0015. When False, defer case "
            "creation to allow a pre-case ACK (Read(Offer(Report))) first."
        ),
    )
    case_actor_service_url: HttpUrl | None = Field(
        default=None,
        description=(
            "Base URL of the dedicated CaseActor service "
            "(e.g. http://case-actor:7999/api/v2). Required for actors that "
            "create cases; absence causes ResolveCaseActorUrlsNode to fail "
            "(CP-08-001)."
        ),
    )

    @field_serializer("default_case_roles")
    def _serialize_default_case_roles(self, value: list[CVDRole]) -> list[str]:
        return serialize_roles(value)

    @field_validator("default_case_roles", mode="before")
    @classmethod
    def _validate_default_case_roles(cls, value: object) -> list[CVDRole]:
        return validate_roles(value)
