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

"""Tests for multi-actor seed configuration (D5-1-G3).

Verifies that the pre-built seed config JSON files in docker/seed-configs/
are valid SeedConfig schemas with deterministic actor IDs and correct peer
registrations for the multi-container Docker Compose setup.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from vultron.demo.cli import main
from vultron.demo.seed_config import SeedConfig
from vultron.demo.utils import DataLayerClient
from vultron.wire.as2.vocab.base.objects.actors import as_Actor

# ---------------------------------------------------------------------------
# Constants: expected deterministic IDs from docker-compose-multi-actor.yml
# ---------------------------------------------------------------------------

FINDER_ID = "http://finder:7999/api/v2/actors/finder"
VENDOR_ID = "http://vendor:7999/api/v2/actors/vendor"
COORDINATOR_ID = "http://coordinator:7999/api/v2/actors/coordinator"
CASE_ACTOR_ID = "http://case-actor:7999/api/v2/actors/case-actor"
VENDOR2_ID = "http://vendor2:7999/api/v2/actors/vendor2"

# Path to the docker/seed-configs/ directory (relative to project root).
_REPO_ROOT = Path(__file__).parents[2]
_SEED_CONFIGS_DIR = _REPO_ROOT / "docker" / "seed-configs"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_seed_config(filename: str) -> SeedConfig:
    """Load and validate one of the pre-built seed config JSON files."""
    path = _SEED_CONFIGS_DIR / filename
    return SeedConfig.from_file(str(path))


def _all_expected_peer_ids(own_id: str) -> set[str]:
    """Return the set of peer IDs expected for a given actor."""
    all_ids = {FINDER_ID, VENDOR_ID, COORDINATOR_ID, CASE_ACTOR_ID, VENDOR2_ID}
    return all_ids - {own_id}


# ---------------------------------------------------------------------------
# Tests for seed-finder.json
# ---------------------------------------------------------------------------


class TestSeedFinderConfig:
    def test_file_exists(self):
        assert (_SEED_CONFIGS_DIR / "seed-finder.json").exists()

    def test_valid_seed_config_schema(self):
        cfg = _load_seed_config("seed-finder.json")
        assert isinstance(cfg, SeedConfig)

    def test_local_actor_id_is_deterministic(self):
        cfg = _load_seed_config("seed-finder.json")
        assert cfg.local_actor.id_ == FINDER_ID

    def test_local_actor_type_is_person(self):
        cfg = _load_seed_config("seed-finder.json")
        assert cfg.local_actor.actor_type == "Person"

    def test_local_actor_name(self):
        cfg = _load_seed_config("seed-finder.json")
        assert cfg.local_actor.name == "Finder"

    def test_peers_include_vendor_and_case_actor(self):
        cfg = _load_seed_config("seed-finder.json")
        peer_ids = {p.id_ for p in cfg.peers}
        assert peer_ids == _all_expected_peer_ids(FINDER_ID)

    def test_peer_ids_are_deterministic(self):
        cfg = _load_seed_config("seed-finder.json")
        peer_ids = {p.id_ for p in cfg.peers}
        assert VENDOR_ID in peer_ids
        assert CASE_ACTOR_ID in peer_ids
        assert COORDINATOR_ID in peer_ids
        assert VENDOR2_ID in peer_ids


# ---------------------------------------------------------------------------
# Tests for seed-vendor.json
# ---------------------------------------------------------------------------


class TestSeedVendorConfig:
    def test_file_exists(self):
        assert (_SEED_CONFIGS_DIR / "seed-vendor.json").exists()

    def test_valid_seed_config_schema(self):
        cfg = _load_seed_config("seed-vendor.json")
        assert isinstance(cfg, SeedConfig)

    def test_local_actor_id_is_deterministic(self):
        cfg = _load_seed_config("seed-vendor.json")
        assert cfg.local_actor.id_ == VENDOR_ID

    def test_local_actor_type_is_organization(self):
        cfg = _load_seed_config("seed-vendor.json")
        assert cfg.local_actor.actor_type == "Organization"

    def test_local_actor_name(self):
        cfg = _load_seed_config("seed-vendor.json")
        assert cfg.local_actor.name == "Vendor"

    def test_peers_include_finder_and_case_actor(self):
        cfg = _load_seed_config("seed-vendor.json")
        peer_ids = {p.id_ for p in cfg.peers}
        assert peer_ids == _all_expected_peer_ids(VENDOR_ID)

    def test_peer_ids_are_deterministic(self):
        cfg = _load_seed_config("seed-vendor.json")
        peer_ids = {p.id_ for p in cfg.peers}
        assert FINDER_ID in peer_ids
        assert CASE_ACTOR_ID in peer_ids
        assert COORDINATOR_ID in peer_ids
        assert VENDOR2_ID in peer_ids


# ---------------------------------------------------------------------------
# Tests for seed-case-actor.json
# ---------------------------------------------------------------------------


class TestSeedCaseActorConfig:
    def test_file_exists(self):
        assert (_SEED_CONFIGS_DIR / "seed-case-actor.json").exists()

    def test_valid_seed_config_schema(self):
        cfg = _load_seed_config("seed-case-actor.json")
        assert isinstance(cfg, SeedConfig)

    def test_local_actor_id_is_deterministic(self):
        cfg = _load_seed_config("seed-case-actor.json")
        assert cfg.local_actor.id_ == CASE_ACTOR_ID

    def test_local_actor_type_is_service(self):
        cfg = _load_seed_config("seed-case-actor.json")
        assert cfg.local_actor.actor_type == "Service"

    def test_local_actor_name(self):
        cfg = _load_seed_config("seed-case-actor.json")
        assert cfg.local_actor.name == "CaseActor"

    def test_peers_include_finder_and_vendor(self):
        cfg = _load_seed_config("seed-case-actor.json")
        peer_ids = {p.id_ for p in cfg.peers}
        assert peer_ids == _all_expected_peer_ids(CASE_ACTOR_ID)

    def test_peer_ids_are_deterministic(self):
        cfg = _load_seed_config("seed-case-actor.json")
        peer_ids = {p.id_ for p in cfg.peers}
        assert FINDER_ID in peer_ids
        assert VENDOR_ID in peer_ids
        assert COORDINATOR_ID in peer_ids
        assert VENDOR2_ID in peer_ids


# ---------------------------------------------------------------------------
# Cross-config consistency tests
# ---------------------------------------------------------------------------


class TestSeedConfigCrossConsistency:
    """All five configs must describe a consistent peer mesh."""

    def test_all_configs_load_successfully(self):
        for filename in (
            "seed-finder.json",
            "seed-vendor.json",
            "seed-coordinator.json",
            "seed-case-actor.json",
            "seed-vendor2.json",
        ):
            cfg = _load_seed_config(filename)
            assert cfg is not None

    def test_each_config_has_exactly_four_peers(self):
        for filename in (
            "seed-finder.json",
            "seed-vendor.json",
            "seed-coordinator.json",
            "seed-case-actor.json",
            "seed-vendor2.json",
        ):
            cfg = _load_seed_config(filename)
            assert (
                len(cfg.peers) == 4
            ), f"{filename}: expected 4 peers, got {len(cfg.peers)}"

    def test_no_config_lists_itself_as_peer(self):
        for filename, own_id in [
            ("seed-finder.json", FINDER_ID),
            ("seed-vendor.json", VENDOR_ID),
            ("seed-coordinator.json", COORDINATOR_ID),
            ("seed-case-actor.json", CASE_ACTOR_ID),
            ("seed-vendor2.json", VENDOR2_ID),
        ]:
            cfg = _load_seed_config(filename)
            peer_ids = {p.id_ for p in cfg.peers}
            assert (
                own_id not in peer_ids
            ), f"{filename}: actor listed as its own peer"

    def test_every_actor_appears_as_peer_in_others(self):
        """Verify the peer mesh is symmetric: A knows B, B knows A."""
        configs = {
            FINDER_ID: _load_seed_config("seed-finder.json"),
            VENDOR_ID: _load_seed_config("seed-vendor.json"),
            COORDINATOR_ID: _load_seed_config("seed-coordinator.json"),
            CASE_ACTOR_ID: _load_seed_config("seed-case-actor.json"),
            VENDOR2_ID: _load_seed_config("seed-vendor2.json"),
        }
        for own_id, cfg in configs.items():
            for other_id, other_cfg in configs.items():
                if own_id == other_id:
                    continue
                other_peer_ids = {p.id_ for p in other_cfg.peers}
                assert own_id in other_peer_ids, (
                    f"Actor {own_id} is not listed as a peer in the "
                    f"config for {other_id}"
                )

    def test_all_deterministic_ids_are_full_http_uris(self):
        all_ids = [
            FINDER_ID,
            VENDOR_ID,
            COORDINATOR_ID,
            CASE_ACTOR_ID,
            VENDOR2_ID,
        ]
        for aid in all_ids:
            assert aid.startswith(
                "http://"
            ), f"Deterministic ID {aid!r} must be a full HTTP URI"

    def test_all_deterministic_ids_include_actors_path(self):
        all_ids = [
            FINDER_ID,
            VENDOR_ID,
            COORDINATOR_ID,
            CASE_ACTOR_ID,
            VENDOR2_ID,
        ]
        for aid in all_ids:
            assert (
                "/actors/" in aid
            ), f"Deterministic ID {aid!r} must include '/actors/' path"


# ---------------------------------------------------------------------------
# CLI integration: seed command uses VULTRON_ACTOR_ID from config file
# ---------------------------------------------------------------------------


class TestSeedCLIWithDeterministicId:
    """Verify that the seed CLI honours the fixed actor ID from seed configs."""

    def _run_seed_with_config(
        self, config_file: Path
    ) -> tuple[list[dict], int]:
        calls: list[dict] = []

        def _capturing_seed(
            client: DataLayerClient,
            name: str,
            actor_type: str = "Organization",
            actor_id: str | None = None,
        ) -> as_Actor:
            calls.append(
                {"name": name, "actor_type": actor_type, "actor_id": actor_id}
            )
            return as_Actor.model_validate(
                {"id": actor_id or f"http://mock/{name}", "name": name}
            )

        runner = CliRunner()
        with patch(
            "vultron.demo.cli.seed_actor",
            MagicMock(side_effect=_capturing_seed),
        ):
            result = runner.invoke(
                main,
                [
                    "seed",
                    "--config",
                    str(config_file),
                    "--api-url",
                    "http://localhost:7999/api/v2",
                ],
            )
        return calls, result.exit_code

    def test_finder_seed_uses_deterministic_id(self):
        config_path = _SEED_CONFIGS_DIR / "seed-finder.json"
        calls, exit_code = self._run_seed_with_config(config_path)
        assert exit_code == 0
        local_call = next((c for c in calls if c["name"] == "Finder"), None)
        assert local_call is not None
        assert local_call["actor_id"] == FINDER_ID

    def test_vendor_seed_uses_deterministic_id(self):
        config_path = _SEED_CONFIGS_DIR / "seed-vendor.json"
        calls, exit_code = self._run_seed_with_config(config_path)
        assert exit_code == 0
        local_call = next((c for c in calls if c["name"] == "Vendor"), None)
        assert local_call is not None
        assert local_call["actor_id"] == VENDOR_ID

    def test_case_actor_seed_uses_deterministic_id(self):
        config_path = _SEED_CONFIGS_DIR / "seed-case-actor.json"
        calls, exit_code = self._run_seed_with_config(config_path)
        assert exit_code == 0
        local_call = next((c for c in calls if c["name"] == "CaseActor"), None)
        assert local_call is not None
        assert local_call["actor_id"] == CASE_ACTOR_ID

    def test_finder_seed_registers_all_peers(self):
        config_path = _SEED_CONFIGS_DIR / "seed-finder.json"
        calls, exit_code = self._run_seed_with_config(config_path)
        assert exit_code == 0
        seeded_ids = {c["actor_id"] for c in calls}
        assert VENDOR_ID in seeded_ids
        assert CASE_ACTOR_ID in seeded_ids

    def test_seed_call_count_equals_one_local_plus_peers(self):
        """Each seed run should call seed_actor once per actor (1 local + 4 peers)."""
        for filename in (
            "seed-finder.json",
            "seed-vendor.json",
            "seed-coordinator.json",
            "seed-case-actor.json",
            "seed-vendor2.json",
        ):
            config_path = _SEED_CONFIGS_DIR / filename
            calls, exit_code = self._run_seed_with_config(config_path)
            assert exit_code == 0, f"{filename}: exit code {exit_code}"
            assert len(calls) == 5, (
                f"{filename}: expected 5 seed_actor calls "
                f"(1 local + 4 peers), got {len(calls)}"
            )
