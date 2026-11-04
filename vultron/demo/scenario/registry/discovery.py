"""Registering scenarios and discovering every one in the scenario package."""

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

import importlib
import pkgutil
from collections.abc import Callable, Iterable
from pathlib import Path

from vultron.demo.scenario.registry.spec import (
    MODULE_SUFFIX,
    SCENARIO_PACKAGE,
    F,
    ScenarioSpec,
    StoryPath,
)
from vultron.demo.scenario.tree import PathStep, TreeNode, build_scenario_tree
from vultron.errors import DemoScenarioRegistryError

_REGISTRY: dict[str, ScenarioSpec] = {}


def scenario(
    *,
    name: str,
    label: str,
    participants: str,
    feature: str,
    in_pr_set: bool,
    story: StoryPath,
) -> Callable[[F], F]:
    """Register the decorated ``main()`` as a demo scenario.

    Keyword-only by design: four same-typed prose arguments are trivially
    swappable positionally, and a swapped ``label``/``participants`` pair would
    render as a plausible-looking wrong table rather than failing.

    ``story`` is the only thing that places the scenario on the tree, and it is
    required: there is no path parameter to type a second copy into
    (DEMOCI-11-019, DEMOCI-11-024).  A scenario that gives no story therefore
    fails with a ``TypeError`` at import, before any check can run on a spec
    that has nowhere to sit.

    Args:
        name: Sub-command spelling; the stem of all derived paths.
        label: Display casing used in generated table cells.
        participants: Prose participant list.
        feature: One-line notable protocol feature.
        in_pr_set: Whether the scenario runs on ``pull_request`` events.
        story: The scenario's assembled story
            (:mod:`vultron.demo.helpers.story`), whose choices are read as its
            full path from the root of the tree (DEMOCI-11-014,
            DEMOCI-11-019).  Prompts and choice labels come from the
            branch-point table, so this decorator takes neither
            (DEMOCI-11-050).

    Returns:
        A decorator that registers the spec and returns the function unchanged.

    Raises:
        DemoScenarioRegistryError: If ``story`` names no path, if the spec is
            malformed, if the name is already registered with a different
            spec, or if the decorator is applied in a module whose name
            contradicts ``name``.
    """
    declared = _story_path(name, story)

    def register(func: F) -> F:
        spec = ScenarioSpec(
            name=name,
            label=label,
            participants=participants,
            feature=feature,
            in_pr_set=in_pr_set,
            path=declared,
        )
        _register(spec, func.__module__)
        return func

    return register


def _story_path(name: str, story: StoryPath) -> tuple[PathStep, ...]:
    """Return the path *story* walks, as the scenario *name*'s path.

    A required argument cannot be omitted, but it can still arrive as a
    ``None`` a module-level name resolved to, which would reach
    :class:`ScenarioSpec` as an ``AttributeError`` naming no scenario.  Tested
    for identity rather than with ``getattr(story, "path", None)``, which would
    also swallow an ``AttributeError`` raised inside a real ``path`` property
    and report a genuine bug as a missing path.

    Raises:
        DemoScenarioRegistryError: When *story* is ``None``.
    """
    if story is None:
        raise DemoScenarioRegistryError(
            f"scenario {name!r} was given None as its story, which names "
            "no path; a scenario is placed on the tree by the choices of its "
            "assembled story (DEMOCI-11-014, DEMOCI-11-019)."
        )
    return tuple(story.path)


def _register(spec: ScenarioSpec, origin_module: str) -> None:
    """Add *spec* to the registry, rejecting conflicts and misplacements.

    Args:
        spec: The scenario being registered.
        origin_module: ``__module__`` of the decorated function.

    Raises:
        DemoScenarioRegistryError: On a name collision with a different spec,
            or when a module of the scenario package that is neither
            ``spec.module_name`` nor one of its submodules declares it.
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
    #
    # A package scenario declares `main()` in a submodule (its `__init__` only
    # re-exports, CS-18-003), so a submodule of the derived name is the same
    # scenario. A plain prefix test would not do: `rv_demo_old` starts with
    # `rv_demo` and is a different module.
    if origin_module.startswith(f"{SCENARIO_PACKAGE}.") and not (
        origin_module == spec.module_name
        or origin_module.startswith(f"{spec.module_name}.")
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
    """Return the scenario package's ``*_demo`` module and package names, sorted.

    Enumerates the package with ``pkgutil`` rather than consulting a list
    (DEMOCI-11-002). A scenario is a ``<name_>_demo.py`` module or a
    ``<name_>_demo/`` package (DEMOCI-11-003), so both are returned.

    Private names are skipped even when they end in the suffix. A shared
    private helper such as ``_shared_demo.py`` is not a scenario, but without
    this filter :func:`discover_scenarios` would raise telling its author to
    decorate it as one.

    Raises:
        DemoScenarioRegistryError: When one name is both a module and a package.
            The import system loads the package and never reads the module,
            so the module's code would sit in the tree and never run. Also
            when a ``*_demo`` directory has no ``__init__.py``: ``pkgutil``
            does not list it, so the scenario would vanish from the CLI and
            every table with no error.
    """
    package = importlib.import_module(SCENARIO_PACKAGE)
    _refuse_misshapen_directories(package.__path__)
    return tuple(
        sorted(
            info.name
            for info in pkgutil.iter_modules(package.__path__)
            if info.name.endswith(MODULE_SUFFIX)
            and not info.name.startswith("_")
        )
    )


def _holds_source(directory: Path) -> bool:
    """Whether *directory* holds any file outside a ``__pycache__``, at any depth.

    Switching to a branch where a package scenario is a module again leaves
    its ``__pycache__`` directories behind, nested ones included, untracked;
    a directory holding nothing else is no scenario.
    """
    return any(
        path.is_file()
        and "__pycache__" not in path.relative_to(directory).parts
        for path in directory.rglob("*")
    )


def _refuse_misshapen_directories(locations: Iterable[str]) -> None:
    """Raise when a ``*_demo`` directory in *locations* is not one scenario.

    A directory beside a ``.py`` module of the same name is both forms, and
    a directory with no ``__init__.py`` is not a package. Leftover bytecode
    is ignored (:func:`_holds_source`).
    """
    directories = [
        path
        for location in locations
        for path in Path(location).glob(f"*{MODULE_SUFFIX}")
        if path.is_dir()
        and not path.name.startswith("_")
        and _holds_source(path)
    ]
    both = sorted(
        path.name
        for path in directories
        if path.with_name(f"{path.name}.py").is_file()
    )
    if both:
        raise DemoScenarioRegistryError(
            "scenario name(s) present as both a module and a package: "
            + ", ".join(both)
            + ". A scenario is one form or the other (DEMOCI-11-003); the "
            "import system would load one and silently ignore the other. "
            "Delete one."
        )
    stray = sorted(
        path.name
        for path in directories
        if not (path / "__init__.py").is_file()
    )
    if stray:
        raise DemoScenarioRegistryError(
            "scenario director(ies) with no __init__.py: "
            + ", ".join(stray)
            + ". pkgutil does not list a directory without one, so the "
            "scenario would be missing from the CLI and every generated "
            "table. Add an __init__.py that re-exports main, ROLES, "
            "CLI_HELP and STORY, or remove the directory (DEMOCI-11-002)."
        )


def discover_scenarios() -> tuple[ScenarioSpec, ...]:
    """Import every ``*_demo`` module or package and return the registry.

    Returns only the specs whose module is one of the discovered stems. The
    global registry is process-wide, so a spec registered from outside the
    scenario package — a test fixture module, or a demo run in-process as
    ``__main__``, both of which :func:`_register` deliberately lets through —
    would otherwise leak into every later caller and make the generated
    artifacts order-dependent.

    Raises:
        DemoScenarioRegistryError: If a discovered module registered nothing,
            or if the declared paths do not make one tree in which every
            scenario is exactly one ending (:func:`scenario_tree`,
            DEMOCI-11-023). Failing
            here rather than returning a short tuple is the point: a
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
            f"{__package__} (DEMOCI-11-001); a package scenario's __init__ "
            "re-exports main from the submodule that declares it, so "
            "importing the package registers it."
        )
    build_scenario_tree(specs)
    return specs


def scenario_tree() -> TreeNode:
    """Discover every scenario and return the tree their paths make.

    Raises:
        DemoScenarioRegistryError: As :func:`discover_scenarios`.
    """
    return build_scenario_tree(discover_scenarios())
