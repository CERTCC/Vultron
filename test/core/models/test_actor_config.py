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

"""
Tests for ActorConfig neutral model.

Spec coverage:
- CFG-07-001: ActorConfig MUST be defined outside the demo layer.
- CFG-07-002: ActorConfig MUST include a default_case_roles field
              (list[CVDRoles], default empty list).
"""

import pytest

from vultron.core.models.actor_config import ActorConfig
from vultron.core.states.roles import CVDRoles

# ============================================================================
# Basic model tests (CFG-07-001, CFG-07-002)
# ============================================================================


def test_actor_config_default_roles_empty():
    """ActorConfig.default_case_roles defaults to an empty list (CFG-07-002)."""
    config = ActorConfig()
    assert config.default_case_roles == []


def test_actor_config_accepts_cvd_roles():
    """ActorConfig.default_case_roles accepts CVDRoles enum values."""
    config = ActorConfig(default_case_roles=[CVDRoles.VENDOR])
    assert CVDRoles.VENDOR in config.default_case_roles


def test_actor_config_accepts_multiple_roles():
    """ActorConfig.default_case_roles accepts multiple roles."""
    config = ActorConfig(
        default_case_roles=[CVDRoles.COORDINATOR, CVDRoles.VENDOR]
    )
    assert CVDRoles.COORDINATOR in config.default_case_roles
    assert CVDRoles.VENDOR in config.default_case_roles


def test_actor_config_accepts_role_names_as_strings():
    """ActorConfig.default_case_roles parses role names from strings (YAML compat)."""
    config = ActorConfig.model_validate(
        {"default_case_roles": ["VENDOR", "COORDINATOR"]}
    )
    assert CVDRoles.VENDOR in config.default_case_roles
    assert CVDRoles.COORDINATOR in config.default_case_roles


def test_actor_config_rejects_invalid_role_name():
    """ActorConfig raises ValueError for unknown role names."""
    with pytest.raises((ValueError, KeyError)):
        ActorConfig.model_validate({"default_case_roles": ["NOT_A_ROLE"]})


def test_actor_config_serializes_roles_as_names():
    """ActorConfig serializes default_case_roles as role name strings."""
    config = ActorConfig(default_case_roles=[CVDRoles.VENDOR])
    data = config.model_dump()
    assert data["default_case_roles"] == ["VENDOR"]


def test_actor_config_roundtrip():
    """ActorConfig round-trips through model_dump / model_validate."""
    config = ActorConfig(
        default_case_roles=[CVDRoles.COORDINATOR, CVDRoles.VENDOR]
    )
    data = config.model_dump()
    restored = ActorConfig.model_validate(data)
    assert restored.default_case_roles == config.default_case_roles


def test_actor_config_does_not_mutate_between_uses():
    """Shared ActorConfig instances do not leak mutations between uses."""
    config = ActorConfig(default_case_roles=[CVDRoles.VENDOR])
    roles_before = list(config.default_case_roles)
    # Simulate a second use: build effective roles list
    _ = list(dict.fromkeys(config.default_case_roles + [CVDRoles.CASE_OWNER]))
    assert config.default_case_roles == roles_before


# ============================================================================
# LocalActorConfig composition (CFG-07-003)
# ============================================================================


def test_local_actor_config_inherits_actor_config():
    """LocalActorConfig MUST inherit from ActorConfig (CFG-07-003)."""
    from vultron.demo.seed_config import LocalActorConfig

    assert issubclass(LocalActorConfig, ActorConfig)


def test_local_actor_config_has_default_case_roles():
    """LocalActorConfig exposes default_case_roles from ActorConfig."""
    from vultron.demo.seed_config import LocalActorConfig

    cfg = LocalActorConfig(name="Test Actor")
    assert hasattr(cfg, "default_case_roles")
    assert cfg.default_case_roles == []


def test_local_actor_config_with_roles():
    """LocalActorConfig accepts default_case_roles alongside actor fields."""
    from vultron.demo.seed_config import LocalActorConfig

    cfg = LocalActorConfig(
        name="Coordinator",
        default_case_roles=[CVDRoles.COORDINATOR],
    )
    assert CVDRoles.COORDINATOR in cfg.default_case_roles
    assert cfg.name == "Coordinator"
