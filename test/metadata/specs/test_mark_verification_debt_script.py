"""Tests for ``scripts/mark_verification_debt.py`` (the #4199 migration).

The script is line-based YAML surgery that must be safe to re-run: it adds a
marker where one is owed, removes a stale one, strips the retired suppression,
and leaves every other line byte for byte.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

from vultron.metadata.specs.registry import load_registry
from vultron.metadata.specs.schema import SpecKind
from vultron.metadata.specs.verification import (
    VERIFICATION_DEBT_OWNERS,
    verification_problems,
)

_SCRIPTS = Path(__file__).parents[3] / "scripts"


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        name, _SCRIPTS / f"{name}.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


mark = _load("mark_verification_debt")

_FIXTURE = """\
id: TST
title: Test
description: Test spec file
scope: [production]
groups:
- id: TST-01
  title: Group
  specs:
  - id: TST-01-001
    priority: MUST
    kind: protocol
    statement: TST-01-001 MUST do the thing
  - id: TST-01-002
    priority: MUST_NOT
    kind: protocol # trailing comment stays
    lint_suppress:
    - phantom_path_ref
    - must_without_verification
    statement: TST-01-002 MUST NOT do the thing
  - id: TST-01-003
    priority: MUST
    kind: protocol
    verification_debt: '#3612'
    verification: Now checked by a test.
    statement: TST-01-003 MUST do the thing
  - id: TST-01-004
    priority: SHOULD
    kind: protocol
    statement: TST-01-004 SHOULD do the thing
  - id: TST-01-005
    priority: MUST
    kind: protocol
    verification: A test.
    statement: TST-01-005 MUST do the thing
"""

_EXPECTED = """\
id: TST
title: Test
description: Test spec file
scope: [production]
groups:
- id: TST-01
  title: Group
  specs:
  - id: TST-01-001
    priority: MUST
    kind: protocol
    verification_debt: '#3612'
    statement: TST-01-001 MUST do the thing
  - id: TST-01-002
    priority: MUST_NOT
    kind: protocol # trailing comment stays
    verification_debt: '#3612'
    lint_suppress:
    - phantom_path_ref
    statement: TST-01-002 MUST NOT do the thing
  - id: TST-01-003
    priority: MUST
    kind: protocol
    verification: Now checked by a test.
    statement: TST-01-003 MUST do the thing
  - id: TST-01-004
    priority: SHOULD
    kind: protocol
    statement: TST-01-004 SHOULD do the thing
  - id: TST-01-005
    priority: MUST
    kind: protocol
    verification: A test.
    statement: TST-01-005 MUST do the thing
"""


def _run(tmp_path: Path, text: str, name: str = "tst.yaml", *flags: str):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    code = mark.main(["--specs-dir", str(tmp_path), *flags])
    return code, path.read_text(encoding="utf-8")


def test_sync_adds_removes_and_strips_and_touches_nothing_else(tmp_path):
    code, text = _run(tmp_path, _FIXTURE)
    assert code == 0
    assert text == _EXPECTED


def test_rerun_is_a_no_op(tmp_path):
    _run(tmp_path, _FIXTURE)
    code, text = _run(tmp_path, _EXPECTED)
    assert code == 0
    assert text == _EXPECTED


def test_dry_run_changes_nothing(tmp_path):
    code, text = _run(tmp_path, _FIXTURE, "tst.yaml", "--dry-run")
    assert code == 0
    assert text == _FIXTURE


def test_result_passes_the_per_item_check(tmp_path):
    _run(tmp_path, _FIXTURE)
    problems = verification_problems(
        load_registry(tmp_path), VERIFICATION_DEBT_OWNERS
    )
    assert problems == []


@pytest.mark.parametrize(
    ("stem", "owner"),
    [
        ("multi-actor-demo", "#2573"),
        ("demo-cli", "#2573"),
        ("spec-registry", "#2574"),
        ("notes-frontmatter", "#2574"),
        ("datalayer", "#2575"),
    ],
)
def test_project_owner_follows_the_file_group(stem, owner):
    assert mark.owner_for(SpecKind.PROJECT, stem) == owner


@pytest.mark.parametrize(
    "kind", [k for k in SpecKind if k is not SpecKind.PROJECT]
)
def test_other_kinds_take_their_single_owner(kind):
    assert {mark.owner_for(kind, "anything")} == VERIFICATION_DEBT_OWNERS[kind]


def test_every_project_owner_is_in_the_owner_table():
    owners = {
        *mark._PROJECT_FILE_OWNERS.values(),
        mark._PROJECT_DEFAULT_OWNER,
    }
    assert owners == VERIFICATION_DEBT_OWNERS[SpecKind.PROJECT]


def test_wrong_kind_marker_is_reported_not_rewritten(tmp_path, capsys):
    """A relabel that kept its old marker (MS-10-008) needs a verification:
    clause, which the script cannot write."""
    text = _FIXTURE.replace(
        "    kind: protocol\n    statement: TST-01-001",
        "    kind: process\n    verification_debt: '#3612'\n"
        "    statement: TST-01-001",
    )
    code, after = _run(tmp_path, text)
    assert code == 1
    assert "verification_debt: '#3612'\n    statement: TST-01-001" in after
    assert "TST-01-001" in capsys.readouterr().err


def test_specs_dir_without_a_value_is_a_usage_error(capsys):
    assert mark.main(["--specs-dir"]) == 2
    assert "requires a directory" in capsys.readouterr().err


def test_unknown_argument_is_a_usage_error():
    assert mark.main(["--bogus"]) == 2
