"""What a scenario declares: :class:`ScenarioSpec` and the paths derived from its name."""

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

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, TypeVar

from vultron.demo.scenario.branch_points import validate_path
from vultron.demo.scenario.tree import PathStep
from vultron.errors import DemoScenarioRegistryError

#: Dotted path of the package holding the scenario demo modules.
SCENARIO_PACKAGE = "vultron.demo.scenario"

#: Repository-relative directory of :data:`SCENARIO_PACKAGE`.
SCENARIO_DIR = "vultron/demo/scenario"

#: Module-name suffix that marks a module in that package as a scenario demo.
#: Both discovery and the set-equality ratchet key off it, so a scenario module
#: that does not end this way is invisible to the registry.
MODULE_SUFFIX = "_demo"

#: Scenario sub-command spelling: lowercase alphanumerics separated by single
#: hyphens. ``name`` is the only field everything else derives from, so a name
#: that cannot round-trip through a filename or a URL slug is rejected here
#: rather than producing an unresolvable derived path later.
#:
#: Anchored with ``\Z`` rather than ``$``, which also matches before a trailing
#: newline: ``"rv\n"`` would pass this check and then fail the module-name
#: comparison in :func:`_register`, pointing the author at the wrong problem.
_NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*\Z")

F = TypeVar("F", bound=Callable[..., None])


class StoryPath(Protocol):
    """A scenario's assembled story, seen only as the path it walks.

    A scenario registers its story, and the registry reads the path off the
    story's choices (DEMOCI-11-019).  Declared structurally rather than
    imported so the registry keeps no dependency on the demo helper library
    that owns stories (:mod:`vultron.demo.helpers.story`), which imports the
    harness, which imports this module.
    """

    @property
    def path(self) -> tuple[PathStep, ...]:
        """The ordered ``(branch point, choice)`` pairs the story decides."""
        ...


def is_scenario_name(value: str) -> bool:
    """Whether *value* is a well-formed scenario name.

    The public form of :data:`_NAME_RE`, so tooling outside this package can ask
    the question without importing a private pattern. Callers that need to *find*
    names inside prose still use the pattern itself — a predicate cannot scan.
    """
    return _NAME_RE.match(value) is not None


def _require_table_cell(
    scenario_name: str, field_name: str, value: object
) -> None:
    """Refuse a prose field that would render as a broken markdown table cell.

    Every one of ``label``, ``participants`` and ``feature`` is rendered into
    one cell of three generated tables, so the ways it can go wrong are the
    same for all three and the check is stated once here.

    Args:
        scenario_name: The scenario the field belongs to, for the message.
        field_name: Which field is being checked.
        value: Its declared value.

    Raises:
        DemoScenarioRegistryError: When the value is not a single stripped,
            non-empty line of plain prose.
    """
    if not isinstance(value, str) or not value.strip():
        raise DemoScenarioRegistryError(
            f"scenario {scenario_name!r} has an empty {field_name}; "
            "it renders as a table cell and there is nowhere else for "
            "a reader to get it."
        )
    # A newline splits the markdown row mid-cell in all three generated
    # consumers, and the result is a *valid* generated file — so --check keeps
    # the corrupted table in sync rather than reporting it. Refuse here, where
    # the value is written.
    #
    # Compared against the stripped value rather than by counting lines:
    # `len("Baseline\n".splitlines())` is 1, so a line-count test accepts the
    # single likeliest spelling of this mistake — a value with one trailing
    # newline — and the corrupted row reaches the artifact anyway.
    if value != value.strip():
        raise DemoScenarioRegistryError(
            f"scenario {scenario_name!r} has a {field_name} with leading "
            f"or trailing whitespace ({value!r}); a newline splits the "
            "markdown row mid-cell and the surrounding whitespace "
            "renders inconsistently across the three consumers. Strip it."
        )
    if len(value.splitlines()) > 1:
        raise DemoScenarioRegistryError(
            f"scenario {scenario_name!r} has a multi-line {field_name} "
            f"({value!r}); every generated consumer renders it as one "
            "markdown table cell, which a line break would break in "
            "half. Keep it to a single line."
        )
    # `markdownlint-cli2 --fix` runs ahead of the demo-scenarios-sync hook and
    # rewrites `_x_` to `*x*` (MD049) and a bare URL to `<url>` (MD034)
    # *inside* a table cell. Either rewrite makes the committed artifact
    # disagree with the registry, and neither command the --check error names
    # can settle it: --write restores the unlinted spelling and markdownlint
    # re-fixes it. Refuse the characters here, where the value is written.
    if any(ch in value for ch in "_<>") or "://" in value:
        raise DemoScenarioRegistryError(
            f"scenario {scenario_name!r} has a {field_name} containing an "
            f"underscore, angle bracket, or URL ({value!r}); "
            "`markdownlint-cli2 --fix` rewrites those inside a "
            "markdown table cell, which would leave the "
            "demo-scenarios-sync hook and markdownlint undoing each "
            "other. Use plain prose."
        )


@dataclass(frozen=True, slots=True)
class ScenarioSpec:
    """One registered demo scenario.

    Holds only facts the demo module is the authority for. Every path is a
    derived property; see the module docstring for why none of them is a field.
    """

    #: Sub-command spelling, e.g. ``"rvcv-handoff"``. The identity of the
    #: scenario and the stem of all three derived paths.
    name: str
    #: Display casing for table cells, e.g. ``"RVCV-handoff"``.
    label: str
    #: Prose participant list, e.g. ``"Reporter + Vendor1 → Coordinator + Vendor2"``.
    participants: str
    #: One-line notable protocol feature.
    feature: str
    #: Whether the scenario runs on ``pull_request`` events. The coverage
    #: rationale for the PR set lives in DEMOCI-06-002, not here.
    in_pr_set: bool
    #: The scenario's full path from the root of the scenario tree: ordered
    #: ``(branch point id, choice id)`` pairs naming entries of
    #: :data:`~vultron.demo.scenario.branch_points.BRANCH_POINTS`
    #: (DEMOCI-11-014), read off the choices of the scenario's assembled story
    #: (DEMOCI-11-019). The prompts and choice labels are read from the
    #: branch-point table, never declared here (DEMOCI-11-050).
    path: tuple[PathStep, ...]

    def __post_init__(self) -> None:
        if not _NAME_RE.match(self.name):
            raise DemoScenarioRegistryError(
                f"scenario name {self.name!r} is not a valid sub-command "
                "spelling; expected lowercase alphanumerics separated by "
                "single hyphens (e.g. 'rvcv-handoff'). Every derived artifact "
                "path is built from this value."
            )
        for field_name in ("label", "participants", "feature"):
            _require_table_cell(
                self.name, field_name, getattr(self, field_name)
            )
        if not isinstance(self.in_pr_set, bool):
            raise DemoScenarioRegistryError(
                f"scenario {self.name!r} has a non-boolean in_pr_set "
                f"({self.in_pr_set!r}); the CI matrix filter compares "
                "'full_suite_only == false' exactly, so a truthy non-boolean "
                "would drop the scenario from the matrix instead of erroring."
            )
        try:
            normalized = validate_path(self.path)
        except DemoScenarioRegistryError as exc:
            raise DemoScenarioRegistryError(
                f"scenario {self.name!r} declares an invalid path: {exc}"
            ) from exc
        if normalized != self.path:
            raise DemoScenarioRegistryError(
                f"scenario {self.name!r} has a path that is not a tuple of "
                f"(branch point, choice) tuples ({self.path!r}); a frozen "
                "spec holds an immutable path."
            )

    @property
    def module_stem(self) -> str:
        """``name`` as a Python identifier fragment (hyphens → underscores)."""
        return self.name.replace("-", "_")

    @property
    def module_name(self) -> str:
        """Dotted module path the decorator must be applied in."""
        return f"{SCENARIO_PACKAGE}.{self.module_stem}{MODULE_SUFFIX}"

    @property
    def demo_filename(self) -> str:
        """Bare filename of the scenario's demo script.

        The single owner of the ``<stem>_demo.py`` spelling, so a renderer that
        wants only the filename does not re-derive the convention and drift
        from :attr:`demo_path` — which is what the derived-path check verifies.
        """
        return f"{self.module_stem}{MODULE_SUFFIX}.py"

    @property
    def demo_path(self) -> str:
        """Repo-relative path of the scenario's demo script (DEMOCI-11-003)."""
        return f"{SCENARIO_DIR}/{self.demo_filename}"

    @property
    def harness_path(self) -> str:
        """Repo-relative path of the scenario's invariant harness."""
        return f"test/ci/invariants/test_{self.module_stem}_invariants.py"

    @property
    def narrative_path(self) -> str:
        """Repo-relative path of the scenario's narrative page."""
        return f"docs/topics/scenarios/{self.name}.md"

    @property
    def derived_paths(self) -> tuple[str, str, str]:
        """All three convention-derived paths, in declaration order."""
        return (self.demo_path, self.harness_path, self.narrative_path)

    @property
    def full_suite_only(self) -> bool:
        """The CI matrix's spelling of :attr:`in_pr_set`, inverted."""
        return not self.in_pr_set
