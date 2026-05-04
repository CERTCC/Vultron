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

"""Seed configuration for bootstrapping actor records in the DataLayer.

Supports loading actor seed data from environment variables or a YAML config
file.  Used by the ``vultron-demo seed`` CLI sub-command (D5-1-G2).

Environment variables
---------------------
``VULTRON_ACTOR_NAME``
    Display name for the local actor (default: ``"Vultron Actor"``).
``VULTRON_ACTOR_TYPE``
    ActivityStreams actor type for the local actor.  One of ``Person``,
    ``Organization``, ``Service``, ``Application``, or ``Group`` (default:
    ``"Organization"``).
``VULTRON_ACTOR_ID``
    Optional full URI for the local actor.  When absent the server derives
    one from ``VULTRON_BASE_URL``.
``VULTRON_SEED_CONFIG``
    Path to a YAML file that overrides the individual env-var values above
    (see ``SeedConfig`` for the expected schema).
"""

import os
from typing import Literal, cast

import yaml
from pydantic import BaseModel, Field

from vultron.core.models.actor_config import ActorConfig

#: Valid ActivityStreams actor type strings accepted by the seed command.
ActorType = Literal[
    "Person", "Organization", "Service", "Application", "Group"
]


class LocalActorConfig(ActorConfig):
    """Configuration for the local actor record to create on startup."""

    name: str = Field(description="Display name of the local actor.")
    actor_type: ActorType = Field(
        default="Organization",
        description="ActivityStreams actor type.",
    )
    id_: str | None = Field(
        default=None,
        alias="id",
        description=(
            "Full URI of the local actor. "
            "Omit to let the server derive one from ``VULTRON_BASE_URL``."
        ),
    )

    model_config = {"populate_by_name": True}


class PeerActorConfig(BaseModel):
    """Configuration for a remote peer actor to register in the local DataLayer."""

    name: str = Field(description="Display name of the peer actor.")
    actor_type: ActorType = Field(
        default="Organization",
        description="ActivityStreams actor type.",
    )
    id_: str = Field(
        alias="id",
        description="Full URI of the peer actor (must include inbox-derivable path).",
    )

    model_config = {"populate_by_name": True}


class SeedConfig(BaseModel):
    """Complete seed configuration: one local actor plus zero or more peers.

    Can be loaded from a YAML file whose top-level keys are ``local_actor``
    and ``peers``::

        local_actor:
          name: Finder
          actor_type: Person
          id: http://finder:7999/api/v2/actors/finder-uuid
        peers:
          - name: Vendor
            actor_type: Organization
            id: http://vendor:7999/api/v2/actors/vendor-uuid
    """

    local_actor: LocalActorConfig
    peers: list[PeerActorConfig] = Field(default_factory=list)

    @classmethod
    def from_env(
        cls,
        actor_name: str | None = None,
        actor_type: str | None = None,
        actor_id: str | None = None,
    ) -> "SeedConfig":
        """Build a SeedConfig from environment variables and/or explicit args.

        Explicit arguments take precedence over environment variables.

        Args:
            actor_name: Local actor display name.  Falls back to
                ``VULTRON_ACTOR_NAME`` env var (default: ``"Vultron Actor"``).
            actor_type: Local actor type string.  Falls back to
                ``VULTRON_ACTOR_TYPE`` env var (default: ``"Organization"``).
            actor_id: Optional full URI for the local actor.  Falls back to
                ``VULTRON_ACTOR_ID`` env var.
        """
        name = actor_name or os.environ.get(
            "VULTRON_ACTOR_NAME", "Vultron Actor"
        )
        a_type = actor_type or os.environ.get(
            "VULTRON_ACTOR_TYPE", "Organization"
        )
        a_id = actor_id or os.environ.get("VULTRON_ACTOR_ID") or None
        return cls(
            local_actor=LocalActorConfig(
                name=name,
                actor_type=cast(ActorType, a_type),
                id=a_id,
            )
        )

    @classmethod
    def from_file(cls, path: str) -> "SeedConfig":
        """Load a SeedConfig from a YAML file.

        Args:
            path: Filesystem path to the YAML seed config file.

        Raises:
            FileNotFoundError: If ``path`` does not exist.
            ValueError: If the YAML content does not match the expected schema.
        """
        with open(path) as fh:
            data = yaml.safe_load(fh)
        return cls.model_validate(data)

    @classmethod
    def load(
        cls,
        config_path: str | None = None,
        actor_name: str | None = None,
        actor_type: str | None = None,
        actor_id: str | None = None,
    ) -> "SeedConfig":
        """Load a SeedConfig from a JSON file or environment variables.

        If ``config_path`` is given (or ``VULTRON_SEED_CONFIG`` env var is
        set), the YAML file takes precedence.  Otherwise, configuration is
        assembled from env vars and any explicit keyword arguments.

        Args:
            config_path: Path to YAML seed config file.
            actor_name: Local actor display name (env var fallback).
            actor_type: Local actor type string (env var fallback).
            actor_id: Optional local actor URI (env var fallback).
        """
        path = config_path or os.environ.get("VULTRON_SEED_CONFIG")
        if path:
            return cls.from_file(path)
        return cls.from_env(
            actor_name=actor_name,
            actor_type=actor_type,
            actor_id=actor_id,
        )
