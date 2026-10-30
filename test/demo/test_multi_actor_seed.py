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

"""Tests for the fixed cast's seed configuration (D5-1-G3, DEMOCI-11-020).

Verifies that the pre-built seed config YAML files in docker/seed-configs/ are
valid SeedConfig schemas, that each one seeds the actor its container hosts,
and that together they describe a symmetric peer mesh.  Parametrized over the
cast rather than written per file: every member's config has the same shape, so
a per-file copy would be eleven ways to miss the same mistake.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from vultron.demo.cli import main
from vultron.demo.helpers.cast import (
    ALL_SLOTS,
    CASE_ACTOR,
    CAST,
    ContainerSlot,
)
from vultron.demo.seed_config import SeedConfig
from vultron.demo.utils import DataLayerClient
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.base.objects.actors import as_Actor

# Path to the docker/seed-configs/ directory (relative to project root).
_REPO_ROOT = Path(__file__).parents[2]
_SEED_CONFIGS_DIR = _REPO_ROOT / "docker" / "seed-configs"

#: The ActivityStreams actor type each container seeds itself as.  A character
#: actor is an ``Organization`` because that is the neutral default; the type is
#: not a CVD role, which comes from the act that seats the actor.
_ACTOR_TYPES = {
    CAST[0].name: "Person",
    CAST[1].name: "Organization",
    CAST[2].name: "Service",
    CAST[3].name: "Organization",
    CAST[4].name: "Organization",
    CASE_ACTOR.name: "Service",
}

_SLOT_IDS = [slot.name for slot in ALL_SLOTS]


def _config_path(slot: ContainerSlot) -> Path:
    return _SEED_CONFIGS_DIR / f"seed-{slot.name}.yaml"


def _load_seed_config(slot: ContainerSlot) -> SeedConfig:
    """Load and validate the pre-built seed config of one cast container."""
    return SeedConfig.from_file(str(_config_path(slot)))


def _own_id(slot: ContainerSlot) -> str:
    """The actor id the container at *slot* hosts on the compose network."""
    return slot.actor_id(slot.compose_url)


class TestEachSeedConfig:
    """One config per cast container, seeding that container's own actor."""

    @pytest.mark.parametrize("slot", ALL_SLOTS, ids=_SLOT_IDS)
    def test_file_exists_and_validates(self, slot: ContainerSlot) -> None:
        assert _config_path(slot).exists()
        assert isinstance(_load_seed_config(slot), SeedConfig)

    @pytest.mark.parametrize("slot", ALL_SLOTS, ids=_SLOT_IDS)
    def test_local_actor_id_is_the_slots(self, slot: ContainerSlot) -> None:
        """One actor id per container, in every scenario (DEMOCI-11-020)."""
        assert _load_seed_config(slot).local_actor.id_ == _own_id(slot)

    @pytest.mark.parametrize("slot", ALL_SLOTS, ids=_SLOT_IDS)
    def test_local_actor_type(self, slot: ContainerSlot) -> None:
        cfg = _load_seed_config(slot)
        assert cfg.local_actor.actor_type == _ACTOR_TYPES[slot.name]

    @pytest.mark.parametrize("slot", ALL_SLOTS, ids=_SLOT_IDS)
    def test_peers_are_every_other_member(self, slot: ContainerSlot) -> None:
        """Each container knows the rest of the cast and not itself.

        A missing peer is how a container ends up unable to address an actor it
        has to message, with no discovery step to fall back on.
        """
        peer_ids = {peer.id_ for peer in _load_seed_config(slot).peers}
        assert peer_ids == {
            _own_id(other) for other in ALL_SLOTS if other is not slot
        }

    @pytest.mark.parametrize("slot", ALL_SLOTS, ids=_SLOT_IDS)
    def test_every_id_is_a_full_actor_uri(self, slot: ContainerSlot) -> None:
        cfg = _load_seed_config(slot)
        ids = [cfg.local_actor.id_, *(peer.id_ for peer in cfg.peers)]
        for actor_id in ids:
            assert actor_id is not None
            assert actor_id.startswith("http://")
            assert "/actors/" in actor_id


class TestSeedConfigCrossConsistency:
    """The configs together must describe one consistent peer mesh."""

    def test_the_mesh_is_symmetric(self) -> None:
        """A knows B and B knows A, for every pair in the cast."""
        peers = {
            slot: {peer.id_ for peer in _load_seed_config(slot).peers}
            for slot in ALL_SLOTS
        }
        for slot, known in peers.items():
            for other in ALL_SLOTS:
                if other is slot:
                    continue
                assert _own_id(other) in known
                assert _own_id(slot) in peers[other]

    def test_no_seed_config_names_a_cvd_role(self) -> None:
        """A role-named id would tie a role-neutral container to one part.

        Over every CVD role rather than the three retired slugs, so a new
        role-named id cannot slip in behind the list (DEMOCI-11-027).
        """
        for slot in ALL_SLOTS:
            text = _config_path(slot).read_text(encoding="utf-8")
            for role in CVDRole:
                assert f"/actors/{role.value}" not in text

    def test_every_config_calls_a_container_the_same_thing(self) -> None:
        """One display name per container across the configs.

        The name is what the devlogs and the UI show, so one file calling
        ``actor2`` the Coordinator while another calls it the Vendor would
        label the same actor two ways with nothing to catch it.
        """
        claimed: dict[str, set[str]] = {slot.name: set() for slot in ALL_SLOTS}
        by_id = {_own_id(slot): slot.name for slot in ALL_SLOTS}
        for slot in ALL_SLOTS:
            cfg = _load_seed_config(slot)
            claimed[slot.name].add(cfg.local_actor.name)
            for peer in cfg.peers:
                claimed[by_id[peer.id_]].add(peer.name)
        for name, names in claimed.items():
            assert len(names) == 1, f"{name} is called {sorted(names)}"

    def test_the_fixed_role_slots_are_named_for_their_role(self) -> None:
        """Slots 0 to 2 play one part in every scenario, so they may say so.

        A character actor may not: its name is the slot's, because its role
        comes from the act that seats it (DEMOCI-11-021).
        """
        names = {
            slot.name: _load_seed_config(slot).local_actor.name
            for slot in ALL_SLOTS
        }
        assert names == {
            CAST[0].name: "Reporter",
            CAST[1].name: "Vendor",
            CAST[2].name: "Coordinator",
            CAST[3].name: "Actor3",
            CAST[4].name: "Actor4",
            CASE_ACTOR.name: "CaseActor",
        }


class TestSeedCLIWithDeterministicId:
    """Verify that the seed CLI honours the fixed actor ID from seed configs."""

    def _run_seed_with_config(
        self, config_file: Path
    ) -> tuple[list[dict], list[dict], int]:
        calls: list[dict] = []
        peer_calls: list[dict] = []

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

        def _capturing_peer(
            client: DataLayerClient,
            local_actor_id: str,
            peer_id: str,
            name: str,
            actor_type: str = "Organization",
        ) -> as_Actor:
            peer_calls.append(
                {
                    "local_actor_id": local_actor_id,
                    "peer_id": peer_id,
                    "name": name,
                    "actor_type": actor_type,
                }
            )
            return as_Actor.model_validate({"id": peer_id, "name": name})

        runner = CliRunner()
        with (
            patch(
                "vultron.demo.cli.seed_actor",
                MagicMock(side_effect=_capturing_seed),
            ),
            patch(
                "vultron.demo.cli.seed_peer",
                MagicMock(side_effect=_capturing_peer),
            ),
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
        return calls, peer_calls, result.exit_code

    @pytest.mark.parametrize("slot", ALL_SLOTS, ids=_SLOT_IDS)
    def test_seed_uses_the_slots_actor_id(self, slot: ContainerSlot) -> None:
        calls, _peer_calls, exit_code = self._run_seed_with_config(
            _config_path(slot)
        )
        assert exit_code == 0
        assert [call["actor_id"] for call in calls] == [_own_id(slot)]

    @pytest.mark.parametrize("slot", ALL_SLOTS, ids=_SLOT_IDS)
    def test_seed_registers_every_other_member_as_a_peer(
        self, slot: ContainerSlot
    ) -> None:
        """One ``seed_actor`` call for the local actor, one per peer."""
        calls, peer_calls, exit_code = self._run_seed_with_config(
            _config_path(slot)
        )
        assert exit_code == 0
        assert len(calls) == 1
        assert {call["peer_id"] for call in peer_calls} == {
            _own_id(other) for other in ALL_SLOTS if other is not slot
        }


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
        transition so the validate_report semanticType appears in the case-actor
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
