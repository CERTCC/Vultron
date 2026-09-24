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
"""Unit tests for the ``ActorRole`` Type Object (DEMOCI-11-011).

``ActorRole`` is what a scenario declares instead of hand-writing a click
option pair plus a matching ``os.environ.get`` call, so the things worth pinning
are the derivations the CLI relies on (flag and parameter spelling, env
resolution) and the malformed declarations that would otherwise produce a
sub-command that runs and does the wrong thing.
"""

from __future__ import annotations

import pytest

from vultron.demo.helpers.actor_roles import (
    ActorRole,
    role_kwarg_names,
    role_map,
)
from vultron.errors import DemoActorRoleError


def _role(**overrides: object) -> ActorRole:
    """Build a valid role, overriding named fields."""
    fields: dict[str, object] = {
        "name": "finder",
        "url_env": "VULTRON_FINDER_BASE_URL",
        "default_url": "http://localhost:7901/api/v2",
        "url_help": "Base URL of the Finder container API.",
    }
    fields.update(overrides)
    return ActorRole(**fields)  # type: ignore[arg-type]


class TestDerivedNames:
    """The flag and parameter spellings the CLI and the ratchet both derive."""

    def test_single_word_name(self) -> None:
        """A one-word name yields matching flags and parameters."""
        role = _role()
        assert role.url_option == "--finder-url"
        assert role.id_option == "--finder-id"
        assert role.url_param == "finder_url"
        assert role.id_param == "finder_id"

    def test_hyphenated_name_keeps_hyphens_in_flags_only(self) -> None:
        """Hyphens survive in the flag and become underscores in the parameter.

        Spelled out on a hyphenated name because that is the only place the two
        conventions differ — a role helper that applied one rule to both would
        still pass every assertion made on ``finder``.
        """
        role = _role(name="case-actor", url_env="VULTRON_CASE_ACTOR_BASE_URL")
        assert role.url_option == "--case-actor-url"
        assert role.id_option == "--case-actor-id"
        assert role.url_param == "case_actor_url"
        assert role.id_param == "case_actor_id"
        assert role.param_stem == "case_actor"


class TestUrlResolution:
    """``url`` is the env var when set and the declared default otherwise."""

    def test_falls_back_to_default_when_env_unset(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An unset env var yields ``default_url``."""
        monkeypatch.delenv("VULTRON_FINDER_BASE_URL", raising=False)
        assert _role().url == "http://localhost:7901/api/v2"

    def test_env_var_wins(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A set env var overrides ``default_url``."""
        monkeypatch.setenv(
            "VULTRON_FINDER_BASE_URL", "http://finder:7999/api/v2"
        )
        assert _role().url == "http://finder:7999/api/v2"

    def test_empty_env_var_is_honoured(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An env var set to the empty string resolves to the empty string.

        Pinned because this is the one place the resolution could plausibly
        differ from what the scenario modules did by hand: ``os.environ.get``
        returns ``""``, while an ``or``-style fallback would silently substitute
        the default and hide a misconfigured compose file.
        """
        monkeypatch.setenv("VULTRON_FINDER_BASE_URL", "")
        assert _role().url == ""


class TestMalformedDeclarations:
    """Declarations that would yield a broken or silently-ignored option."""

    @pytest.mark.parametrize(
        "name",
        [
            "Finder",  # uppercase would not round-trip a flag stem
            "finder_url",  # underscores belong to the parameter, not the flag
            "",
            # `$` also matches before a trailing newline, so an `re.match(r"…$")`
            # would accept this and emit a `--finder\n-url` flag.
            "finder\n",
            "--finder",
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

        Guards the guard — `fcvcv` and both `fccv` scenarios name their actors
        `c1`, `c2`, `v1`, `v2`, so a regex tightened to letters-only would reject
        the shipped declarations.
        """
        assert _role(name="c1").url_param == "c1_url"
        assert _role(name="vendor2").id_param == "vendor2_id"

    @pytest.mark.parametrize("field", ["url_env", "default_url", "url_help"])
    def test_rejects_an_empty_required_field(self, field: str) -> None:
        """A blank env var, default, or help string is refused."""
        with pytest.raises(DemoActorRoleError, match="empty"):
            _role(**{field: "   "})

    def test_rejects_has_id_without_help(self) -> None:
        """An id option with no help text would be undocumented in ``--help``."""
        with pytest.raises(DemoActorRoleError, match="no id_help"):
            _role(has_id=True)

    @pytest.mark.parametrize("id_env", ["", "   "])
    def test_rejects_a_blank_id_env(self, id_env: str) -> None:
        """A blank ``id_env`` looks like an env binding and is never one.

        The factory would pass ``envvar=""`` to click, whose
        ``resolve_envvar_value`` does ``os.environ.get("")`` and always gets
        ``None`` — the same silently-dropped-metadata failure the
        ``has_id``/``id_help`` check catches, and the asymmetry with the
        non-blank checks on ``url_env`` that let it through.
        """
        with pytest.raises(DemoActorRoleError, match="blank id_env"):
            _role(has_id=True, id_help="Deterministic URI.", id_env=id_env)

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("id_help", "Deterministic full URI for the Finder actor."),
            ("id_env", "VULTRON_FINDER_ACTOR_ID"),
        ],
    )
    def test_rejects_id_metadata_without_has_id(
        self, field: str, value: str
    ) -> None:
        """Id metadata on a role with ``has_id=False`` is refused, not ignored.

        The factory emits ``--<name>-id`` only when ``has_id``, so this would
        otherwise leave an author believing the scenario accepts an option it
        does not.
        """
        with pytest.raises(DemoActorRoleError, match="has_id is False"):
            _role(**{field: value})

    def test_is_frozen(self) -> None:
        """A role cannot be mutated after declaration."""
        role = _role()
        with pytest.raises((AttributeError, TypeError)):
            role.default_url = "http://elsewhere/api/v2"  # type: ignore[misc]


class TestRoleMap:
    """``role_map`` is both the lookup and the declared-once guarantee."""

    def test_indexes_by_name(self) -> None:
        """Roles are addressable by name."""
        finder = _role()
        vendor = _role(
            name="vendor",
            url_env="VULTRON_VENDOR_BASE_URL",
            default_url="http://localhost:7902/api/v2",
            url_help="Base URL of the Vendor container API.",
        )
        assert role_map([finder, vendor]) == {
            "finder": finder,
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

    def test_rejects_two_roles_declaring_one_container_slot(self) -> None:
        """A role reading another role's ``url_env`` is refused at declaration.

        Refused here rather than left to a reviewer spotting two identical env
        var names, because the slot names deliberately do not track the role
        names — so a half-edited copy-paste does not look wrong on the page.
        """
        with pytest.raises(DemoActorRoleError, match="container slot"):
            role_map(
                [
                    _role(),
                    _role(name="vendor", url_help="Base URL of the Vendor."),
                ]
            )


class TestRoleKwargNames:
    """The single statement of the option and parameter ordering rule."""

    def test_urls_in_role_order_then_ids_in_role_order(self) -> None:
        """Ids follow every URL, and a role without an id contributes none."""
        roles = [
            _role(has_id=True, id_help="Finder id."),
            _role(
                name="vendor",
                url_env="VULTRON_VENDOR_BASE_URL",
                url_help="Base URL of the Vendor.",
                has_id=True,
                id_help="Vendor id.",
            ),
            _role(
                name="case-actor",
                url_env="VULTRON_CASE_ACTOR_BASE_URL",
                url_help="Base URL of the CaseActor.",
            ),
        ]
        assert role_kwarg_names(roles) == (
            "finder_url",
            "vendor_url",
            "case_actor_url",
            "finder_id",
            "vendor_id",
        )
