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
Tests for ActorConfig neutral model and load_actor_config().

Spec coverage:
- CFG-07-001: ActorConfig MUST be defined outside the demo layer.
- CFG-07-002: ActorConfig MUST include a default_case_roles field
              (list[CVDRole], default empty list).
- CFG-07-005: load_actor_config() must exist in vultron/config/.
- CFG-07-007: LocalActorConfig must not extend ActorConfig.
"""

import yaml
import pytest

from vultron.config.actor import ActorConfig, load_actor_config
from vultron.enums.roles import CVDRole

# ============================================================================
# Basic model tests (CFG-07-001, CFG-07-002)
# ============================================================================


def test_actor_config_default_roles_empty():
    """ActorConfig.default_case_roles defaults to an empty list (CFG-07-002)."""
    config = ActorConfig()
    assert config.default_case_roles == []


def test_actor_config_auto_create_case_defaults_true():
    """ActorConfig.auto_create_case defaults to True (CM-15-001, ADR-0015)."""
    config = ActorConfig()
    assert config.auto_create_case is True


def test_actor_config_auto_create_case_can_be_disabled():
    """ActorConfig.auto_create_case can be set to False (CM-15-001)."""
    config = ActorConfig(auto_create_case=False)
    assert config.auto_create_case is False


def test_actor_config_auto_create_case_roundtrip():
    """auto_create_case round-trips through model_dump / model_validate."""
    config = ActorConfig(auto_create_case=False)
    restored = ActorConfig.model_validate(config.model_dump())
    assert restored.auto_create_case is False


def test_actor_config_accepts_cvd_roles():
    """ActorConfig.default_case_roles accepts CVDRoles enum values."""
    config = ActorConfig(default_case_roles=[CVDRole.VENDOR])
    assert CVDRole.VENDOR in config.default_case_roles


def test_actor_config_accepts_multiple_roles():
    """ActorConfig.default_case_roles accepts multiple roles."""
    config = ActorConfig(
        default_case_roles=[CVDRole.COORDINATOR, CVDRole.VENDOR]
    )
    assert CVDRole.COORDINATOR in config.default_case_roles
    assert CVDRole.VENDOR in config.default_case_roles


def test_actor_config_accepts_role_names_as_strings():
    """ActorConfig.default_case_roles parses role names from strings (YAML compat)."""
    config = ActorConfig.model_validate(
        {"default_case_roles": ["VENDOR", "COORDINATOR"]}
    )
    assert CVDRole.VENDOR in config.default_case_roles
    assert CVDRole.COORDINATOR in config.default_case_roles


def test_actor_config_rejects_invalid_role_name():
    """ActorConfig raises ValueError for unknown role names."""
    with pytest.raises((ValueError, KeyError)):
        ActorConfig.model_validate({"default_case_roles": ["NOT_A_ROLE"]})


def test_actor_config_rejects_scalar_default_case_roles():
    """ActorConfig raises ValueError when default_case_roles is a scalar string."""
    with pytest.raises((ValueError, KeyError)):
        ActorConfig.model_validate({"default_case_roles": "coordinator"})


def test_actor_config_serializes_roles_as_names():
    """ActorConfig serializes default_case_roles as role value strings."""
    config = ActorConfig(default_case_roles=[CVDRole.VENDOR])
    data = config.model_dump()
    assert data["default_case_roles"] == ["vendor"]


def test_actor_config_roundtrip():
    """ActorConfig round-trips through model_dump / model_validate."""
    config = ActorConfig(
        default_case_roles=[CVDRole.COORDINATOR, CVDRole.VENDOR]
    )
    data = config.model_dump()
    restored = ActorConfig.model_validate(data)
    assert restored.default_case_roles == config.default_case_roles


def test_actor_config_does_not_mutate_between_uses():
    """Shared ActorConfig instances do not leak mutations between uses."""
    config = ActorConfig(default_case_roles=[CVDRole.VENDOR])
    roles_before = list(config.default_case_roles)
    # Simulate a second use: build effective roles list
    _ = list(dict.fromkeys(config.default_case_roles + [CVDRole.CASE_OWNER]))
    assert config.default_case_roles == roles_before


# ============================================================================
# LocalActorConfig decoupling from ActorConfig (CFG-07-007)
# ============================================================================


def test_local_actor_config_is_plain_base_model():
    """LocalActorConfig MUST be a plain BaseModel, not a subclass of ActorConfig
    (CFG-07-007).
    """
    from pydantic import BaseModel

    from vultron.demo.seed_config import LocalActorConfig

    assert issubclass(LocalActorConfig, BaseModel)
    assert not issubclass(LocalActorConfig, ActorConfig)


def test_local_actor_config_has_no_policy_fields():
    """LocalActorConfig must NOT have auto_create_case or default_case_roles
    (CFG-07-007).
    """
    from vultron.demo.seed_config import LocalActorConfig

    cfg = LocalActorConfig(name="Test Actor")
    assert not hasattr(cfg, "auto_create_case")
    assert not hasattr(cfg, "default_case_roles")


def test_local_actor_config_identity_fields_only():
    """LocalActorConfig carries only name, actor_type, and id_ (CFG-07-007)."""
    from vultron.demo.seed_config import LocalActorConfig

    cfg = LocalActorConfig(
        name="Coordinator",
        actor_type="Service",
        id="http://coordinator:7999/api/v2/actors/coordinator",
    )
    assert cfg.name == "Coordinator"
    assert cfg.actor_type == "Service"
    assert cfg.id_ == "http://coordinator:7999/api/v2/actors/coordinator"


# ============================================================================
# load_actor_config() (CFG-07-005)
# ============================================================================


def test_load_actor_config_returns_actor_config():
    """load_actor_config() MUST return an ActorConfig instance (CFG-07-005)."""
    cfg = load_actor_config()
    assert isinstance(cfg, ActorConfig)


def test_load_actor_config_defaults(monkeypatch):
    """load_actor_config() returns defaults when no env vars or file set."""
    monkeypatch.delenv("VULTRON_SEED_CONFIG", raising=False)
    monkeypatch.delenv("VULTRON_ACTOR__AUTO_CREATE_CASE", raising=False)
    monkeypatch.delenv("VULTRON_ACTOR__DEFAULT_CASE_ROLES", raising=False)
    cfg = load_actor_config()
    assert cfg.auto_create_case is True
    assert cfg.default_case_roles == []


def test_load_actor_config_reads_auto_create_case_from_env(monkeypatch):
    """load_actor_config() reads VULTRON_ACTOR__AUTO_CREATE_CASE env var."""
    monkeypatch.delenv("VULTRON_SEED_CONFIG", raising=False)
    monkeypatch.setenv("VULTRON_ACTOR__AUTO_CREATE_CASE", "false")
    monkeypatch.delenv("VULTRON_ACTOR__DEFAULT_CASE_ROLES", raising=False)
    cfg = load_actor_config()
    assert cfg.auto_create_case is False


def test_load_actor_config_reads_default_case_roles_from_env(monkeypatch):
    """load_actor_config() reads VULTRON_ACTOR__DEFAULT_CASE_ROLES env var."""
    monkeypatch.delenv("VULTRON_SEED_CONFIG", raising=False)
    monkeypatch.delenv("VULTRON_ACTOR__AUTO_CREATE_CASE", raising=False)
    monkeypatch.setenv("VULTRON_ACTOR__DEFAULT_CASE_ROLES", '["coordinator"]')
    cfg = load_actor_config()
    assert CVDRole.COORDINATOR in cfg.default_case_roles


def test_load_actor_config_reads_policy_from_seed_yaml(tmp_path, monkeypatch):
    """load_actor_config() extracts policy fields from VULTRON_SEED_CONFIG YAML."""
    seed_file = tmp_path / "seed.yaml"
    data = {
        "local_actor": {
            "name": "Vendor",
            "actor_type": "Organization",
            "id": "http://vendor:7999/api/v2/actors/vendor",
            "auto_create_case": False,
            "default_case_roles": ["coordinator"],
        }
    }
    seed_file.write_text(yaml.dump(data))
    monkeypatch.setenv("VULTRON_SEED_CONFIG", str(seed_file))
    monkeypatch.delenv("VULTRON_ACTOR__AUTO_CREATE_CASE", raising=False)
    monkeypatch.delenv("VULTRON_ACTOR__DEFAULT_CASE_ROLES", raising=False)
    cfg = load_actor_config()
    assert cfg.auto_create_case is False
    assert CVDRole.COORDINATOR in cfg.default_case_roles


def test_load_actor_config_ignores_bootstrap_fields_from_yaml(
    tmp_path, monkeypatch
):
    """load_actor_config() ignores name/actor_type/id from YAML (extra=ignore)."""
    seed_file = tmp_path / "seed.yaml"
    data = {
        "local_actor": {
            "name": "Vendor",
            "actor_type": "Organization",
            "id": "http://vendor:7999/api/v2/actors/vendor",
        }
    }
    seed_file.write_text(yaml.dump(data))
    monkeypatch.setenv("VULTRON_SEED_CONFIG", str(seed_file))
    monkeypatch.delenv("VULTRON_ACTOR__AUTO_CREATE_CASE", raising=False)
    monkeypatch.delenv("VULTRON_ACTOR__DEFAULT_CASE_ROLES", raising=False)
    cfg = load_actor_config()
    # Bootstrap fields are ignored; policy defaults apply
    assert cfg.auto_create_case is True
    assert cfg.default_case_roles == []
    assert not hasattr(cfg, "name")


def test_load_actor_config_falls_back_to_env_when_seed_yaml_missing(
    tmp_path, monkeypatch
):
    """load_actor_config() falls back to env vars when VULTRON_SEED_CONFIG file
    is missing.
    """
    monkeypatch.setenv(
        "VULTRON_SEED_CONFIG", str(tmp_path / "nonexistent.yaml")
    )
    monkeypatch.setenv("VULTRON_ACTOR__AUTO_CREATE_CASE", "false")
    monkeypatch.delenv("VULTRON_ACTOR__DEFAULT_CASE_ROLES", raising=False)
    cfg = load_actor_config()
    assert cfg.auto_create_case is False


def test_load_actor_config_falls_back_to_env_when_yaml_has_no_local_actor(
    tmp_path, monkeypatch
):
    """load_actor_config() falls back to env vars when VULTRON_SEED_CONFIG YAML
    exists but contains no local_actor key (CFG-07-005 resolution order).
    """
    seed_file = tmp_path / "seed.yaml"
    seed_file.write_text(yaml.dump({"peers": []}))
    monkeypatch.setenv("VULTRON_SEED_CONFIG", str(seed_file))
    monkeypatch.setenv("VULTRON_ACTOR__AUTO_CREATE_CASE", "false")
    monkeypatch.delenv("VULTRON_ACTOR__DEFAULT_CASE_ROLES", raising=False)
    cfg = load_actor_config()
    assert cfg.auto_create_case is False


def test_load_actor_config_exported_from_config_package():
    """load_actor_config MUST be importable from vultron.config (CFG-07-005)."""
    from vultron.config import load_actor_config as lac

    assert callable(lac)
