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
"""A ``<name_>_demo/`` package is a scenario, end to end (DEMOCI-11-003).

No committed scenario is a package yet, so the package form is exercised by a
fixture package written to a temporary directory.  The scenario package's
``__path__`` is pointed at that directory alone for the duration of a test, so
discovery sees the fixture and nothing else, and the process-wide registry is
swapped for a copy.  Every test that uses the fixture asserts afterwards that it
left no trace in the registry, the CLI, ``sys.modules`` or the generated
inventories: a fixture scenario that leaked would become a real row of every
generated table.
"""

from __future__ import annotations

import importlib
import sys
import textwrap
from collections.abc import Iterator
from pathlib import Path

import pytest
from click.testing import CliRunner

import vultron.demo.scenario as scenario_package
from vultron.demo import cli
from vultron.demo.cli.scenario_commands import _make_scenario_command
from vultron.demo.scenario.registry import (
    SCENARIO_DIR,
    SCENARIO_PACKAGE,
    ScenarioSpec,
    discover_scenarios,
    discovery,
    registered_scenarios,
    scenario_module_stems,
)
from vultron.errors import DemoScenarioRegistryError
from vultron.metadata.demo_scenarios import (
    desired_contents,
    missing_derived_paths,
)

#: The fixture scenario's name; its stem is ``zz_fixture_pkg``.
_NAME = "zz-fixture-pkg"
_STEM = "zz_fixture_pkg_demo"
_MODULE = f"{SCENARIO_PACKAGE}.{_STEM}"

#: The fixture package's files, by path inside the package directory.  The
#: ``__init__`` only re-exports (CS-18-003); ``main()`` is declared in
#: ``cli.py``, a submodule, which is the case registration must accept.
_PACKAGE_FILES = {
    "__init__.py": f"""
        from {_MODULE}.cli import CLI_HELP, ROLES, main

        __all__ = ["CLI_HELP", "ROLES", "main"]
    """,
    "story.py": """
        class _Story:
            path = (
                ("reporter-whom-to-tell", "vendor"),
                ("vendor-after-answer", "report-fix-ready"),
            )


        STORY = _Story()
    """,
    "cli.py": f"""
        from vultron.demo.helpers.actor_roles import case_actor_role
        from vultron.demo.scenario.registry import scenario
        from {_MODULE}.story import STORY

        ROLES = [case_actor_role()]
        CLI_HELP = "Run the package fixture scenario."
        CALLS: list[dict[str, object]] = []


        @scenario(
            name="{_NAME}",
            label="ZZ-fixture-pkg",
            participants="Reporter + Vendor",
            feature="Package-form scenario fixture",
            in_pr_set=False,
            story=STORY,
        )
        def main(
            skip_health_check: bool = False,
            case_actor_url: str | None = None,
        ) -> None:
            CALLS.append(
                {{
                    "skip_health_check": skip_health_check,
                    "case_actor_url": case_actor_url,
                }}
            )
    """,
    "phases/__init__.py": "",
    "phases/deep.py": "DEPTH = 2\n",
    # Keeps `python -m <package>` working, as a module scenario's
    # `if __name__ == "__main__"` guard does.
    "__main__.py": f"""
        from {_MODULE} import main

        main()
    """,
}


def _write(root: Path, files: dict[str, str]) -> None:
    for relative, text in files.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(textwrap.dedent(text).lstrip(), encoding="utf-8")


def _fixture_modules() -> list[str]:
    return [
        name
        for name in sys.modules
        if name == _MODULE or name.startswith(f"{_MODULE}.")
    ]


def _assert_no_leak() -> None:
    """The fixture is in no registry, command table or generated inventory."""
    assert _NAME not in {spec.name for spec in registered_scenarios()}
    assert _NAME not in {spec.name for spec in discover_scenarios()}
    assert _STEM not in scenario_module_stems()
    assert _NAME not in cli.main.commands
    assert not _fixture_modules()
    assert not hasattr(scenario_package, _STEM)
    leaked = [
        path
        for path, text in desired_contents().items()
        if _NAME in text or _STEM in text
    ]
    assert not leaked, f"the fixture scenario reached {leaked}"


@pytest.fixture
def package_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Path]:
    """A repo root holding one package scenario and its derived files.

    Yields the root.  The scenario package's search path is the root's
    ``vultron/demo/scenario`` directory alone while the test runs.
    """
    scenario_dir = tmp_path / SCENARIO_DIR
    _write(scenario_dir / _STEM, _PACKAGE_FILES)
    _write(
        tmp_path,
        {
            "test/ci/invariants/test_zz_fixture_pkg_invariants.py": "",
            f"docs/topics/scenarios/{_NAME}.md": "# fixture\n",
        },
    )
    monkeypatch.setattr(scenario_package, "__path__", [str(scenario_dir)])
    monkeypatch.setattr(discovery, "_REGISTRY", dict(discovery._REGISTRY))
    importlib.invalidate_caches()
    try:
        yield tmp_path
    finally:
        for name in _fixture_modules():
            del sys.modules[name]
        # Importing a submodule binds it on its parent package too.
        if hasattr(scenario_package, _STEM):
            delattr(scenario_package, _STEM)
        monkeypatch.undo()
        importlib.invalidate_caches()
        _assert_no_leak()


def test_a_package_scenario_registers_end_to_end(package_tree: Path) -> None:
    """Discovered, registered, given a sub-command, its derived paths resolve.

    The scenario's ``main()`` is declared in ``cli.py``, a submodule of the
    derived package, so registration accepts it there (DEMOCI-11-003).
    """
    assert scenario_module_stems() == (_STEM,)

    specs = discover_scenarios()

    assert [spec.name for spec in specs] == [_NAME]
    (spec,) = specs
    assert spec.is_package is True
    assert spec.demo_filename == f"{_STEM}/"
    assert spec.demo_path == f"{SCENARIO_DIR}/{_STEM}/"
    assert missing_derived_paths(package_tree, specs) == []

    command = _make_scenario_command(spec)
    assert command.name == _NAME
    result = CliRunner().invoke(
        command, ["--skip-health-check", "--case-actor-url", "http://x:1"]
    )
    assert result.exit_code == 0, result.output
    calls = sys.modules[f"{_MODULE}.cli"].CALLS
    assert calls == [
        {"skip_health_check": True, "case_actor_url": "http://x:1"}
    ]


def test_a_package_scenarios_sources_are_every_submodule(
    package_tree: Path,
) -> None:
    """``source_files`` is every ``.py`` file of the package, at any depth.

    This is what a ratchet reading a scenario's own code scans, so a check
    that read only the ``__init__`` would miss the ``main()`` in ``cli.py``.
    """
    (spec,) = discover_scenarios()
    package_dir = package_tree / SCENARIO_DIR / _STEM
    assert spec.source_files == tuple(
        sorted(package_dir / relative for relative in _PACKAGE_FILES)
    )


def test_a_missing_package_file_is_reported(package_tree: Path) -> None:
    """A derived file that is absent is reported against the package form."""
    (spec,) = discover_scenarios()
    (package_tree / f"docs/topics/scenarios/{_NAME}.md").unlink()
    assert missing_derived_paths(package_tree, (spec,)) == [
        f"{_NAME}: docs/topics/scenarios/{_NAME}.md"
    ]


@pytest.mark.parametrize(
    "origin",
    [
        # A sibling whose name merely starts with the derived module's name.
        f"{_MODULE}_old",
        f"{_MODULE}_old.cli",
        # A submodule of a different scenario.
        f"{SCENARIO_PACKAGE}.rv_demo.cli",
    ],
)
def test_registration_refuses_a_module_outside_the_derived_package(
    origin: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only the derived module and its submodules may declare the scenario."""
    monkeypatch.setattr(discovery, "_REGISTRY", dict(discovery._REGISTRY))
    spec = ScenarioSpec(
        name=_NAME,
        label="ZZ",
        participants="Reporter + Vendor",
        feature="Something",
        in_pr_set=False,
        path=(("reporter-whom-to-tell", "vendor"),),
    )
    with pytest.raises(DemoScenarioRegistryError, match="derives the module"):
        discovery._register(spec, origin)


def test_both_forms_of_one_name_are_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A name present as a module and as a package is one scenario too many.

    The import system loads the package and never reads the module, so the
    module would be dead code that every table still seems to describe.
    """
    _write(tmp_path, {"twin_demo.py": "", "twin_demo/__init__.py": ""})
    monkeypatch.setattr(scenario_package, "__path__", [str(tmp_path)])
    importlib.invalidate_caches()
    with pytest.raises(DemoScenarioRegistryError, match="twin_demo"):
        scenario_module_stems()


def test_a_name_that_resolves_nowhere_reads_as_the_module_form() -> None:
    """With nothing on disk the derived path is the ``.py`` file to report.

    ``source_files`` raises instead, because a ratchet scanning no file would
    pass over the scenario it was asked about.
    """
    spec = ScenarioSpec(
        name="zz-nowhere",
        label="ZZ",
        participants="Reporter + Vendor",
        feature="Something",
        in_pr_set=False,
        path=(("reporter-whom-to-tell", "vendor"),),
    )
    assert spec.is_package is False
    assert spec.demo_path == f"{SCENARIO_DIR}/zz_nowhere_demo.py"
    with pytest.raises(DemoScenarioRegistryError, match="does not resolve"):
        _ = spec.source_files


def test_a_module_scenarios_source_is_its_one_file() -> None:
    """The module form reads exactly its own ``.py`` file."""
    (spec,) = [s for s in discover_scenarios() if s.name == "rv"]
    assert spec.is_package is False
    assert spec.source_files == (
        Path(scenario_package.__file__).parent / "rv_demo.py",
    )


def test_a_package_whose_init_does_not_import_main_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Importing the package must register it, so ``__init__`` re-exports.

    A package whose ``main()`` sits in a submodule that ``__init__`` never
    imports registers nothing on discovery, and is refused rather than
    silently left out of every table.
    """
    files = dict(_PACKAGE_FILES)
    files["__init__.py"] = ""
    _write(tmp_path / _STEM, files)
    monkeypatch.setattr(scenario_package, "__path__", [str(tmp_path)])
    monkeypatch.setattr(discovery, "_REGISTRY", dict(discovery._REGISTRY))
    importlib.invalidate_caches()
    try:
        with pytest.raises(
            DemoScenarioRegistryError, match="imported but not registered"
        ):
            discover_scenarios()
    finally:
        for name in _fixture_modules():
            del sys.modules[name]
        if hasattr(scenario_package, _STEM):
            delattr(scenario_package, _STEM)


def test_a_scenario_directory_without_init_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``pkgutil`` lists no directory without ``__init__.py``, so say so.

    Otherwise the scenario would be missing from the CLI and every table, and
    the set-equality check, which reads packages by their ``__init__.py``,
    would agree with the omission.
    """
    _write(tmp_path, {"lost_demo/cli.py": ""})
    monkeypatch.setattr(scenario_package, "__path__", [str(tmp_path)])
    importlib.invalidate_caches()
    with pytest.raises(DemoScenarioRegistryError, match="lost_demo"):
        scenario_module_stems()


def test_a_directory_holding_only_bytecode_is_ignored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A ``__pycache__`` left behind by a branch switch is no scenario."""
    _write(tmp_path, {"gone_demo/__pycache__/cli.cpython-313.pyc": ""})
    monkeypatch.setattr(scenario_package, "__path__", [str(tmp_path)])
    importlib.invalidate_caches()
    assert scenario_module_stems() == ()


def test_a_namespace_directory_reads_as_no_package(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A directory with no ``__init__.py`` is not the package form.

    The import system resolves it as a namespace package with no origin, so
    the demo path stays the ``.py`` file that the derived-path checks report
    missing, and ``source_files`` raises.
    """
    _write(tmp_path, {"zz_ns_demo/cli.py": ""})
    monkeypatch.setattr(scenario_package, "__path__", [str(tmp_path)])
    importlib.invalidate_caches()
    spec = ScenarioSpec(
        name="zz-ns",
        label="ZZ",
        participants="Reporter + Vendor",
        feature="Something",
        in_pr_set=False,
        path=(("reporter-whom-to-tell", "vendor"),),
    )
    try:
        assert spec.is_package is False
        assert spec.demo_path == f"{SCENARIO_DIR}/zz_ns_demo.py"
        with pytest.raises(
            DemoScenarioRegistryError, match="does not resolve"
        ):
            _ = spec.source_files
    finally:
        sys.modules.pop(f"{SCENARIO_PACKAGE}.zz_ns_demo", None)
