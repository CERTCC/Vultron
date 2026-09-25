"""CI verification test — every site build is strict, so build warnings fail.

Implements DOCBW-03-009, DOCBW-03-010 and DOCBW-03-011 from
``specs/docs-build-workflow.yaml`` (#3051).

``mkdocs.yml`` raises two checks to ``warn`` on purpose: dead in-page anchor
links (``validation.links.anchors``) and pages absent from the nav with no
``not_in_nav`` entry (``validation.nav.omitted_files``). A warning fails
nothing unless the build is ``--strict``, and for months no workflow passed it,
so both settings printed a line and the job stayed green. The gate therefore
has two halves, and this module pins both: every build step is strict, and the
settings stay at ``warn`` — a downgrade to ``info`` turns the gate off as
quietly as dropping the flag.

The last test proves the halves compose. It builds a two-page site in
``tmp_path`` with only the project's ``validation`` block, never the real site
(no test may build ``site/``; the project build takes minutes).
"""

from __future__ import annotations

import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

from test.ci._workflows import (
    MKDOCS_BUILD,
    load_workflow,
    site_building_workflows,
    steps,
)
from vultron.metadata.base import mkdocs_config

STRICT_FLAG = "--strict"
# ``--quiet`` raises the log threshold above WARNING before mkdocs' strict-mode
# counter sees a record, so ``build --strict --quiet`` exits 0 over warnings.
QUIET_FLAGS = ("--quiet", "-q")


def _build_commands(workflow: Path) -> list[str]:
    """Return every ``mkdocs build`` command in the workflow's steps.

    Backslash continuations are joined first, so a flag on a continued line is
    still part of its command.
    """
    return [
        line.strip()
        for step in steps(load_workflow(workflow))
        for line in str(step.get("run", "")).replace("\\\n", " ").splitlines()
        if MKDOCS_BUILD in line
    ]


def _validation() -> dict[str, Any]:
    block = mkdocs_config().get("validation", {})
    return block if isinstance(block, dict) else {}


@pytest.mark.spec("DOCBW-03-009")
@pytest.mark.parametrize(
    "workflow", site_building_workflows(), ids=lambda p: p.name
)
def test_every_site_build_is_strict(workflow: Path):
    """A non-strict build step lets every validation warning pass."""
    commands = _build_commands(workflow)
    assert commands, f"{workflow.name} names 'mkdocs build' in no step."
    for command in commands:
        assert STRICT_FLAG in shlex.split(command), (
            f"{workflow.name} runs {command!r} without {STRICT_FLAG}, so a "
            "dead anchor or un-navved page prints a warning and the job "
            "stays green (DOCBW-03-009)."
        )


@pytest.mark.spec("DOCBW-03-010")
@pytest.mark.parametrize(
    "workflow", site_building_workflows(), ids=lambda p: p.name
)
def test_no_strict_build_is_quiet(workflow: Path):
    """``--quiet`` hides the warnings ``--strict`` counts."""
    for command in _build_commands(workflow):
        quiet = set(QUIET_FLAGS) & set(shlex.split(command))
        assert not quiet, (
            f"{workflow.name} runs {command!r}: {sorted(quiet)} suppresses "
            f"the warnings {STRICT_FLAG} counts, so the build passes over "
            "them (DOCBW-03-010)."
        )


@pytest.mark.spec("DOCBW-03-011")
@pytest.mark.parametrize(
    "section, key",
    [("links", "anchors"), ("nav", "omitted_files")],
)
def test_validation_setting_stays_at_warn(section: str, key: str):
    """``info`` is below what ``--strict`` counts, so a downgrade is silent."""
    value = _validation().get(section, {}).get(key)
    assert value == "warn", (
        f"mkdocs.yml validation.{section}.{key} is {value!r}, not 'warn'. "
        "Below warn, --strict never sees the defect it exists to catch "
        "(DOCBW-03-011)."
    )


def _mini_site(tmp_path: Path, index_body: str, extra_page: bool) -> Path:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "index.md").write_text(f"# Home\n\n{index_body}\n", "utf-8")
    if extra_page:
        (docs / "orphan.md").write_text("# Orphan\n", "utf-8")
    config = {
        "site_name": "strict-gate-fixture",
        "nav": ["index.md"],
        "validation": _validation(),
    }
    (tmp_path / "mkdocs.yml").write_text(yaml.safe_dump(config), "utf-8")
    return tmp_path


def _strict_build(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "mkdocs", "build", STRICT_FLAG],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.spec("DOCBW-03-011")
def test_strict_build_with_project_validation_passes_a_clean_site(
    tmp_path: Path,
):
    """Control: the fixture itself is clean, so the failures below are real."""
    result = _strict_build(_mini_site(tmp_path, "[Top](#home)", False))
    assert result.returncode == 0, result.stderr


@pytest.mark.spec("DOCBW-03-011")
@pytest.mark.parametrize(
    "index_body, extra_page, expected",
    [
        ("[Gone](#no-such-heading)", False, "no-such-heading"),
        ("[Top](#home)", True, "orphan.md"),
    ],
    ids=["dead-in-page-anchor", "page-missing-from-nav"],
)
def test_strict_build_with_project_validation_fails(
    tmp_path: Path, index_body: str, extra_page: bool, expected: str
):
    """#3051 AC-1 and AC-2: each defect fails a strict build."""
    result = _strict_build(_mini_site(tmp_path, index_body, extra_page))
    assert result.returncode != 0, (
        f"A strict build with the project's validation settings passed a "
        f"site containing {expected!r}."
    )
    assert expected in result.stderr, result.stderr
