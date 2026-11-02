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
"""The demo scenario tree, merged from the scenarios' declared paths.

Each registered scenario declares its full path from the root as ordered
``(branch point, choice)`` pairs — on ``@scenario(path=...)``, or read off the
choices of its assembled story once it is written as composition
(DEMOCI-11-014, DEMOCI-11-019). Merging the paths gives the tree: a node is
identified by its **path prefix**, never by its branch point, because one
decision can recur on a path. :func:`build_scenario_tree` refuses a set of
paths that is not one well-formed tree, so that every registered scenario is
exactly one ending (DEMOCI-11-023):

- two scenarios with the same path (one ending, two scenarios);
- a path that is a strict prefix of another (a scenario that is both an
  interior node and an ending);
- two paths that reach the same node and continue with different branch
  points (a node at which two different decisions are made).

Unknown branch points and choices are refused earlier, when ``@scenario``
builds the spec (:func:`vultron.demo.scenario.branch_points.validate_path`).

Rules: ``notes/demo-scenario-registry.md`` § "The path and the branch-point
table".
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from vultron.errors import DemoScenarioRegistryError

if TYPE_CHECKING:
    from vultron.demo.scenario.registry import ScenarioSpec

#: One step of a path: ``(branch point id, choice id)``.
PathStep = tuple[str, str]


@dataclass(slots=True)
class TreeNode:
    """One node of the scenario tree, keyed by its path prefix.

    A node is either an **interior** node, at which :attr:`branch_point` is
    decided and :attr:`children` holds one child per choice taken, or an
    **ending**, which carries the :attr:`scenario` name and has no children.
    """

    #: The path from the root to this node.
    prefix: tuple[PathStep, ...]
    #: The branch point decided at this node; ``None`` for an ending.
    branch_point: str | None = None
    #: Child nodes keyed by choice id, in first-declared order.
    children: dict[str, TreeNode] = field(default_factory=dict)
    #: The scenario that ends here; ``None`` for an interior node.
    scenario: str | None = None

    def walk(self) -> Iterator[TreeNode]:
        """Yield this node and every descendant, depth first."""
        yield self
        for child in self.children.values():
            yield from child.walk()

    def endings(self) -> dict[str, TreeNode]:
        """Every ending at or below this node, keyed by scenario name."""
        return {
            node.scenario: node
            for node in self.walk()
            if node.scenario is not None
        }


def _describe(prefix: tuple[PathStep, ...]) -> str:
    if not prefix:
        return "the root"
    return " → ".join(f"{bp}:{choice}" for bp, choice in prefix)


def build_scenario_tree(specs: Iterable[ScenarioSpec]) -> TreeNode:
    """Merge the declared paths of *specs* into one tree.

    Args:
        specs: The scenarios whose paths make up the tree.

    Returns:
        The root node. Every spec is exactly one ending.

    Raises:
        DemoScenarioRegistryError: If two specs declare the same path, if one
            path is a strict prefix of another, or if two paths reach the same
            node and decide different branch points there.
    """
    root = TreeNode(prefix=())
    for spec in specs:
        node = root
        for depth, (branch_point_id, choice_id) in enumerate(spec.path):
            if node.scenario is not None:
                raise DemoScenarioRegistryError(
                    f"scenario {node.scenario!r} ends at "
                    f"{_describe(node.prefix)}, a strict prefix of "
                    f"{spec.name!r}'s path; a scenario cannot be both an "
                    "interior node and an ending (DEMOCI-11-023)."
                )
            if node.branch_point is None:
                node.branch_point = branch_point_id
            elif node.branch_point != branch_point_id:
                raise DemoScenarioRegistryError(
                    f"scenario {spec.name!r} decides {branch_point_id!r} at "
                    f"{_describe(node.prefix)}, where another scenario "
                    f"decides {node.branch_point!r}; one node is one decision."
                )
            child = node.children.get(choice_id)
            if child is None:
                child = TreeNode(prefix=spec.path[: depth + 1])
                node.children[choice_id] = child
            node = child
        if node.scenario is not None:
            raise DemoScenarioRegistryError(
                f"scenarios {node.scenario!r} and {spec.name!r} declare the "
                f"same path ({_describe(node.prefix)}); every scenario is "
                "its own ending (DEMOCI-11-023)."
            )
        if node.children:
            raise DemoScenarioRegistryError(
                f"scenario {spec.name!r} ends at {_describe(node.prefix)}, a "
                "strict prefix of another scenario's path; a scenario cannot "
                "be both an interior node and an ending (DEMOCI-11-023)."
            )
        node.scenario = spec.name
    return root


__all__ = ["PathStep", "TreeNode", "build_scenario_tree"]
