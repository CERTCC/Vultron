"""Self-registering demo scenario registry (ADR-0098, DEMOCI-11).

Each scenario module under ``vultron/demo/scenario/`` declares itself by
decorating its own ``main()``::

    @scenario(
        name="rv",
        label="rv",
        participants="Reporter + Vendor",
        feature="Baseline two-actor CVD",
        in_pr_set=True,
        story=STORY,
    )
    def main(skip_health_check: bool = False, ...) -> None:

The registry is then the **sole** declaration point for the set of scenarios
that exist (DEMOCI-11-036), and `.github/demo-scenarios.json`, the plot
manifest at `vultron/demo/scenario/plots.json`, the scenario
tables in `test/ci/README-case-log-ratchet.md` and
`vultron/demo/scenario/README.md`, and the narrative index at
`docs/topics/scenarios/index.md` are all derived from it by
:mod:`vultron.metadata.demo_scenarios`.

Two design rules are load-bearing and easy to undo by accident:

- **The decorator carries no paths.** All three of a scenario's artifact paths
  derive from ``name`` by convention (DEMOCI-11-003). A scenario is a
  ``<name_>_demo.py`` module or a ``<name_>_demo/`` package; the demo path
  follows whichever form the import system resolves the derived name to. A
  stored path is a path that can be wrong about itself; a derived path either
  resolves or fails a check. Adding an override field re-opens the drift
  channel for every scenario, not just the one that needed it.
- **Discovery walks the package.** Import-time registration only sees modules
  that were imported, so a hand-maintained import list here would recreate
  exactly the silent omission the registry exists to remove (DEMOCI-11-038).
  :func:`discover_scenarios` therefore enumerates the package with ``pkgutil``
  and raises when a discovered module did not register, so a generated table
  can never come out quietly short.

**A scenario registers its story, and the story is its path.** A scenario is
written as composition (:mod:`vultron.demo.helpers.story`), so it passes
``story=`` and the registry reads the path off the story's choices — the path
is never typed a second time beside the code that walks it (DEMOCI-11-019,
DEMOCI-11-024). ``story`` is the only way a scenario places itself on the
tree, so :func:`scenario` takes no path parameter and nothing can declare a
second copy.

**The path places the scenario on the tree.** The path names entries of the
branch-point table (:mod:`vultron.demo.scenario.branch_points`) and is checked
against it when the spec is built; :func:`discover_scenarios` then merges every
path into one tree (:mod:`vultron.demo.scenario.tree`) and fails unless each
scenario is exactly one ending (DEMOCI-11-023).

**Registration means built.** A scenario that has a spec group but no module
is declared by the planned-scenario register in ``notes/demo-future-ideas.md``
instead, never here (DEMOCI-11-010).

Design rationale: ``docs/adr/0098-demo-scenarios-self-register.md``.
Implementation guidance: ``notes/demo-scenario-registry.md``.
"""

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

from vultron.demo.scenario.registry.discovery import (
    discover_scenarios,
    registered_scenarios,
    scenario,
    scenario_module_stems,
    scenario_tree,
)
from vultron.demo.scenario.registry.spec import (
    MODULE_SUFFIX,
    SCENARIO_DIR,
    SCENARIO_PACKAGE,
    AssembledStory,
    ScenarioSpec,
    is_scenario_name,
)

__all__ = [
    "MODULE_SUFFIX",
    "SCENARIO_DIR",
    "SCENARIO_PACKAGE",
    "AssembledStory",
    "ScenarioSpec",
    "discover_scenarios",
    "is_scenario_name",
    "registered_scenarios",
    "scenario",
    "scenario_module_stems",
    "scenario_tree",
]
