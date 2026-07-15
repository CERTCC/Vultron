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

import json
import logging
import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import (
    BaseModel,
    Field,
    field_serializer,
    field_validator,
)

from vultron.enums.roles import CVDRole, serialize_roles, validate_roles

logger = logging.getLogger(__name__)


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

    @field_serializer("default_case_roles")
    def _serialize_default_case_roles(self, value: list[CVDRole]) -> list[str]:
        return serialize_roles(value)

    @field_validator("default_case_roles", mode="before")
    @classmethod
    def _validate_default_case_roles(cls, value: object) -> list[CVDRole]:
        return validate_roles(value)


def _actor_config_from_seed_yaml(path: str) -> ActorConfig | None:
    """Extract actor policy fields from a seed YAML file.

    Reads the ``local_actor`` block from the YAML and constructs an
    :class:`ActorConfig` using only the policy fields it recognises,
    discarding bootstrap-only fields (``name``, ``actor_type``, ``id``)
    via ``extra="ignore"`` (CFG-07-005).

    Returns ``None`` if the file is missing or unparseable.
    """
    p = Path(path)
    if not p.exists():
        logger.debug("_actor_config_from_seed_yaml: file not found: %s", path)
        return None
    try:
        with p.open() as fh:
            raw: Any = yaml.safe_load(fh) or {}
        if not isinstance(raw, dict) or "local_actor" not in raw:
            return None
        local_actor_data: Any = raw["local_actor"]
        if not isinstance(local_actor_data, dict):
            return None
        return ActorConfig.model_validate(local_actor_data, strict=False)
    except Exception as exc:
        logger.debug(
            "_actor_config_from_seed_yaml: could not parse %s: %s", path, exc
        )
        return None


def _actor_config_from_env() -> ActorConfig:
    """Build an :class:`ActorConfig` from ``VULTRON_ACTOR__*`` env vars.

    Reads ``VULTRON_ACTOR__AUTO_CREATE_CASE`` and
    ``VULTRON_ACTOR__DEFAULT_CASE_ROLES`` with their documented defaults.
    """
    raw: dict[str, Any] = {}
    auto_create = os.environ.get("VULTRON_ACTOR__AUTO_CREATE_CASE")
    if auto_create is not None:
        raw["auto_create_case"] = auto_create.lower() not in (
            "false",
            "0",
            "no",
        )
    default_roles = os.environ.get("VULTRON_ACTOR__DEFAULT_CASE_ROLES")
    if default_roles is not None:
        try:
            raw["default_case_roles"] = json.loads(default_roles)
        except json.JSONDecodeError:
            # Treat as a comma-separated list
            raw["default_case_roles"] = [
                r.strip() for r in default_roles.split(",") if r.strip()
            ]
    return ActorConfig.model_validate(raw)


def load_actor_config() -> ActorConfig:
    """Load the local actor's policy :class:`ActorConfig`.

    Resolution order (CFG-07-005):

    1. ``VULTRON_SEED_CONFIG`` YAML — reads the ``local_actor`` block,
       extracting only policy fields and ignoring bootstrap-only fields
       (``name``, ``actor_type``, ``id``).
    2. ``VULTRON_ACTOR__*`` environment variables.
    3. Hard-coded defaults (``auto_create_case=True``,
       ``default_case_roles=[]``).

    Production adapter modules MUST call this function instead of importing
    from ``vultron.demo`` to obtain actor policy configuration (CFG-07-005).

    Returns:
        An :class:`ActorConfig` populated from the available sources.
    """
    seed_path = os.environ.get("VULTRON_SEED_CONFIG")
    if seed_path:
        cfg = _actor_config_from_seed_yaml(seed_path)
        if cfg is not None:
            return cfg
    return _actor_config_from_env()
