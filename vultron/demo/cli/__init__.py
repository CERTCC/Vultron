"""
Unified Vultron demo CLI (DC-01-001 through DC-01-005).

Each sub-command maps to one demo script in ``vultron/demo/``.
The ``all`` sub-command runs every demo in sequence and prints a
pass/fail summary.

The multi-container **scenario** sub-commands are not declared here at all:
they are generated, one per registered scenario, by
:func:`~vultron.demo.cli.scenario_commands._make_scenario_command` from the scenario registry (DEMOCI-11-011, ADR-0098).  The registry is the sole
declaration point for which scenarios exist, so this module cannot be a place a
scenario is omitted from or added to independently of it — which it was while it
hand-wired one ``@main.command`` block each.  Each scenario module supplies the
two things the registry deliberately does not carry: its ``ROLES`` list (the
container-URL and actor-id options, whose env bindings key to physical container
slots rather than roles) and its ``CLI_HELP`` text.

A ``vultrabot`` sub-group provides access to the three standalone
behaviour-tree demos (pacman, robot, cvd).

The ``seed`` sub-command bootstraps actor records in the DataLayer on
container startup, supporting multi-actor demo scenarios (D5-1-G2).
"""

#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
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

# Importing each command module registers its sub-commands on ``main``.
from vultron.demo.cli import (
    scenario_commands,
    seed_command,
    vultrabot_commands,
)
from vultron.demo.cli.exchange_commands import DEMOS, run_all
from vultron.demo.cli.group import main
from vultron.demo.cli.scenario_commands import SCENARIOS
from vultron.demo.cli.seed_command import seed
from vultron.demo.cli.vultrabot_commands import (
    vultrabot_cvd,
    vultrabot_group,
    vultrabot_pacman,
    vultrabot_robot,
)

__all__ = [
    "DEMOS",
    "SCENARIOS",
    "main",
    "run_all",
    "seed",
    "vultrabot_cvd",
    "vultrabot_group",
    "vultrabot_pacman",
    "vultrabot_robot",
]
