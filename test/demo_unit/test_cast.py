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
"""The fixed cast: one set of containers for the whole scenario tree.

Three agreements are checked here, because each has two sides that can drift:

* **the cast and the compose file** — one service per slot, at the slot's
  address, with the slot's actor id and seed config (DEMOCI-11-020);
* **the cast and each scenario** — every scenario seats its actors in cast
  slots, and the first Reporter, Vendor and Coordinator in slots 0, 1 and 2
  (DEMOCI-11-021);
* **the cast and the scenario names** — a name's leading letters spell the
  roles that join (DEMOCI-11-015), so they say independently of ``ROLES`` which
  fixed roles a scenario seats and how many actors it needs.
"""

from __future__ import annotations

import importlib
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

import pytest
import yaml

from vultron.demo.helpers.actor_roles import ActorRole
from vultron.demo.helpers.cast import (
    ALL_SLOTS,
    CASE_ACTOR,
    CAST,
    CAST_SIZE,
    CHARACTER_SLOTS,
    CONTAINER_PORT,
    COORDINATOR_SLOT,
    FIRST_OF_ROLE,
    REPORTER_SLOT,
    ROLE_OF_SLOT,
    VENDOR_SLOT,
    ContainerSlot,
)
from vultron.demo.scenario.registry import ScenarioSpec, discover_scenarios
from vultron.enums.roles import CVDRole

_REPO_ROOT = Path(__file__).parents[2]
_COMPOSE_FILE = _REPO_ROOT / "docker" / "docker-compose-multi-actor.yml"
_SEED_CONFIGS = _REPO_ROOT / "docker" / "seed-configs"

#: The compose service that runs a scenario and reads the slot URLs.
_RUNNER_SERVICE = "demo-runner"

#: What each letter of a scenario name spells (DEMOCI-11-015).  ``d`` is here
#: for the Deployer so ``rcvd`` needs no edit; it is never a fixed-role slot.
_ROLE_LETTERS = {
    "r": CVDRole.REPORTER,
    "v": CVDRole.VENDOR,
    "c": CVDRole.COORDINATOR,
    "d": CVDRole.DEPLOYER,
}


def _load_compose() -> dict[str, Any]:
    """The multi-actor compose file, parsed."""
    loaded: dict[str, Any] = yaml.safe_load(
        _COMPOSE_FILE.read_text(encoding="utf-8")
    )
    return loaded


def _env(service_name: str) -> dict[str, str]:
    """A compose service's ``environment`` list as a name → value mapping."""
    service = _load_compose()["services"][service_name]
    return dict(
        str(entry).split("=", 1) for entry in service.get("environment", [])
    )


def _roles_of(spec: ScenarioSpec) -> Sequence[ActorRole]:
    """The scenario module's declared role list."""
    module = importlib.import_module(spec.module_name)
    return cast("Sequence[ActorRole]", module.ROLES)


def _joining_roles(name: str) -> list[CVDRole]:
    """The roles a scenario's name says join, in order.

    ``"rcvv-embargo"`` → Reporter, Coordinator, Vendor, Vendor.  Only the
    leading letter group is the grammar; the suffix names the outcome.
    """
    return [_ROLE_LETTERS[letter] for letter in name.split("-", maxsplit=1)[0]]


_SCENARIOS = sorted(discover_scenarios(), key=lambda spec: spec.name)
_SCENARIO_IDS = [spec.name for spec in _SCENARIOS]


class TestCastShape:
    """The cast table itself: distinct containers, in a declared order."""

    def test_the_cast_has_one_slot_per_member(self) -> None:
        assert len(CAST) == CAST_SIZE

    def test_every_slot_has_its_own_name_and_port(self) -> None:
        """Two members sharing an address would share a store."""
        names = [slot.name for slot in ALL_SLOTS]
        ports = [slot.port for slot in ALL_SLOTS]
        assert len(set(names)) == len(names)
        assert len(set(ports)) == len(ports)

    def test_the_fixed_roles_are_the_first_three_slots(self) -> None:
        """Slots 0, 1 and 2 are the Reporter, Vendor and Coordinator."""
        assert FIRST_OF_ROLE[CVDRole.REPORTER] is CAST[0]
        assert FIRST_OF_ROLE[CVDRole.VENDOR] is CAST[1]
        assert FIRST_OF_ROLE[CVDRole.COORDINATOR] is CAST[2]

    def test_character_slots_are_the_rest_of_the_cast(self) -> None:
        """Every member that is not fixed-role is a character actor."""
        assert CAST[3:] == CHARACTER_SLOTS
        assert all(slot.name not in ROLE_OF_SLOT for slot in CHARACTER_SLOTS)

    def test_the_case_actor_is_not_a_cast_member(self) -> None:
        """It plays no CVD role of its own choosing (DEMOMA-06-004)."""
        assert CASE_ACTOR not in CAST
        assert CASE_ACTOR.name not in ROLE_OF_SLOT

    def test_env_var_and_urls_derive_from_the_slot_name(self) -> None:
        """Each address is written once, in the slot."""
        slot = ContainerSlot(name="actor9", port=7999)
        assert slot.url_env == "VULTRON_ACTOR9_BASE_URL"
        assert slot.default_url == "http://localhost:7999/api/v2"
        assert slot.compose_url == f"http://actor9:{CONTAINER_PORT}/api/v2"

    def test_a_hyphenated_slot_name_yields_a_legal_env_var(self) -> None:
        """``case-actor`` → ``VULTRON_CASE_ACTOR_BASE_URL``, not a hyphen."""
        assert CASE_ACTOR.url_env == "VULTRON_CASE_ACTOR_BASE_URL"


class TestComposeMatchesTheCast:
    """The Docker side of the cast table (DEMOCI-11-020)."""

    def test_every_slot_has_a_service(self) -> None:
        services = _load_compose()["services"]
        for slot in ALL_SLOTS:
            assert slot.name in services

    def test_no_extra_actor_service(self) -> None:
        """A service left behind by a rename would seed an unused container."""
        services = set(_load_compose()["services"])
        expected = {slot.name for slot in ALL_SLOTS} | {_RUNNER_SERVICE}
        assert services == expected

    @pytest.mark.parametrize("slot", ALL_SLOTS, ids=lambda s: s.name)
    def test_the_service_serves_its_slots_url(self, slot: ContainerSlot):
        env = _env(slot.name)
        assert env["VULTRON_SERVER__BASE_URL"].rstrip("/") == slot.compose_url

    @pytest.mark.parametrize("slot", ALL_SLOTS, ids=lambda s: s.name)
    def test_the_service_hosts_its_slots_actor(self, slot: ContainerSlot):
        """One actor id per container, the same in every scenario."""
        assert _env(slot.name)["VULTRON_ACTOR_ID"] == slot.actor_id(
            slot.compose_url
        )

    @pytest.mark.parametrize("slot", ALL_SLOTS, ids=lambda s: s.name)
    def test_the_service_names_its_own_seed_config(self, slot: ContainerSlot):
        """And that file seeds the actor the container hosts."""
        configured = _env(slot.name)["VULTRON_SEED_CONFIG"]
        assert configured.endswith(f"seed-{slot.name}.yaml")
        seed_file = _SEED_CONFIGS / f"seed-{slot.name}.yaml"
        seeded = yaml.safe_load(seed_file.read_text(encoding="utf-8"))
        assert seeded["local_actor"]["id"] == slot.actor_id(slot.compose_url)

    def test_no_stray_seed_config(self) -> None:
        """A seed config for a retired container would seed the wrong id."""
        on_disk = {path.name for path in _SEED_CONFIGS.glob("seed-*.yaml")}
        assert on_disk == {f"seed-{slot.name}.yaml" for slot in ALL_SLOTS}

    @pytest.mark.parametrize("slot", ALL_SLOTS, ids=lambda s: s.name)
    def test_no_character_actor_id_names_a_role(self, slot: ContainerSlot):
        """A role-named actor id would make a neutral container role-bound.

        Checked over every slot, not only the character actors: the whole cast
        is role-neutral in its naming, which is what lets two scenarios give
        one container two different parts.
        """
        actor_id = _env(slot.name)["VULTRON_ACTOR_ID"]
        for role in CVDRole:
            assert f"/actors/{role.value}" not in actor_id

    def test_the_runner_names_every_slots_url(self) -> None:
        """``ContainerSlot.url`` reads these, so a missing one falls to
        ``localhost`` and the scenario talks to nothing."""
        env = _env(_RUNNER_SERVICE)
        for slot in ALL_SLOTS:
            assert env[slot.url_env] == slot.compose_url

    def test_the_runner_waits_for_every_slot(self) -> None:
        depends = _load_compose()["services"][_RUNNER_SERVICE]["depends_on"]
        assert set(depends) == {slot.name for slot in ALL_SLOTS}
        for condition in depends.values():
            assert condition == {"condition": "service_healthy"}

    def test_every_slot_has_its_own_volume(self) -> None:
        """A shared volume would leak one container's store into another's."""
        volumes = set(_load_compose()["volumes"])
        assert volumes == {f"{slot.name}-data" for slot in ALL_SLOTS}


class TestScenariosSeatTheCast:
    """Every registered scenario runs on the cast and nothing else."""

    @pytest.mark.parametrize("spec", _SCENARIOS, ids=_SCENARIO_IDS)
    def test_every_actor_runs_in_a_cast_container(self, spec: ScenarioSpec):
        """No scenario declares a container of its own (DEMOCI-11-020)."""
        for role in _roles_of(spec):
            assert role.slot in ALL_SLOTS, (
                f"{spec.name}'s {role.name!r} runs in {role.slot!r}, which is "
                "not a cast container"
            )

    @pytest.mark.parametrize("spec", _SCENARIOS, ids=_SCENARIO_IDS)
    def test_every_scenario_seats_the_case_actor(self, spec: ScenarioSpec):
        slots = [role.slot for role in _roles_of(spec)]
        assert CASE_ACTOR in slots

    @pytest.mark.parametrize("spec", _SCENARIOS, ids=_SCENARIO_IDS)
    def test_the_cast_size_matches_the_scenario_name(self, spec: ScenarioSpec):
        """The name's letters count the actors, so a dropped one shows up."""
        seated = [
            role for role in _roles_of(spec) if role.slot is not CASE_ACTOR
        ]
        assert len(seated) == len(_joining_roles(spec.name))

    @pytest.mark.parametrize("spec", _SCENARIOS, ids=_SCENARIO_IDS)
    @pytest.mark.parametrize(
        "role",
        [CVDRole.REPORTER, CVDRole.VENDOR, CVDRole.COORDINATOR],
        ids=lambda r: r.value,
    )
    def test_the_first_of_each_fixed_role_runs_in_its_slot(
        self, spec: ScenarioSpec, role: CVDRole
    ):
        """Slots 0, 1 and 2 hold the first Reporter, Vendor, Coordinator.

        Read off the scenario's name rather than its ``ROLES``, so the two
        declarations check each other: a scenario whose name says it seats a
        Coordinator must put one in slot 2, and one whose name does not must
        leave that slot empty (``rv`` has no Coordinator).
        """
        in_slot = [
            r.name for r in _roles_of(spec) if r.slot is FIRST_OF_ROLE[role]
        ]
        expected = 1 if role in _joining_roles(spec.name) else 0
        assert len(in_slot) == expected, (
            f"{spec.name} seats {in_slot} in the {role.value} slot; its name "
            f"says it needs {expected}"
        )

    @pytest.mark.parametrize("spec", _SCENARIOS, ids=_SCENARIO_IDS)
    def test_extra_actors_of_a_role_are_character_actors(
        self, spec: ScenarioSpec
    ):
        """A second Vendor or Coordinator takes a character slot.

        Its role comes from the Invite that seats it, so the count of
        character actors is the count of repeated letters in the name
        (DEMOCI-11-021).
        """
        joining = _joining_roles(spec.name)
        repeated = len(joining) - len(set(joining))
        character = [
            role for role in _roles_of(spec) if role.slot in CHARACTER_SLOTS
        ]
        assert len(character) == repeated
        assert all(role.plays is None for role in character)

    @pytest.mark.parametrize("spec", _SCENARIOS, ids=_SCENARIO_IDS)
    def test_the_fixed_role_actors_declare_their_role(
        self, spec: ScenarioSpec
    ):
        """``plays`` agrees with the slot for every seated actor."""
        for role in _roles_of(spec):
            assert role.plays is ROLE_OF_SLOT.get(role.slot.name)

    def test_the_whole_cast_is_used_by_some_scenario(self) -> None:
        """A cast member no scenario seats is a container CI starts for nothing."""
        seated = {role.slot for spec in _SCENARIOS for role in _roles_of(spec)}
        assert seated == set(ALL_SLOTS)


class TestRolesAreSharedBetweenScenarios:
    """The point of the cast: one address per part, across the tree."""

    @pytest.mark.parametrize(
        ("slot", "role"),
        [
            (REPORTER_SLOT, CVDRole.REPORTER),
            (VENDOR_SLOT, CVDRole.VENDOR),
            (COORDINATOR_SLOT, CVDRole.COORDINATOR),
        ],
        ids=lambda value: getattr(value, "name", str(value)),
    )
    def test_one_actor_id_per_part_across_the_tree(
        self, slot: ContainerSlot, role: CVDRole
    ):
        """``rcv``'s ``coordinator`` and ``rcvcv``'s ``c1`` are one actor.

        Differently-named actors of different scenarios resolve to the same
        id, which is what lets their shared opening record the same bytes
        (DEMOCI-11-018).
        """
        ids = {
            actor.resolve_id(slot.compose_url)
            for spec in _SCENARIOS
            for actor in _roles_of(spec)
            if actor.slot is slot
        }
        assert len(ids) == 1
        assert ids == {slot.actor_id(slot.compose_url)}
