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

"""Tests for the seed configuration model (D5-1-G2).

Covers ``SeedConfig``, ``LocalActorConfig``, and ``PeerActorConfig`` loaded
from environment variables and from a YAML file.
"""

import yaml

import pytest

from vultron.demo.seed_config import (
    LocalActorConfig,
    PeerActorConfig,
    SeedConfig,
)


class TestLocalActorConfig:
    def test_minimal_config(self):
        cfg = LocalActorConfig(name="Alice")
        assert cfg.name == "Alice"
        assert cfg.actor_type == "Organization"
        assert cfg.id_ is None

    def test_custom_actor_type(self):
        cfg = LocalActorConfig(name="Alice", actor_type="Person")
        assert cfg.actor_type == "Person"

    def test_custom_id_via_field(self):
        cfg = LocalActorConfig(
            name="Alice", id="http://example.org/actors/alice"
        )
        assert cfg.id_ == "http://example.org/actors/alice"

    def test_custom_id_via_alias(self):
        cfg = LocalActorConfig.model_validate(
            {"name": "Alice", "id": "http://example.org/actors/alice"}
        )
        assert cfg.id_ == "http://example.org/actors/alice"


class TestPeerActorConfig:
    def test_requires_id(self):
        with pytest.raises(Exception):
            PeerActorConfig.model_validate({"name": "Bob"})  # id required

    def test_valid_peer(self):
        peer = PeerActorConfig(
            name="Vendor",
            actor_type="Organization",
            id="http://vendor:7999/api/v2/actors/vendor-uuid",
        )
        assert peer.name == "Vendor"
        assert peer.id_ == "http://vendor:7999/api/v2/actors/vendor-uuid"

    def test_peer_id_via_alias(self):
        peer = PeerActorConfig.model_validate(
            {"name": "Vendor", "id": "http://vendor:7999/api/v2/actors/v"}
        )
        assert peer.id_ == "http://vendor:7999/api/v2/actors/v"


class TestSeedConfigFromEnv:
    def test_from_env_defaults(self, monkeypatch):
        monkeypatch.delenv("VULTRON_ACTOR_NAME", raising=False)
        monkeypatch.delenv("VULTRON_ACTOR_TYPE", raising=False)
        monkeypatch.delenv("VULTRON_ACTOR_ID", raising=False)
        cfg = SeedConfig.from_env()
        assert cfg.local_actor.name == "Vultron Actor"
        assert cfg.local_actor.actor_type == "Organization"
        assert cfg.local_actor.id_ is None
        assert cfg.peers == []

    def test_from_env_reads_name(self, monkeypatch):
        monkeypatch.setenv("VULTRON_ACTOR_NAME", "Finder")
        monkeypatch.delenv("VULTRON_ACTOR_TYPE", raising=False)
        monkeypatch.delenv("VULTRON_ACTOR_ID", raising=False)
        cfg = SeedConfig.from_env()
        assert cfg.local_actor.name == "Finder"

    def test_from_env_reads_type(self, monkeypatch):
        monkeypatch.delenv("VULTRON_ACTOR_NAME", raising=False)
        monkeypatch.setenv("VULTRON_ACTOR_TYPE", "Person")
        monkeypatch.delenv("VULTRON_ACTOR_ID", raising=False)
        cfg = SeedConfig.from_env()
        assert cfg.local_actor.actor_type == "Person"

    def test_from_env_reads_id(self, monkeypatch):
        monkeypatch.setenv("VULTRON_ACTOR_NAME", "Finder")
        monkeypatch.delenv("VULTRON_ACTOR_TYPE", raising=False)
        monkeypatch.setenv(
            "VULTRON_ACTOR_ID", "http://finder:7999/api/v2/actors/finder"
        )
        cfg = SeedConfig.from_env()
        assert cfg.local_actor.id_ == "http://finder:7999/api/v2/actors/finder"

    def test_from_env_explicit_args_override_env(self, monkeypatch):
        monkeypatch.setenv("VULTRON_ACTOR_NAME", "EnvName")
        monkeypatch.setenv("VULTRON_ACTOR_TYPE", "Organization")
        cfg = SeedConfig.from_env(actor_name="CliName", actor_type="Person")
        assert cfg.local_actor.name == "CliName"
        assert cfg.local_actor.actor_type == "Person"


class TestSeedConfigFromFile:
    def test_from_file_local_actor_only(self, tmp_path):
        data = {
            "local_actor": {
                "name": "Finder",
                "actor_type": "Person",
                "id": "http://finder:7999/api/v2/actors/finder-uuid",
            }
        }
        config_file = tmp_path / "seed.yaml"
        config_file.write_text(yaml.dump(data))
        cfg = SeedConfig.from_file(str(config_file))
        assert cfg.local_actor.name == "Finder"
        assert cfg.local_actor.actor_type == "Person"
        assert (
            cfg.local_actor.id_
            == "http://finder:7999/api/v2/actors/finder-uuid"
        )
        assert cfg.peers == []

    def test_from_file_with_peers(self, tmp_path):
        data = {
            "local_actor": {
                "name": "Finder",
                "actor_type": "Person",
                "id": "http://f/actors/a",
            },
            "peers": [
                {
                    "name": "Vendor",
                    "actor_type": "Organization",
                    "id": "http://vendor:7999/api/v2/actors/vendor-uuid",
                },
                {
                    "name": "Coordinator",
                    "actor_type": "Organization",
                    "id": "http://coordinator:7999/api/v2/actors/coord-uuid",
                },
            ],
        }
        config_file = tmp_path / "seed.yaml"
        config_file.write_text(yaml.dump(data))
        cfg = SeedConfig.from_file(str(config_file))
        assert len(cfg.peers) == 2
        assert cfg.peers[0].name == "Vendor"
        assert cfg.peers[1].name == "Coordinator"

    def test_from_file_not_found_raises(self):
        with pytest.raises(FileNotFoundError):
            SeedConfig.from_file("/nonexistent/path/seed.yaml")

    def test_from_file_invalid_schema_raises(self, tmp_path):
        config_file = tmp_path / "bad.yaml"
        config_file.write_text("bad_key: bad_value\n")
        with pytest.raises(Exception):
            SeedConfig.from_file(str(config_file))


class TestSeedConfigLoad:
    def test_load_uses_file_when_config_path_provided(
        self, tmp_path, monkeypatch
    ):
        data = {
            "local_actor": {
                "name": "FromFile",
                "actor_type": "Service",
                "id": "http://example.org/actors/fromfile",
            }
        }
        config_file = tmp_path / "seed.yaml"
        config_file.write_text(yaml.dump(data))
        monkeypatch.delenv("VULTRON_SEED_CONFIG", raising=False)
        cfg = SeedConfig.load(config_path=str(config_file))
        assert cfg.local_actor.name == "FromFile"

    def test_load_uses_env_var_config_path(self, tmp_path, monkeypatch):
        data = {
            "local_actor": {
                "name": "EnvFile",
                "actor_type": "Person",
                "id": "http://f/a",
            }
        }
        config_file = tmp_path / "seed.yaml"
        config_file.write_text(yaml.dump(data))
        monkeypatch.setenv("VULTRON_SEED_CONFIG", str(config_file))
        cfg = SeedConfig.load()
        assert cfg.local_actor.name == "EnvFile"

    def test_load_falls_back_to_env_when_no_file(self, monkeypatch):
        monkeypatch.delenv("VULTRON_SEED_CONFIG", raising=False)
        monkeypatch.setenv("VULTRON_ACTOR_NAME", "FallbackName")
        monkeypatch.delenv("VULTRON_ACTOR_TYPE", raising=False)
        monkeypatch.delenv("VULTRON_ACTOR_ID", raising=False)
        cfg = SeedConfig.load()
        assert cfg.local_actor.name == "FallbackName"

    def test_load_explicit_config_path_overrides_env_var(
        self, tmp_path, monkeypatch
    ):
        """Explicit config_path must take precedence over VULTRON_SEED_CONFIG."""
        env_data = {
            "local_actor": {"name": "EnvFileActor", "id": "http://env/a"}
        }
        explicit_data = {
            "local_actor": {"name": "ExplicitFileActor", "id": "http://exp/a"}
        }

        env_file = tmp_path / "env_seed.yaml"
        env_file.write_text(yaml.dump(env_data))
        explicit_file = tmp_path / "explicit_seed.yaml"
        explicit_file.write_text(yaml.dump(explicit_data))

        monkeypatch.setenv("VULTRON_SEED_CONFIG", str(env_file))
        cfg = SeedConfig.load(config_path=str(explicit_file))
        assert cfg.local_actor.name == "ExplicitFileActor"
