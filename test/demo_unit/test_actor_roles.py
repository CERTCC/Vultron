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
"""Unit tests for the ``ActorRole`` Type Object (DEMOCI-11-011, DEMOCI-11-020).

``ActorRole`` is what a scenario declares instead of hand-writing a click
option pair plus a matching ``os.environ.get`` call, so the things worth pinning
are the derivations the CLI relies on (flag and parameter spelling, env
resolution, the actor id) and the malformed declarations that would otherwise
produce a sub-command that runs and does the wrong thing.
"""

from __future__ import annotations

import pytest

from vultron.demo.helpers.actor_roles import (
    ActorRole,
    case_actor_role,
    resolved_actor_ids,
    role_kwarg_names,
    role_map,
)
from vultron.demo.helpers.cast import (
    CASE_ACTOR,
    CAST,
    COORDINATOR_SLOT,
    REPORTER_SLOT,
    VENDOR_SLOT,
)
from vultron.demo.utils import DataLayerClient
from vultron.enums.roles import CVDRole
from vultron.errors import DemoActorRoleError


def _role(**overrides: object) -> ActorRole:
    """Build a valid role, overriding named fields."""
    fields: dict[str, object] = {
        "name": "reporter",
        "slot": REPORTER_SLOT,
        "title": "Reporter",
    }
    fields.update(overrides)
    return ActorRole(**fields)  # type: ignore[arg-type]


class TestDerivedNames:
    """The flag and parameter spellings the CLI and the ratchet both derive."""

    def test_single_word_name(self) -> None:
        """A one-word name yields matching flags and parameters."""
        role = _role()
        assert role.url_option == "--reporter-url"
        assert role.id_option == "--reporter-id"
        assert role.url_param == "reporter_url"
        assert role.id_param == "reporter_id"

    def test_hyphenated_name_keeps_hyphens_in_flags_only(self) -> None:
        """Hyphens survive in the flag and become underscores in the parameter.

        Spelled out on a hyphenated name because that is the only place the two
        conventions differ — a role helper that applied one rule to both would
        still pass every assertion made on ``reporter``.
        """
        role = _role(name="case-actor", slot=CASE_ACTOR)
        assert role.url_option == "--case-actor-url"
        assert role.id_option == "--case-actor-id"
        assert role.url_param == "case_actor_url"
        assert role.id_param == "case_actor_id"
        assert role.param_stem == "case_actor"


class TestSlotDerivations:
    """Everything about the container comes from the cast slot, not the role."""

    def test_url_env_and_default_url_are_the_slots(self) -> None:
        """A role declares no env var and no port of its own (DEMOCI-11-020).

        Spelled out as literals: both properties return the slot's value
        verbatim, so comparing them against the slot could not disagree.
        """
        role = _role(name="c1", slot=COORDINATOR_SLOT, title="C1", has_id=True)
        assert role.url_env == "VULTRON_ACTOR2_BASE_URL"
        assert role.default_url == "http://localhost:7903/api/v2"
        assert role.id_env == "VULTRON_ACTOR2_ACTOR_ID"

    def test_an_id_option_is_env_bound_to_its_container(self) -> None:
        """DEMOMA-14-008 wants the id options env-bound; the slot names it."""
        assert _role(has_id=True).id_env == "VULTRON_ACTOR0_ACTOR_ID"
        assert _role().id_env is None

    def test_two_roles_in_one_slot_share_its_address(self) -> None:
        """Differently-named roles in one slot resolve to the same container.

        The point of the cast: ``rcv``'s ``coordinator`` and ``rcvcv``'s ``c1``
        are the same container, so a shared opening records the same bytes.
        """
        coordinator = _role(name="coordinator", slot=COORDINATOR_SLOT)
        c1 = _role(name="c1", slot=COORDINATOR_SLOT)
        assert coordinator.url_env == "VULTRON_ACTOR2_BASE_URL"
        assert c1.url_env == "VULTRON_ACTOR2_BASE_URL"
        assert coordinator.resolve_id("http://x/api/v2") == c1.resolve_id(
            "http://x/api/v2"
        )

    def test_resolve_id_derives_the_slots_actor(self) -> None:
        """With no override, the id is the one the container serves."""
        role = _role()
        assert (
            role.resolve_id("http://actor0:7999/api/v2")
            == "http://actor0:7999/api/v2/actors/actor0"
        )

    def test_resolve_id_tolerates_a_trailing_slash(self) -> None:
        """A base URL with a trailing slash yields no doubled separator."""
        assert (
            _role().resolve_id("http://actor0:7999/api/v2/")
            == "http://actor0:7999/api/v2/actors/actor0"
        )

    def test_resolve_id_prefers_an_override(self) -> None:
        """A ``--<name>-id`` value wins over the derived id."""
        assert (
            _role().resolve_id("http://actor0:7999/api/v2", "http://other/a")
            == "http://other/a"
        )

    @pytest.mark.parametrize(
        ("slot", "role"),
        [
            (REPORTER_SLOT, CVDRole.REPORTER),
            (VENDOR_SLOT, CVDRole.VENDOR),
            (COORDINATOR_SLOT, CVDRole.COORDINATOR),
        ],
    )
    def test_a_fixed_role_slot_plays_that_role(
        self, slot: object, role: CVDRole
    ) -> None:
        """Cast slots 0 to 2 play the Reporter, Vendor and Coordinator."""
        assert _role(name="x", slot=slot).plays is role

    @pytest.mark.parametrize("slot", [CAST[3], CAST[4], CASE_ACTOR])
    def test_a_character_actor_plays_no_fixed_role(self, slot: object) -> None:
        """A character actor's role comes from the act that seats it.

        ``plays`` is ``None`` rather than a guess, because the scenario gives
        it the role its Invite offers (DEMOCI-11-021).
        """
        assert _role(name="x", slot=slot).plays is None

    def test_help_text_names_the_container_and_the_part(self) -> None:
        """``--help`` says who the actor is and which container it runs in."""
        role = _role(name="v2", slot=CAST[4], title="V2 (VendorDeployer)")
        assert "V2 (VendorDeployer)" in role.url_help
        assert CAST[4].name in role.url_help
        assert CAST[4].url_env in role.url_help

    def test_id_help_is_absent_without_an_id_option(self) -> None:
        """A role with no ``--<name>-id`` offers no help text for one."""
        assert _role().id_help is None
        assert _role(has_id=True).id_help is not None


class TestUrlResolution:
    """``url`` is the slot's env var when set and its local port otherwise."""

    def test_falls_back_to_default_when_env_unset(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An unset env var yields the slot's local URL."""
        monkeypatch.delenv(REPORTER_SLOT.url_env, raising=False)
        assert _role().url == REPORTER_SLOT.default_url

    def test_env_var_wins(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A set env var overrides the slot's local URL."""
        monkeypatch.setenv(REPORTER_SLOT.url_env, "http://actor0:7999/api/v2")
        assert _role().url == "http://actor0:7999/api/v2"

    def test_empty_env_var_is_honoured(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An env var set to the empty string resolves to the empty string.

        Pinned because this is the one place the resolution could plausibly
        differ from what the scenario modules did by hand: ``os.environ.get``
        returns ``""``, while an ``or``-style fallback would silently substitute
        the default and hide a misconfigured compose file.
        """
        monkeypatch.setenv(REPORTER_SLOT.url_env, "")
        assert _role().url == ""


class TestMalformedDeclarations:
    """Declarations that would yield a broken or silently-ignored option."""

    @pytest.mark.parametrize(
        "name",
        [
            "Reporter",  # uppercase would not round-trip a flag stem
            "reporter_url",  # underscores belong to the parameter, not the flag
            "",
            # `$` also matches before a trailing newline, so an `re.match(r"…$")`
            # would accept this and emit a `--reporter\n-url` flag.
            "reporter\n",
            "--reporter",
            # A fine click flag (`--2nd-vendor-url`) whose parameter stem
            # `2nd_vendor_url` no main() can declare — the half of the invariant
            # a flag-only check misses.
            "2nd-vendor",
            "1",
        ],
    )
    def test_rejects_a_malformed_name(self, name: str) -> None:
        """A name that cannot be both a flag stem and an identifier is refused."""
        with pytest.raises(
            DemoActorRoleError, match="not a valid option stem"
        ):
            _role(name=name)

    def test_accepts_a_digit_after_the_first_character(self) -> None:
        """Only a *leading* digit is refused: ``c1``/``v2`` are real role names.

        Guards the guard — `rcvcv` and both `rccv` scenarios name their actors
        `c1`, `c2`, `v1`, `v2`, so a regex tightened to letters-only would reject
        the shipped declarations.
        """
        assert _role(name="c1").url_param == "c1_url"
        assert _role(name="vendor2").id_param == "vendor2_id"

    @pytest.mark.parametrize(
        "slot", ["actor0", "http://actor0:7999/api/v2", None, 0]
    )
    def test_rejects_a_slot_that_is_not_a_cast_container(
        self, slot: object
    ) -> None:
        """A role must be seated in a ``ContainerSlot``, not a name or a URL.

        A string slot would still produce flags and parameters, and fail only
        when the CLI reached for ``slot.url_env`` at decoration time.
        """
        with pytest.raises(DemoActorRoleError, match="not a ContainerSlot"):
            _role(slot=slot)

    @pytest.mark.parametrize("title", ["", "   "])
    def test_rejects_an_empty_title(self, title: str) -> None:
        """A blank title would leave the generated ``--help`` naming no one."""
        with pytest.raises(DemoActorRoleError, match="empty title"):
            _role(title=title)

    def test_is_frozen(self) -> None:
        """A role cannot be mutated after declaration."""
        role = _role()
        with pytest.raises((AttributeError, TypeError)):
            role.slot = VENDOR_SLOT  # type: ignore[misc]


class TestCaseActorRole:
    """Every scenario declares the CaseActor identically (#1876)."""

    def test_sits_in_the_case_actor_slot(self) -> None:
        """The dedicated container, not a cast member."""
        role = case_actor_role()
        assert role.name == "case-actor"
        assert role.slot is CASE_ACTOR
        assert role.plays is None

    def test_takes_an_id_option_only_when_asked(self) -> None:
        """Only the handoff scenarios offer ``--case-actor-id`` (DEMOMA-14-008)."""
        assert case_actor_role().has_id is False
        assert case_actor_role().id_help is None
        assert case_actor_role(has_id=True).id_help is not None


class TestRoleMap:
    """``role_map`` is both the lookup and the declared-once guarantee."""

    def test_indexes_by_name(self) -> None:
        """Roles are addressable by name."""
        reporter = _role()
        vendor = _role(name="vendor", slot=VENDOR_SLOT, title="Vendor")
        assert role_map([reporter, vendor]) == {
            "reporter": reporter,
            "vendor": vendor,
        }

    def test_rejects_an_empty_role_list(self) -> None:
        """A scenario with no roles would get a sub-command with no options."""
        with pytest.raises(
            DemoActorRoleError, match="at least one actor role"
        ):
            role_map([])

    def test_rejects_a_duplicate_name(self) -> None:
        """Two roles with one name would collide as click options."""
        with pytest.raises(DemoActorRoleError, match="declared twice"):
            role_map([_role(), _role()])

    def test_rejects_two_roles_in_one_cast_container(self) -> None:
        """Two actors of one scenario cannot share a container.

        Refused at declaration rather than left to a reviewer spotting the same
        slot twice: a half-edited copy-paste does not look wrong on the page,
        and the two actors would then share one store and one actor id.
        """
        with pytest.raises(DemoActorRoleError, match="cast container"):
            role_map([_role(), _role(name="vendor", title="Vendor")])


class TestRoleKwargNames:
    """The single statement of the option and parameter ordering rule."""

    def test_urls_in_role_order_then_ids_in_role_order(self) -> None:
        """Ids follow every URL, and a role without an id contributes none."""
        roles = [
            _role(has_id=True),
            _role(
                name="vendor", slot=VENDOR_SLOT, title="Vendor", has_id=True
            ),
            case_actor_role(),
        ]
        assert role_kwarg_names(roles) == (
            "reporter_url",
            "vendor_url",
            "case_actor_url",
            "reporter_id",
            "vendor_id",
        )


class TestResolvedActorIds:
    """The one statement of how a ``main()`` resolves its actors' ids."""

    def test_an_override_wins_and_a_missing_one_falls_to_the_slot(
        self,
    ) -> None:
        """The rule all 11 ``main()`` functions share (DEMOMA-17-001)."""
        roles = role_map(
            [
                _role(has_id=True),
                _role(
                    name="vendor",
                    slot=VENDOR_SLOT,
                    title="Vendor",
                    has_id=True,
                ),
            ]
        )
        resolved = resolved_actor_ids(
            roles,
            reporter=(
                DataLayerClient(base_url=REPORTER_SLOT.compose_url),
                None,
            ),
            vendor=(
                DataLayerClient(base_url=VENDOR_SLOT.compose_url),
                "http://elsewhere/api/v2/actors/given",
            ),
        )
        assert resolved == {
            "reporter_id": (
                f"{REPORTER_SLOT.compose_url}/actors/{REPORTER_SLOT.name}"
            ),
            "vendor_id": "http://elsewhere/api/v2/actors/given",
        }

    def test_refuses_a_seat_no_role_declares(self) -> None:
        """A ``main()`` that has drifted from its ``ROLES``."""
        roles = role_map([_role(has_id=True)])
        with pytest.raises(DemoActorRoleError, match="which no actor role"):
            resolved_actor_ids(
                roles,
                vendor=(
                    DataLayerClient(base_url=VENDOR_SLOT.compose_url),
                    None,
                ),
            )

    def test_refuses_a_seat_whose_role_has_no_id_option(self) -> None:
        """Without ``--<name>-id`` the value could only be the slot's own."""
        roles = role_map([_role()])
        with pytest.raises(DemoActorRoleError, match="has_id=False"):
            resolved_actor_ids(
                roles,
                reporter=(
                    DataLayerClient(base_url=REPORTER_SLOT.compose_url),
                    None,
                ),
            )
