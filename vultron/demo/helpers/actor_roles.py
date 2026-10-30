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
"""Per-scenario actor role declarations (DEMOCI-11-011, DEMOCI-11-020).

A demo scenario runs N actors, each in its own container of the fixed cast
(:mod:`vultron.demo.helpers.cast`).  :class:`ActorRole` is where a scenario
seats each of its actors, **once**: the actor's name in the scenario, the cast
container it runs in, and whether it also takes a ``--<name>-id`` option.  The
container's URL, env var, local port and actor id all come from the cast slot,
so no scenario declares its own (DEMOCI-11-020).

Both consumers read the same list:

* ``vultron/demo/cli.py``'s command factory turns the list into that scenario's
  click options, so a registered scenario cannot be missing a sub-command and a
  sub-command cannot be hand-declared (DEMOCI-11-011);
* the module's own ``*_BASE_URL`` constants are :attr:`ActorRole.url` values,
  and its ``main()`` resolves each actor's id with
  :meth:`ActorRole.resolve_id`.

The declaration is deliberately **not** carried by the ``@scenario`` decorator:
DEMOCI-11-001 confines that decorator to facts the registry can derive
everything else from, and per-scenario option metadata is not one of them.  The
pattern instead follows ``ActorSession`` (DEMOMA-26) — a frozen value object
whose shape is pinned to its call site by a ratchet, here
``test/architecture/test_scenario_roles_match_main_kwargs.py``.

Implementation guidance: ``notes/demo-scenario-registry.md``.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from vultron.demo.helpers.cast import (
    CASE_ACTOR,
    ROLE_OF_SLOT,
    ContainerSlot,
)
from vultron.enums.roles import CVDRole
from vultron.errors import DemoActorRoleError

#: Role name spelling: lowercase alphanumerics separated by single hyphens, with
#: a leading letter.  ``name`` is the stem of both option flags and both
#: ``main()`` parameters, so a name that cannot round-trip into a click flag
#: *and* a Python identifier is rejected here rather than producing an
#: unreachable option later.
#:
#: The leading letter is what makes the identifier half true: ``"2nd-vendor"`` is
#: a fine click flag but yields ``2nd_vendor_url``, which no ``main()`` can
#: declare — the failure would surface in the ratchet rather than at the
#: declaration site this check exists to guard.
#:
#: Anchored with ``\Z`` rather than ``$``, which also matches before a trailing
#: newline: ``"reporter\n"`` would pass and then yield a ``--reporter\n-url`` flag.
_NAME_RE = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*\Z")


@dataclass(frozen=True, slots=True)
class ActorRole:
    """One scenario actor, the cast container it runs in, and its CLI options.

    Frozen because the CLI reads ``url`` at decoration time and the scenario's
    ``main()`` reads the derived ``*_BASE_URL`` constant at call time; a role
    whose slot could be changed between those two reads would give the option
    default and the fallback different containers.
    """

    #: Flag stem, e.g. ``"reporter"``, ``"c1"``, ``"case-actor"``.  Yields
    #: ``--<name>-url`` / ``--<name>-id`` and ``<name_>_url`` / ``<name_>_id``.
    name: str
    #: The cast container this actor runs in.  Its env var, local port and
    #: actor id are the slot's, never the scenario's (DEMOCI-11-020).
    slot: ContainerSlot
    #: Who the actor is in this scenario, for ``--help`` text, e.g.
    #: ``"C1 (Coordinator1)"``.
    title: str
    #: Whether this actor also takes a ``--<name>-id`` option, which overrides
    #: the slot's actor id.
    has_id: bool = False

    def __post_init__(self) -> None:
        if not _NAME_RE.match(self.name) or not self.param_stem.isidentifier():
            raise DemoActorRoleError(
                f"actor role name {self.name!r} is not a valid option stem; "
                "expected lowercase alphanumerics separated by single hyphens "
                "and starting with a letter (e.g. 'case-actor'). Both option "
                "flags and both main() parameter names derive from it, and "
                f"{self.param_stem!r} is not a Python identifier."
            )
        if not isinstance(self.slot, ContainerSlot):
            raise DemoActorRoleError(
                f"actor role {self.name!r} runs in {self.slot!r}, which is not "
                "a cast container; seat it in a slot from "
                "vultron.demo.helpers.cast (DEMOCI-11-020)."
            )
        if not isinstance(self.title, str) or not self.title.strip():
            raise DemoActorRoleError(
                f"actor role {self.name!r} has an empty title; its --help "
                "text would name no one."
            )

    @property
    def url_env(self) -> str:
        """Env var naming this actor's container: the slot's."""
        return self.slot.url_env

    @property
    def default_url(self) -> str:
        """Base URL used when :attr:`url_env` is unset: the slot's local port."""
        return self.slot.default_url

    @property
    def url(self) -> str:
        """This actor's container base URL: :attr:`url_env` or the default.

        Read once per consumer — at click decoration time for the option
        default, and at module import time for the scenario's ``*_BASE_URL``
        constant.
        """
        return self.slot.url

    @property
    def plays(self) -> CVDRole | None:
        """The role this actor holds from the start, or ``None``.

        A cast member with a fixed role (slots 0 to 2) plays it in every
        scenario.  A character actor returns ``None``: its role comes from the
        act that seats it, not from its container (DEMOCI-11-021).
        """
        return ROLE_OF_SLOT.get(self.slot.name)

    def resolve_id(self, base_url: str, override: str | None = None) -> str:
        """This actor's id: *override*, or the one its container serves.

        Args:
            base_url: The container's resolved base URL.
            override: A ``--<name>-id`` value, when the caller passed one.
        """
        return override or self.slot.actor_id(base_url)

    @property
    def url_help(self) -> str:
        """``--help`` text for the ``--<name>-url`` option."""
        return (
            f"Base URL of the {self.title} container API "
            f"(container {self.slot.name}; env: {self.url_env})."
        )

    @property
    def id_help(self) -> str | None:
        """``--help`` text for the ``--<name>-id`` option, if it has one."""
        if not self.has_id:
            return None
        return (
            f"Full URI for the {self.title} actor (default: "
            f"<url>/actors/{self.slot.name})."
        )

    @property
    def url_option(self) -> str:
        """The ``--<name>-url`` click flag."""
        return f"--{self.name}-url"

    @property
    def id_option(self) -> str:
        """The ``--<name>-id`` click flag."""
        return f"--{self.name}-id"

    @property
    def param_stem(self) -> str:
        """:attr:`name` as a Python identifier fragment (hyphens → underscores)."""
        return self.name.replace("-", "_")

    @property
    def url_param(self) -> str:
        """The ``main()`` keyword this role's URL is passed as."""
        return f"{self.param_stem}_url"

    @property
    def id_param(self) -> str:
        """The ``main()`` keyword this role's actor id is passed as."""
        return f"{self.param_stem}_id"


def role_map(roles: Sequence[ActorRole]) -> dict[str, ActorRole]:
    """Index *roles* by :attr:`ActorRole.name`.

    Used by a scenario module to derive its ``*_BASE_URL`` constants from the
    same list the CLI reads, so each binding is declared once.

    Args:
        roles: The scenario's role list, in ``main()`` parameter order.

    Returns:
        A mapping from role name to role.

    Raises:
        DemoActorRoleError: If *roles* is empty, if two roles share a name, or
            if two roles run in the same cast container.
    """
    if not roles:
        raise DemoActorRoleError(
            "a scenario declares at least one actor role; an empty ROLES list "
            "generates a sub-command with no container options."
        )

    by_name: dict[str, ActorRole] = {}
    for role in roles:
        if role.name in by_name:
            raise DemoActorRoleError(
                f"actor role {role.name!r} is declared twice; the second "
                "declaration would generate a duplicate --"
                f"{role.name}-url option and click would keep only one."
            )
        by_name[role.name] = role

    # One actor per container (ADR-0042): a second role in an occupied slot is
    # a copy-pasted declaration that was half edited, the likeliest mistake
    # when adding an actor to an existing scenario.
    seen_slot: dict[str, str] = {}
    for role in roles:
        owner = seen_slot.get(role.slot.name)
        if owner is not None:
            raise DemoActorRoleError(
                f"actor roles {owner!r} and {role.name!r} both run in cast "
                f"container {role.slot.name!r}; one actor runs per container. "
                "Seat the second one in a free member of the cast "
                "(vultron.demo.helpers.cast)."
            )
        seen_slot[role.slot.name] = role.name

    return by_name


def role_kwarg_names(roles: Sequence[ActorRole]) -> tuple[str, ...]:
    """Return the ``main()`` keyword names *roles* imply, in order.

    All URL parameters in role order, then all id parameters in role order —
    the order every scenario ``main()`` already declares them in, and the order
    the CLI factory emits options in.  Stated once here so the factory and the
    ratchet cannot disagree about it (a ratchet that re-derived the expected
    order would be testing its own copy of the rule).

    Args:
        roles: The scenario's role list.

    Returns:
        The expected keyword parameter names, excluding ``skip_health_check``.
    """
    return tuple(role.url_param for role in roles) + tuple(
        role.id_param for role in roles if role.has_id
    )


def case_actor_role(*, has_id: bool = False) -> ActorRole:
    """The ``case-actor`` role every Docker scenario declares (#1876).

    Every scenario proposes its cases to the dedicated case-actor container
    (CP-08-008, DEMOMA-06-004), so each has this role, in the
    :data:`~vultron.demo.helpers.cast.CASE_ACTOR` slot.  Scenarios differ only
    in whether they take a ``--case-actor-id`` (the handoff scenarios do, per
    DEMOMA-14-008).

    Args:
        has_id: Whether the scenario also takes ``--case-actor-id``.
    """
    return ActorRole(
        name="case-actor",
        slot=CASE_ACTOR,
        title="dedicated CaseActor",
        has_id=has_id,
    )


__all__ = [
    "ActorRole",
    "case_actor_role",
    "role_kwarg_names",
    "role_map",
]
