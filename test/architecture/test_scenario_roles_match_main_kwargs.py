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

"""Architecture invariant: a scenario's ``ROLES`` list cannot drift from its
``main()`` signature (DEMOCI-11-011).

``vultron/demo/cli.py`` generates each scenario sub-command's options from that
scenario's ``ROLES`` and then splats the parsed values into ``main(**kwargs)``.
The two halves are declared in different places, so nothing at import time
notices when they disagree — and the failure is not a clean ``TypeError`` at the
top of the run in every direction:

* a role whose ``url_param`` ``main()`` does not accept raises ``TypeError`` when
  the sub-command is invoked, i.e. only once someone runs that scenario in CI;
* a ``main()`` keyword no role declares gets no option at all, so the parameter
  silently keeps its ``None`` default and the scenario runs against whatever
  fallback constant it was written to use — a working-looking demo pointed at
  the wrong container.

This pins the whole tuple, in order, so either direction fails here instead.
Ordering is checked rather than set equality because the generated options and
the signature are read by humans side by side; a reordered pair is a review
hazard even though click passes by keyword.

The analogue for ``ActorSession`` is
``test_actor_session_kwargs_match_request_models.py`` (DEMOMA-26-004), the
consolidation this one follows.
"""

import importlib
import inspect
from collections.abc import Sequence
from typing import cast

import pytest

from vultron.demo.helpers.actor_roles import ActorRole, role_kwarg_names
from vultron.demo.scenario.registry import ScenarioSpec, discover_scenarios

#: ``main()`` keyword that every scenario takes and no role contributes.
_NON_ROLE_KWARGS = frozenset({"skip_health_check"})


def _scenario_main_kwargs(main) -> tuple[str, ...]:
    """Role-contributed keyword parameters of a scenario ``main()``, in order."""
    return tuple(
        name
        for name, param in inspect.signature(main).parameters.items()
        if name not in _NON_ROLE_KWARGS
        and param.kind in (param.POSITIONAL_OR_KEYWORD, param.KEYWORD_ONLY)
    )


@pytest.mark.parametrize(
    "spec", discover_scenarios(), ids=lambda spec: spec.name
)
def test_scenario_roles_match_main_kwargs(spec: ScenarioSpec) -> None:
    """``role_kwarg_names(ROLES)`` equals ``main()``'s role keywords, in order."""
    module = importlib.import_module(spec.module_name)
    roles = cast("Sequence[ActorRole]", module.ROLES)

    expected = role_kwarg_names(roles)
    actual = _scenario_main_kwargs(module.main)

    assert expected == actual, (
        f"scenario {spec.name!r} declares roles implying keywords "
        f"{list(expected)} but {spec.module_name}.main() takes "
        f"{list(actual)}.\n"
        "The CLI generates this scenario's options from ROLES and calls "
        "main(**kwargs), so a missing keyword raises TypeError at run time and "
        "a missing role leaves the parameter at its default with no option to "
        "set it (DEMOCI-11-011). Fix whichever side is wrong — do not add a "
        "**kwargs shim."
    )


@pytest.mark.parametrize(
    "spec", discover_scenarios(), ids=lambda spec: spec.name
)
def test_scenario_main_takes_skip_health_check(spec: ScenarioSpec) -> None:
    """Every scenario ``main()`` accepts the one non-role keyword.

    Guards the guard: ``_NON_ROLE_KWARGS`` subtracts ``skip_health_check``
    before comparing, so a scenario that dropped the parameter would make the
    ratchet above pass while its generated ``--skip-health-check`` option raised
    ``TypeError``.
    """
    module = importlib.import_module(spec.module_name)
    params = inspect.signature(module.main).parameters
    assert "skip_health_check" in params, (
        f"{spec.module_name}.main() takes no skip_health_check parameter, but "
        "the CLI factory generates a --skip-health-check option for every "
        "scenario and passes it by keyword."
    )


def test_every_scenario_declares_roles() -> None:
    """A scenario module with no ``ROLES`` list fails here, not at ``--help``.

    Without this the parametrized ratchets above would raise
    ``AttributeError`` inside a test case, which reads as a broken test rather
    than as the missing declaration it is.
    """
    missing = sorted(
        spec.name
        for spec in discover_scenarios()
        if not getattr(
            importlib.import_module(spec.module_name), "ROLES", None
        )
    )
    assert not missing, (
        f"scenario module(s) {missing} declare no ROLES list. The demo CLI "
        "generates their container-URL and actor-id options from it "
        "(DEMOCI-11-011); without it the sub-command has no options and runs "
        "against localhost defaults."
    )
