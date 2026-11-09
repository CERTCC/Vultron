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

"""Which registered scenarios a ``--scenario`` option selects.

Both recorder commands take a repeatable ``--scenario`` and default to every
registered scenario, so the selection is written once (CS-22-001).  The
registry is passed in rather than discovered here, so each command keeps one
discovery call of its own.
"""

from collections.abc import Mapping, Sequence

import click

from vultron.demo.scenario.registry import ScenarioSpec


def select_scenarios(
    registered: Mapping[str, ScenarioSpec], names: Sequence[str]
) -> dict[str, ScenarioSpec]:
    """Return the scenarios *names* selects out of *registered*.

    Args:
        registered: Every registered scenario, by name.
        names: The ``--scenario`` values, in the order given.  Empty selects
            every registered scenario.

    Returns:
        The selected scenarios, in the order given, or the whole registry in
        its own order.

    Raises:
        click.BadParameter: When a name is not registered.  Reported rather
            than skipped: a gate asked for a scenario that no longer exists
            compares one fewer than its caller believes.
    """
    unknown = sorted(set(names) - set(registered))
    if unknown:
        raise click.BadParameter(
            f"not registered: {', '.join(unknown)}", param_hint="--scenario"
        )
    if not names:
        return dict(registered)
    return {name: registered[name] for name in names}


__all__ = ["select_scenarios"]
