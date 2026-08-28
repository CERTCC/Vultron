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

Verifies that the pre-built seed config YAML files in docker/seed-configs/
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
VENDOR2_ID = "http://actor5:7999/api/v2/actors/vendor2"
VENDOR_DEPLOYER_ID = "http://actor6:7999/api/v2/actors/vendor-deployer"
COORDINATOR2_ID = "http://actor5:7999/api/v2/actors/coordinator2"

# Path to the docker/seed-configs/ directory (relative to project root).
_REPO_ROOT = Path(__file__).parents[2]
_SEED_CONFIGS_DIR = _REPO_ROOT / "docker" / "seed-configs"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_seed_config(filename: str) -> SeedConfig:
    """Load and validate one of the pre-built seed config YAML files."""
    path = _SEED_CONFIGS_DIR / filename
    return SeedConfig.from_file(str(path))


def _all_expected_peer_ids(own_id: str) -> set[str]:
    """Return the set of peer IDs expected for a given actor."""
    all_ids = {FINDER_ID, VENDOR_ID, COORDINATOR_ID, CASE_ACTOR_ID, VENDOR2_ID}
    return all_ids - {own_id}


# ---------------------------------------------------------------------------
# Tests for seed-finder.yaml
# ---------------------------------------------------------------------------


class TestSeedFinderConfig:
    def test_file_exists(self):
        assert (_SEED_CONFIGS_DIR / "seed-finder.yaml").exists()

    def test_valid_seed_config_schema(self):
        cfg = _load_seed_config("seed-finder.yaml")
        assert isinstance(cfg, SeedConfig)

    def test_local_actor_id_is_deterministic(self):
        cfg = _load_seed_config("seed-finder.yaml")
        assert cfg.local_actor.id_ == FINDER_ID

    def test_local_actor_type_is_person(self):
        cfg = _load_seed_config("seed-finder.yaml")
        assert cfg.local_actor.actor_type == "Person"

    def test_local_actor_name(self):
        cfg = _load_seed_config("seed-finder.yaml")
        assert cfg.local_actor.name == "Finder"

    def test_peers_include_vendor_and_case_actor(self):
        cfg = _load_seed_config("seed-finder.yaml")
        peer_ids = {p.id_ for p in cfg.peers}
        assert peer_ids == _all_expected_peer_ids(FINDER_ID)

    def test_peer_ids_are_deterministic(self):
        cfg = _load_seed_config("seed-finder.yaml")
        peer_ids = {p.id_ for p in cfg.peers}
        assert VENDOR_ID in peer_ids
        assert CASE_ACTOR_ID in peer_ids
        assert COORDINATOR_ID in peer_ids
        assert VENDOR2_ID in peer_ids


# ---------------------------------------------------------------------------
# Tests for seed-vendor.yaml
# ---------------------------------------------------------------------------


class TestSeedVendorConfig:
    def test_file_exists(self):
        assert (_SEED_CONFIGS_DIR / "seed-vendor.yaml").exists()

    def test_valid_seed_config_schema(self):
        cfg = _load_seed_config("seed-vendor.yaml")
        assert isinstance(cfg, SeedConfig)

    def test_local_actor_id_is_deterministic(self):
        cfg = _load_seed_config("seed-vendor.yaml")
        assert cfg.local_actor.id_ == VENDOR_ID

    def test_local_actor_type_is_organization(self):
        cfg = _load_seed_config("seed-vendor.yaml")
        assert cfg.local_actor.actor_type == "Organization"

    def test_local_actor_name(self):
        cfg = _load_seed_config("seed-vendor.yaml")
        assert cfg.local_actor.name == "Vendor"

    def test_peers_include_finder_and_case_actor(self):
        cfg = _load_seed_config("seed-vendor.yaml")
        peer_ids = {p.id_ for p in cfg.peers}
        assert peer_ids == _all_expected_peer_ids(VENDOR_ID)

    def test_peer_ids_are_deterministic(self):
        cfg = _load_seed_config("seed-vendor.yaml")
        peer_ids = {p.id_ for p in cfg.peers}
        assert FINDER_ID in peer_ids
        assert CASE_ACTOR_ID in peer_ids
        assert COORDINATOR_ID in peer_ids
        assert VENDOR2_ID in peer_ids


# ---------------------------------------------------------------------------
# Tests for seed-case-actor.yaml
# ---------------------------------------------------------------------------


class TestSeedCaseActorConfig:
    def test_file_exists(self):
        assert (_SEED_CONFIGS_DIR / "seed-case-actor.yaml").exists()

    def test_valid_seed_config_schema(self):
        cfg = _load_seed_config("seed-case-actor.yaml")
        assert isinstance(cfg, SeedConfig)

    def test_local_actor_id_is_deterministic(self):
        cfg = _load_seed_config("seed-case-actor.yaml")
        assert cfg.local_actor.id_ == CASE_ACTOR_ID

    def test_local_actor_type_is_service(self):
        cfg = _load_seed_config("seed-case-actor.yaml")
        assert cfg.local_actor.actor_type == "Service"

    def test_local_actor_name(self):
        cfg = _load_seed_config("seed-case-actor.yaml")
        assert cfg.local_actor.name == "CaseActor"

    def test_peers_include_finder_and_vendor(self):
        cfg = _load_seed_config("seed-case-actor.yaml")
        peer_ids = {p.id_ for p in cfg.peers}
        assert peer_ids == _all_expected_peer_ids(CASE_ACTOR_ID)

    def test_peer_ids_are_deterministic(self):
        cfg = _load_seed_config("seed-case-actor.yaml")
        peer_ids = {p.id_ for p in cfg.peers}
        assert FINDER_ID in peer_ids
        assert VENDOR_ID in peer_ids
        assert COORDINATOR_ID in peer_ids
        assert VENDOR2_ID in peer_ids


# ---------------------------------------------------------------------------
# Tests for seed-actor6.yaml (FCVCV VendorDeployer — DEMOMA-19-001)
# ---------------------------------------------------------------------------


class TestSeedActor6Config:
    def test_file_exists(self):
        assert (_SEED_CONFIGS_DIR / "seed-actor6.yaml").exists()

    def test_valid_seed_config_schema(self):
        cfg = _load_seed_config("seed-actor6.yaml")
        assert isinstance(cfg, SeedConfig)

    def test_local_actor_id_is_deterministic(self):
        cfg = _load_seed_config("seed-actor6.yaml")
        assert cfg.local_actor.id_ == VENDOR_DEPLOYER_ID

    def test_local_actor_type_is_organization(self):
        cfg = _load_seed_config("seed-actor6.yaml")
        assert cfg.local_actor.actor_type == "Organization"

    def test_local_actor_name(self):
        cfg = _load_seed_config("seed-actor6.yaml")
        assert cfg.local_actor.name == "VendorDeployer"

    def test_peers_include_finder_vendor_coordinator_coordinator2_case_actor(
        self,
    ):
        cfg = _load_seed_config("seed-actor6.yaml")
        peer_ids = {p.id_ for p in cfg.peers}
        assert FINDER_ID in peer_ids
        assert VENDOR_ID in peer_ids
        assert COORDINATOR_ID in peer_ids
        assert COORDINATOR2_ID in peer_ids
        assert CASE_ACTOR_ID in peer_ids

    def test_does_not_list_itself_as_peer(self):
        cfg = _load_seed_config("seed-actor6.yaml")
        peer_ids = {p.id_ for p in cfg.peers}
        assert VENDOR_DEPLOYER_ID not in peer_ids

    def test_has_exactly_five_peers(self):
        cfg = _load_seed_config("seed-actor6.yaml")
        assert len(cfg.peers) == 5, f"expected 5 peers, got {len(cfg.peers)}"


# ---------------------------------------------------------------------------
# Cross-config consistency tests
# ---------------------------------------------------------------------------


class TestSeedConfigCrossConsistency:
    """All five original configs must describe a consistent peer mesh.

    actor6 (seed-actor6.yaml) is excluded here: it has 5 peers (not 4) and the
    other five actors do not yet list actor6 as a peer — that cross-registration
    is deferred to DEMOMA-19-002 (seed_containers_fcvcv function).
    """

    def test_all_configs_load_successfully(self):
        # actor6 excluded — see class docstring (DEMOMA-19-002 pending)
        for filename in (
            "seed-finder.yaml",
            "seed-vendor.yaml",
            "seed-coordinator.yaml",
            "seed-case-actor.yaml",
            "seed-actor5.yaml",
        ):
            cfg = _load_seed_config(filename)
            assert cfg is not None

    def test_each_config_has_exactly_four_peers(self):
        for filename in (
            "seed-finder.yaml",
            "seed-vendor.yaml",
            "seed-coordinator.yaml",
            "seed-case-actor.yaml",
            "seed-actor5.yaml",
        ):
            cfg = _load_seed_config(filename)
            assert (
                len(cfg.peers) == 4
            ), f"{filename}: expected 4 peers, got {len(cfg.peers)}"

    def test_no_config_lists_itself_as_peer(self):
        for filename, own_id in [
            ("seed-finder.yaml", FINDER_ID),
            ("seed-vendor.yaml", VENDOR_ID),
            ("seed-coordinator.yaml", COORDINATOR_ID),
            ("seed-case-actor.yaml", CASE_ACTOR_ID),
            ("seed-actor5.yaml", VENDOR2_ID),
        ]:
            cfg = _load_seed_config(filename)
            peer_ids = {p.id_ for p in cfg.peers}
            assert (
                own_id not in peer_ids
            ), f"{filename}: actor listed as its own peer"

    def test_every_actor_appears_as_peer_in_others(self):
        """Verify the peer mesh is symmetric: A knows B, B knows A."""
        configs = {
            FINDER_ID: _load_seed_config("seed-finder.yaml"),
            VENDOR_ID: _load_seed_config("seed-vendor.yaml"),
            COORDINATOR_ID: _load_seed_config("seed-coordinator.yaml"),
            CASE_ACTOR_ID: _load_seed_config("seed-case-actor.yaml"),
            VENDOR2_ID: _load_seed_config("seed-actor5.yaml"),
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
        config_path = _SEED_CONFIGS_DIR / "seed-finder.yaml"
        calls, exit_code = self._run_seed_with_config(config_path)
        assert exit_code == 0
        local_call = next((c for c in calls if c["name"] == "Finder"), None)
        assert local_call is not None
        assert local_call["actor_id"] == FINDER_ID

    def test_vendor_seed_uses_deterministic_id(self):
        config_path = _SEED_CONFIGS_DIR / "seed-vendor.yaml"
        calls, exit_code = self._run_seed_with_config(config_path)
        assert exit_code == 0
        local_call = next((c for c in calls if c["name"] == "Vendor"), None)
        assert local_call is not None
        assert local_call["actor_id"] == VENDOR_ID

    def test_case_actor_seed_uses_deterministic_id(self):
        config_path = _SEED_CONFIGS_DIR / "seed-case-actor.yaml"
        calls, exit_code = self._run_seed_with_config(config_path)
        assert exit_code == 0
        local_call = next((c for c in calls if c["name"] == "CaseActor"), None)
        assert local_call is not None
        assert local_call["actor_id"] == CASE_ACTOR_ID

    def test_finder_seed_registers_all_peers(self):
        config_path = _SEED_CONFIGS_DIR / "seed-finder.yaml"
        calls, exit_code = self._run_seed_with_config(config_path)
        assert exit_code == 0
        seeded_ids = {c["actor_id"] for c in calls}
        assert VENDOR_ID in seeded_ids
        assert CASE_ACTOR_ID in seeded_ids

    def test_seed_call_count_equals_one_local_plus_peers(self):
        """Each seed run should call seed_actor once per actor (1 local + 4 peers)."""
        for filename in (
            "seed-finder.yaml",
            "seed-vendor.yaml",
            "seed-coordinator.yaml",
            "seed-case-actor.yaml",
            "seed-actor5.yaml",
        ):
            config_path = _SEED_CONFIGS_DIR / filename
            calls, exit_code = self._run_seed_with_config(config_path)
            assert exit_code == 0, f"{filename}: exit code {exit_code}"
            assert len(calls) == 5, (
                f"{filename}: expected 5 seed_actor calls "
                f"(1 local + 4 peers), got {len(calls)}"
            )

    def test_vendor_deployer_seed_uses_deterministic_id(self):
        config_path = _SEED_CONFIGS_DIR / "seed-actor6.yaml"
        calls, exit_code = self._run_seed_with_config(config_path)
        assert exit_code == 0
        local_call = next(
            (c for c in calls if c["name"] == "VendorDeployer"), None
        )
        assert local_call is not None
        assert local_call["actor_id"] == VENDOR_DEPLOYER_ID

    def test_actor6_seed_call_count_is_six(self):
        """actor6 has 5 peers (not 4), so CLI must make 6 seed_actor calls."""
        config_path = _SEED_CONFIGS_DIR / "seed-actor6.yaml"
        calls, exit_code = self._run_seed_with_config(config_path)
        assert exit_code == 0
        assert len(calls) == 6, (
            f"seed-actor6.yaml: expected 6 seed_actor calls "
            f"(1 local + 5 peers), got {len(calls)}"
        )


# ---------------------------------------------------------------------------
# Regression tests for _seed_vendor_participant RM-state pre-seeding (issue #2273)
# ---------------------------------------------------------------------------


class TestSeedVendorParticipantRMState:
    """_seed_vendor_participant must not pre-seed any RM state.

    RM transitions (RECEIVED → VALID → ACCEPTED) must happen through the
    protocol, not by pre-seeding the DataLayer.  Pre-seeding RM.VALID causes
    ``validate_report`` to never appear in the case-actor ledger because the
    validate-report trigger's short-circuit guard (``CheckRMStateValid``)
    sees the vendor already at VALID and skips the emission path.

    Regression: issue #2273.
    """

    def _call_seed_vendor(self):
        """Call _seed_vendor_participant with a minimal mock case and DL."""
        from unittest.mock import MagicMock

        from vultron.demo.helpers.seeding import _seed_vendor_participant

        case_obj = MagicMock()
        case_obj.id_ = "https://example.org/cases/test-case"
        object.__setattr__(case_obj, "actor_participant_index", {})

        dl = MagicMock()
        dl.create.return_value = None

        vendor_actor_id = "https://vendor/actors/vendor"
        _seed_vendor_participant(case_obj, vendor_actor_id, dl)
        return dl

    def test_vendor_seeded_at_rm_received_not_beyond(self):
        """Vendor must be seeded at RM.RECEIVED — no higher RM state.

        RM.RECEIVED is the minimum needed for validate-report to advance
        RECEIVED → VALID.  In a multi-server deployment this transition comes
        automatically from SubmitReportReceivedUseCase, which creates the
        case participant at RM.RECEIVED when the Offer is processed.  In
        single-server demo mode that round-trip is blocked, so seeding at
        RM.RECEIVED simulates what the protocol would have done.

        RM.VALID must NOT be pre-seeded — validate-report must drive that
        transition so the validate_report eventType appears in the case-actor
        ledger (issue #2273).
        """
        from vultron.core.states.rm import RM

        dl = self._call_seed_vendor()
        created_participant = dl.create.call_args.args[0]
        statuses = getattr(created_participant, "participant_statuses", [])
        rm_states = [ps.rm.state for ps in statuses]
        # Must be seeded at exactly RM.RECEIVED (the minimum for validate-report)
        assert rm_states == [RM.RECEIVED], (
            f"Expected [RM.RECEIVED], got {rm_states!r}. "
            "Vendor must be seeded at RM.RECEIVED only; RM.VALID must come "
            "from validate-report through the protocol (issue #2273)."
        )

    def test_vendor_seeded_without_rm_valid(self):
        """RM.VALID must not be pre-seeded; it must come from validate-report."""
        from vultron.core.states.rm import RM

        dl = self._call_seed_vendor()
        created_participant = dl.create.call_args.args[0]
        rm_states = [
            ps.rm.state
            for ps in getattr(created_participant, "participant_statuses", [])
        ]
        assert RM.VALID not in rm_states, (
            "Must not pre-seed RM.VALID; validate-report must drive this "
            "transition through the protocol (issue #2273)."
        )
