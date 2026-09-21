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
"""Self-registering demo scenario registry (ADR-0098, DEMOCI-11).

Each scenario module under ``vultron/demo/scenario/`` declares itself by
decorating its own ``main()``::

    @scenario(
        name="fv",
        label="FV",
        participants="Finder + Vendor",
        feature="Baseline two-actor CVD",
        in_pr_set=True,
    )
    def main(skip_health_check: bool = False, ...) -> None:

The registry is then the **sole** declaration point for the set of scenarios
that exist (DEMOCI-11-001), and `.github/demo-scenarios.json`, the scenario
tables in `test/ci/README-case-log-ratchet.md` and
`vultron/demo/scenario/README.md`, and the narrative index at
`docs/topics/scenarios/index.md` are all derived from it by
:mod:`vultron.metadata.demo_scenarios`.

Two design rules are load-bearing and easy to undo by accident:

- **The decorator carries no paths.** All three of a scenario's artifact paths
  derive from ``name`` by convention (DEMOCI-11-003). A stored path is a path
  that can be wrong about itself; a derived path either resolves or fails a
  check. Adding an override field re-opens the drift channel for every
  scenario, not just the one that needed it.
- **Discovery walks the package.** Import-time registration only sees modules
  that were imported, so a hand-maintained import list here would recreate
  exactly the silent omission the registry exists to remove (DEMOCI-11-002).
  :func:`discover_scenarios` therefore enumerates the package with ``pkgutil``
  and raises when a discovered module did not register, so a generated table
  can never come out quietly short.

**Registration means built.** A scenario that has a spec group but no module
is declared by the planned-scenario register in ``notes/demo-future-ideas.md``
instead, never here (DEMOCI-11-010).

Design rationale: ``docs/adr/0098-demo-scenarios-self-register.md``.
Implementation guidance: ``notes/demo-scenario-registry.md``.
"""

from __future__ import annotations

import importlib
import pkgutil
import re
from dataclasses import dataclass
from typing import Callable, TypeVar

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
#: newline: ``"fv\n"`` would pass this check and then fail the module-name
#: comparison in :func:`_register`, pointing the author at the wrong problem.
_NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*\Z")

F = TypeVar("F", bound=Callable[..., None])


@dataclass(frozen=True, slots=True)
class ScenarioSpec:
    """One registered demo scenario.

    Holds only facts the demo module is the authority for. Every path is a
    derived property; see the module docstring for why none of them is a field.
    """

    #: Sub-command spelling, e.g. ``"fvcv-handoff"``. The identity of the
    #: scenario and the stem of all three derived paths.
    name: str
    #: Display casing for table cells, e.g. ``"FVCV-handoff"``.
    label: str
    #: Prose participant list, e.g. ``"Finder + Vendor1 → Coordinator + Vendor2"``.
    participants: str
    #: One-line notable protocol feature.
    feature: str
    #: Whether the scenario runs on ``pull_request`` events. The coverage
    #: rationale for the PR set lives in DEMOCI-06-002, not here.
    in_pr_set: bool

    def __post_init__(self) -> None:
        if not _NAME_RE.match(self.name):
            raise DemoScenarioRegistryError(
                f"scenario name {self.name!r} is not a valid sub-command "
                "spelling; expected lowercase alphanumerics separated by "
                "single hyphens (e.g. 'fvcv-handoff'). Every derived artifact "
                "path is built from this value."
            )
        for field_name in ("label", "participants", "feature"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise DemoScenarioRegistryError(
                    f"scenario {self.name!r} has an empty {field_name}; "
                    "it renders as a table cell and there is nowhere else for "
                    "a reader to get it."
                )
            # A newline splits the markdown row mid-cell in all three generated
            # consumers, and the result is a *valid* generated file — so
            # --check keeps the corrupted table in sync rather than reporting
            # it. Refuse here, where the value is written.
            #
            # Compared against the stripped value rather than by counting
            # lines: `len("Baseline\n".splitlines())` is 1, so a line-count
            # test accepts the single likeliest spelling of this mistake — a
            # value with one trailing newline — and the corrupted row reaches
            # the artifact anyway.
            if value != value.strip():
                raise DemoScenarioRegistryError(
                    f"scenario {self.name!r} has a {field_name} with leading "
                    f"or trailing whitespace ({value!r}); a newline splits the "
                    "markdown row mid-cell and the surrounding whitespace "
                    "renders inconsistently across the three consumers. Strip "
                    "it."
                )
            if len(value.splitlines()) > 1:
                raise DemoScenarioRegistryError(
                    f"scenario {self.name!r} has a multi-line {field_name} "
                    f"({value!r}); every generated consumer renders it as one "
                    "markdown table cell, which a line break would break in "
                    "half. Keep it to a single line."
                )
            # `markdownlint-cli2 --fix` runs ahead of the demo-scenarios-sync
            # hook and rewrites `_x_` to `*x*` (MD049) and a bare URL to
            # `<url>` (MD034) *inside* a table cell. Either rewrite makes the
            # committed artifact disagree with the registry, and neither
            # command the --check error names can settle it: --write restores
            # the unlinted spelling and markdownlint re-fixes it. Refuse the
            # characters here, where the value is written.
            if any(ch in value for ch in "_<>") or "://" in value:
                raise DemoScenarioRegistryError(
                    f"scenario {self.name!r} has a {field_name} containing an "
                    f"underscore, angle bracket, or URL ({value!r}); "
                    "`markdownlint-cli2 --fix` rewrites those inside a "
                    "markdown table cell, which would leave the "
                    "demo-scenarios-sync hook and markdownlint undoing each "
                    "other. Use plain prose."
                )
        if not isinstance(self.in_pr_set, bool):
            raise DemoScenarioRegistryError(
                f"scenario {self.name!r} has a non-boolean in_pr_set "
                f"({self.in_pr_set!r}); the CI matrix filter compares "
                "'full_suite_only == false' exactly, so a truthy non-boolean "
                "would drop the scenario from the matrix instead of erroring."
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


_REGISTRY: dict[str, ScenarioSpec] = {}


def scenario(
    *,
    name: str,
    label: str,
    participants: str,
    feature: str,
    in_pr_set: bool,
) -> Callable[[F], F]:
    """Register the decorated ``main()`` as a demo scenario.

    Keyword-only by design: five same-typed prose arguments are trivially
    swappable positionally, and a swapped ``label``/``participants`` pair would
    render as a plausible-looking wrong table rather than failing.

    Args:
        name: Sub-command spelling; the stem of all derived paths.
        label: Display casing used in generated table cells.
        participants: Prose participant list.
        feature: One-line notable protocol feature.
        in_pr_set: Whether the scenario runs on ``pull_request`` events.

    Returns:
        A decorator that registers the spec and returns the function unchanged.

    Raises:
        DemoScenarioRegistryError: If the spec is malformed, if the name is
            already registered with a different spec, or if the decorator is
            applied in a module whose name contradicts ``name``.
    """

    def register(func: F) -> F:
        spec = ScenarioSpec(
            name=name,
            label=label,
            participants=participants,
            feature=feature,
            in_pr_set=in_pr_set,
        )
        _register(spec, func.__module__)
        return func

    return register


def _register(spec: ScenarioSpec, origin_module: str) -> None:
    """Add *spec* to the registry, rejecting conflicts and misplacements.

    Args:
        spec: The scenario being registered.
        origin_module: ``__module__`` of the decorated function.

    Raises:
        DemoScenarioRegistryError: On a name collision with a different spec,
            or when a scenario package module's name contradicts ``spec.name``.
    """
    existing = _REGISTRY.get(spec.name)
    if existing is not None and existing != spec:
        raise DemoScenarioRegistryError(
            f"scenario {spec.name!r} is already registered with a different "
            f"spec:\n  registered: {existing}\n  offered:    {spec}"
        )

    # A copy-pasted decorator with the old `name` still in it registers a
    # scenario whose derived paths point at the module it was copied *from* —
    # all three of which resolve, so no path check catches it. Comparing the
    # declared name against the module it was declared in does.
    #
    # Skipped when the module is not in the scenario package: running a demo
    # module as a script makes `__module__` `"__main__"`, and a test may
    # register a spec from a fixture module.
    if origin_module.startswith(f"{SCENARIO_PACKAGE}.") and (
        origin_module != spec.module_name
    ):
        raise DemoScenarioRegistryError(
            f"scenario {spec.name!r} is declared in {origin_module!r} but its "
            f"name derives the module {spec.module_name!r}. Every artifact "
            "path is derived from the name, so rename the module or fix the "
            "name — do not add a path override (DEMOCI-11-003)."
        )

    _REGISTRY[spec.name] = spec


def registered_scenarios() -> tuple[ScenarioSpec, ...]:
    """Return every registered scenario, ordered by :attr:`ScenarioSpec.name`.

    Name order is the canonical order for every generated artifact. It is
    stated once here so that no consumer has to choose, and so that the
    generated tables and the CI matrix cannot disagree about sequence.

    Only modules already imported have registered; call
    :func:`discover_scenarios` first to see the whole set.
    """
    return tuple(sorted(_REGISTRY.values(), key=lambda spec: spec.name))


def scenario_module_stems() -> tuple[str, ...]:
    """Return the scenario package's ``*_demo`` module names, sorted.

    Enumerates the package with ``pkgutil`` rather than consulting a list
    (DEMOCI-11-002).

    Private modules and sub-packages are skipped even when the name ends in the
    suffix. A shared private helper such as ``_shared_demo.py`` is not a
    scenario, but without this filter :func:`discover_scenarios` would raise
    telling its author to decorate it as one.
    """
    package = importlib.import_module(SCENARIO_PACKAGE)
    return tuple(
        sorted(
            info.name
            for info in pkgutil.iter_modules(package.__path__)
            if info.name.endswith(MODULE_SUFFIX)
            and not info.name.startswith("_")
            and not info.ispkg
        )
    )


def discover_scenarios() -> tuple[ScenarioSpec, ...]:
    """Import every ``*_demo`` module in the package and return the registry.

    Returns only the specs whose module is one of the discovered stems. The
    global registry is process-wide, so a spec registered from outside the
    scenario package — a test fixture module, or a demo run in-process as
    ``__main__``, both of which :func:`_register` deliberately lets through —
    would otherwise leak into every later caller and make the generated
    artifacts order-dependent.

    Raises:
        DemoScenarioRegistryError: If a discovered module registered nothing.
            Failing here rather than returning a short tuple is the point: a
            generator that silently omits a scenario produces a table that
            looks complete and is wrong, which is the defect ADR-0098 exists
            to remove.
    """
    stems = scenario_module_stems()
    for stem in stems:
        importlib.import_module(f"{SCENARIO_PACKAGE}.{stem}")

    stem_set = set(stems)
    specs = tuple(
        spec
        for spec in registered_scenarios()
        if f"{spec.module_stem}{MODULE_SUFFIX}" in stem_set
    )
    registered_stems = {f"{spec.module_stem}{MODULE_SUFFIX}" for spec in specs}
    undeclared = sorted(stem_set - registered_stems)
    if undeclared:
        raise DemoScenarioRegistryError(
            "scenario module(s) imported but not registered: "
            + ", ".join(undeclared)
            + ". Decorate the module's main() with @scenario(...) from "
            f"{__name__} (DEMOCI-11-001)."
        )
    return specs


__all__ = [
    "MODULE_SUFFIX",
    "SCENARIO_DIR",
    "SCENARIO_PACKAGE",
    "ScenarioSpec",
    "discover_scenarios",
    "registered_scenarios",
    "scenario",
    "scenario_module_stems",
]
