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
"""Per-scenario actor role declarations (DEMOCI-11-011).

A demo scenario runs N actors, each in its own container.  Three facts about
each of them are ad hoc per scenario and derivable from nothing:

* which ``VULTRON_*_BASE_URL`` env var names that actor's container — the URL
  options key to **physical container slots, not roles**, so ``fccv-handoff``'s
  ``--c1-url`` reads ``VULTRON_VENDOR_BASE_URL`` while ``fccv-extension``'s
  reads ``VULTRON_COORDINATOR_BASE_URL``;
* the fallback port when that env var is unset;
* whether the actor also takes a ``--<name>-id`` option, and whether *that*
  option has an env binding (only ``fcvcv`` binds ids to env vars).

:class:`ActorRole` is where a scenario declares them, **once**.  Both consumers
read the same list:

* ``vultron/demo/cli.py``'s command factory turns the list into that scenario's
  click options, so a registered scenario cannot be missing a sub-command and a
  sub-command cannot be hand-declared (DEMOCI-11-011);
* the module's own ``*_BASE_URL`` constants are :attr:`ActorRole.url` values, so
  the env-var/default pair is written in exactly one place.

The declaration is deliberately **not** carried by the ``@scenario`` decorator:
DEMOCI-11-001 confines that decorator to facts the registry can derive
everything else from, and per-scenario option metadata is not one of them.  The
pattern instead follows ``ActorSession`` (DEMOMA-26) — a frozen value object
whose shape is pinned to its call site by a ratchet, here
``test/architecture/test_scenario_roles_match_main_kwargs.py``.

Implementation guidance: ``notes/demo-scenario-registry.md``.
"""

from __future__ import annotations

import os
import re
from collections.abc import Sequence
from dataclasses import dataclass

from vultron.errors import DemoActorRoleError

#: Role name spelling: lowercase alphanumerics separated by single hyphens.
#: ``name`` is the stem of both option flags and both ``main()`` parameters, so a
#: name that cannot round-trip into a click flag *and* a Python identifier is
#: rejected here rather than producing an unreachable option later.
#:
#: Anchored with ``\Z`` rather than ``$``, which also matches before a trailing
#: newline: ``"finder\n"`` would pass and then yield a ``--finder\n-url`` flag.
_NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*\Z")


@dataclass(frozen=True, slots=True)
class ActorRole:
    """One actor slot in a demo scenario, and the CLI options it contributes.

    Frozen because the CLI reads ``url`` at decoration time and the scenario's
    ``main()`` reads the derived ``*_BASE_URL`` constant at call time; a role
    whose binding could be mutated between those two reads would give the option
    default and the fallback different containers.
    """

    #: Flag stem, e.g. ``"finder"``, ``"c1"``, ``"case-actor"``.  Yields
    #: ``--<name>-url`` / ``--<name>-id`` and ``<name_>_url`` / ``<name_>_id``.
    name: str
    #: Env var naming this actor's container, e.g. ``"VULTRON_VENDOR_BASE_URL"``.
    #: A *container slot*, not a role — two scenarios may map the same slot to
    #: differently-named roles, which is why this cannot be derived from ``name``.
    url_env: str
    #: Base URL used when :attr:`url_env` is unset.
    default_url: str
    #: Verbatim ``--help`` text for the ``--<name>-url`` option.  Ad hoc per
    #: scenario because it names the container slot, not the role.
    url_help: str
    #: Whether this actor also takes a ``--<name>-id`` option.  Only the handoff
    #: scenarios pass a deterministic id for the CaseActor, for instance.
    has_id: bool = False
    #: Verbatim ``--help`` text for the ``--<name>-id`` option.  Required when
    #: :attr:`has_id`, forbidden otherwise.
    id_help: str | None = None
    #: Env var backing the ``--<name>-id`` option.  ``None`` for every scenario
    #: but ``fcvcv``, whose actor ids are supplied by the compose environment.
    id_env: str | None = None

    def __post_init__(self) -> None:
        if not _NAME_RE.match(self.name):
            raise DemoActorRoleError(
                f"actor role name {self.name!r} is not a valid option stem; "
                "expected lowercase alphanumerics separated by single hyphens "
                "(e.g. 'case-actor'). Both option flags and both main() "
                "parameter names derive from it."
            )
        for field_name in ("url_env", "default_url", "url_help"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise DemoActorRoleError(
                    f"actor role {self.name!r} has an empty {field_name}; "
                    "the CLI has nowhere else to get it."
                )
        if self.has_id:
            # Without a help string the generated `--<name>-id` option is
            # reachable but undocumented, which reads as an internal flag and
            # is how a deterministic-id option goes unused in a new scenario.
            if not (self.id_help and self.id_help.strip()):
                raise DemoActorRoleError(
                    f"actor role {self.name!r} declares has_id=True but no "
                    "id_help; the generated --"
                    f"{self.name}-id option would have no --help text."
                )
        else:
            # Set-but-ignored id metadata is the failure this catches: the
            # author believes the scenario accepts `--<name>-id` and it does
            # not, because the factory only emits the option when has_id.
            extra = [
                field_name
                for field_name in ("id_help", "id_env")
                if getattr(self, field_name) is not None
            ]
            if extra:
                raise DemoActorRoleError(
                    f"actor role {self.name!r} sets {sorted(extra)} but "
                    "has_id is False, so no --"
                    f"{self.name}-id option is generated and the value is "
                    "silently ignored. Set has_id=True or drop them."
                )

    @property
    def url(self) -> str:
        """This actor's container base URL: :attr:`url_env` or the default.

        Read once per consumer — at click decoration time for the option
        default, and at module import time for the scenario's ``*_BASE_URL``
        constant — which is the same env resolution each site did by hand
        before.
        """
        return os.environ.get(self.url_env, self.default_url)

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
            if two roles name the same container env var.
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

    # The second half of "declared once": a role that reads another role's
    # `url_env` was not really declared, it was copy-pasted and half-edited —
    # the likeliest mistake when adding an actor to an existing scenario, since
    # the slot names and the role names deliberately do not correspond.
    #
    # This catches the *declaration* mistake only. It says nothing about two
    # roles whose distinct env vars happen to resolve to the same URL, which is
    # normal for local development and a compose concern rather than a
    # declaration one.
    seen_env: dict[str, str] = {}
    for role in roles:
        owner = seen_env.get(role.url_env)
        if owner is not None:
            raise DemoActorRoleError(
                f"actor roles {owner!r} and {role.name!r} both declare "
                f"{role.url_env}; one of them is reading the other's container "
                "slot. Give each role its own VULTRON_*_BASE_URL slot (the slot "
                "names do not track the role names — see "
                "notes/demo-scenario-authoring.md)."
            )
        seen_env[role.url_env] = role.name

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


__all__ = [
    "ActorRole",
    "role_kwarg_names",
    "role_map",
]
