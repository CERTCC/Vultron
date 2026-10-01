"""Smoke tests for ``scripts/relabel_spec_kinds.py`` and its item slicer.

The relabel is line-based YAML surgery, so the property that matters is that
nothing outside the targeted lines changes. Each fixture below exercises one
shape the live corpus presented in #3600: a block-style ``lint_suppress:`` with
another code that must survive, a flow-style list that empties, a block whose
items carry justification comments (CP-01-007), a suppression-only entry, and
an item the mapping never names.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).parents[3] / "scripts"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(
        name, _SCRIPTS / f"{name}.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


relabel = _load("relabel_spec_kinds")
items = _load("_spec_yaml_items")

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
    lint_suppress:
    - phantom_path_ref
    - missing_story_reference
  - id: TST-01-002
    priority: MUST
    kind: protocol
    statement: TST-01-002 MUST do the thing
    lint_suppress: [missing_story_reference]
  - id: TST-01-003
    lint_suppress:
    - rationale_too_long
    # No story for the same reason as its parent: internal plumbing the story
    # corpus never asked for.
    - missing_story_reference
    priority: MUST
    kind: protocol
    statement: >-
      TST-01-003 MUST do the thing
      across two lines.
  - id: TST-01-004
    priority: MUST
    kind: project
    statement: TST-01-004 MUST do the thing
    lint_suppress:
    - missing_story_reference
  - id: TST-01-005
    priority: MUST
    kind: protocol
    statement: TST-01-005 MUST stay exactly as it is
    lint_suppress:
    - missing_story_reference
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
    kind: project
    statement: TST-01-001 MUST do the thing
    lint_suppress:
    - phantom_path_ref
  - id: TST-01-002
    priority: MUST
    kind: process
    statement: TST-01-002 MUST do the thing
  - id: TST-01-003
    lint_suppress:
    - rationale_too_long
    priority: MUST
    kind: project
    statement: >-
      TST-01-003 MUST do the thing
      across two lines.
  - id: TST-01-004
    priority: MUST
    kind: project
    statement: TST-01-004 MUST do the thing
  - id: TST-01-005
    priority: MUST
    kind: protocol
    statement: TST-01-005 MUST stay exactly as it is
    lint_suppress:
    - missing_story_reference
"""


def _run(
    tmp_path: Path, mapping: dict, *flags: str, text: str = _FIXTURE
) -> tuple[int, str]:
    specs_dir = tmp_path / "specs"
    specs_dir.mkdir()
    (specs_dir / "tst.yaml").write_text(text, encoding="utf-8")
    mapping_path = tmp_path / "mapping.json"
    mapping_path.write_text(json.dumps(mapping), encoding="utf-8")
    rc = relabel.main(
        [str(mapping_path), "--specs-dir", str(specs_dir), *flags]
    )
    return rc, (specs_dir / "tst.yaml").read_text(encoding="utf-8")


_MAPPING = {
    "TST-01-001": "project",  # block list keeps its other code
    "TST-01-002": "process",  # flow list empties and disappears
    "TST-01-003": "project",  # justification comments leave with the item
    "TST-01-004": None,  # suppression-only: kind untouched
}


def test_relabel_rewrites_only_the_targeted_lines(tmp_path):
    rc, text = _run(tmp_path, _MAPPING)
    assert rc == 0
    assert text == _EXPECTED


def test_dry_run_changes_nothing(tmp_path):
    rc, text = _run(tmp_path, _MAPPING, "--dry-run")
    assert rc == 0
    assert text == _FIXTURE


def test_unknown_spec_id_fails_the_run(tmp_path, capsys):
    rc, text = _run(tmp_path, {**_MAPPING, "TST-09-999": "project"})
    assert rc == 1
    assert "TST-09-999" in capsys.readouterr().err
    assert text == _EXPECTED  # the known entries were still applied


def test_relabel_reports_tallies(tmp_path, capsys):
    _run(tmp_path, _MAPPING)
    out = capsys.readouterr().out
    assert (
        "3 kind(s) relabeled; 4 missing_story_reference suppression(s) removed"
        in out
    )


@pytest.mark.parametrize("text", [_FIXTURE, _EXPECTED])
def test_iter_blocks_round_trips_the_file(text):
    lines = text.splitlines(keepends=True)
    rebuilt = "".join(
        b if isinstance(b, str) else "".join(b.lines)
        for b in items.iter_blocks(lines)
    )
    assert rebuilt == text


def test_iter_blocks_slices_items_at_their_indent():
    lines = _FIXTURE.splitlines(keepends=True)
    found = [b for b in items.iter_blocks(lines) if not isinstance(b, str)]
    assert [b.spec_id for b in found] == [f"TST-01-00{n}" for n in range(1, 6)]
    assert all(b.indent == "  " and b.field_indent == "    " for b in found)
    # the multi-line block scalar belongs to its item
    assert any("across two lines." in line for line in found[2].lines)


# ---------------------------------------------------------------------------
# Shapes the live corpus did not present, which the script must still handle
# without editing anything it was not asked to.
# ---------------------------------------------------------------------------

_HEADER = """\
id: TST
title: Test
description: Test spec file
scope: [production]
groups:
- id: TST-01
  title: Group
  specs:
"""


def test_kind_with_trailing_comment_is_relabeled_and_keeps_the_comment(
    tmp_path,
):
    text = _HEADER + (
        "  - id: TST-01-001\n"
        "    priority: MUST\n"
        "    kind: protocol  # decided in #1234\n"
        "    statement: TST-01-001 MUST do the thing\n"
    )
    rc, out = _run(tmp_path, {"TST-01-001": "project"}, text=text)
    assert rc == 0
    assert "    kind: project  # decided in #1234\n" in out


def test_quoted_and_commented_list_entries_are_parsed(tmp_path):
    text = _HEADER + (
        "  - id: TST-01-001\n"
        "    priority: MUST\n"
        "    kind: protocol\n"
        "    statement: TST-01-001 MUST do the thing\n"
        "    lint_suppress:\n"
        '    - "phantom_path_ref"  # the path is illustrative\n'
        "    - missing_story_reference  # no story yet\n"
    )
    rc, out = _run(tmp_path, {"TST-01-001": "project"}, text=text)
    assert rc == 0
    assert out.endswith(
        "    lint_suppress:\n"
        '    - "phantom_path_ref"  # the path is illustrative\n'
    )
    assert "missing_story_reference" not in out


@pytest.mark.parametrize(
    ("flow", "expected"),
    [
        ("['missing_story_reference']", None),
        ('["missing_story_reference"]', None),
        ("[missing_story_reference]  # no story yet", None),
        (
            "['phantom_path_ref', 'missing_story_reference']  # path is a sketch",
            "    lint_suppress: ['phantom_path_ref']  # path is a sketch\n",
        ),
    ],
)
def test_quoted_and_commented_flow_entries_are_stripped(
    tmp_path, flow, expected
):
    text = _HEADER + (
        "  - id: TST-01-001\n"
        "    priority: MUST\n"
        "    kind: protocol\n"
        "    statement: TST-01-001 MUST do the thing\n"
        f"    lint_suppress: {flow}\n"
    )
    rc, out = _run(tmp_path, {"TST-01-001": "project"}, text=text)
    assert rc == 0
    assert "missing_story_reference" not in out
    if expected is None:
        assert "lint_suppress" not in out
    else:
        assert out.endswith(expected)


def test_null_lint_suppress_header_is_left_alone(tmp_path):
    text = _HEADER + (
        "  - id: TST-01-001\n"
        "    priority: MUST\n"
        "    kind: protocol\n"
        "    lint_suppress:\n"
        "    statement: TST-01-001 MUST do the thing\n"
    )
    rc, out = _run(tmp_path, {"TST-01-001": "project"}, text=text)
    assert rc == 0
    assert out == text.replace("kind: protocol", "kind: project")


def test_unparseable_list_entry_raises_instead_of_orphaning_it(tmp_path):
    text = _HEADER + (
        "  - id: TST-01-001\n"
        "    priority: MUST\n"
        "    kind: protocol\n"
        "    statement: TST-01-001 MUST do the thing\n"
        "    lint_suppress:\n"
        "    - {code: missing_story_reference}\n"
    )
    with pytest.raises(ValueError, match="unparseable lint_suppress entry"):
        _run(tmp_path, {"TST-01-001": "project"}, text=text)


def test_missing_kind_line_is_reported_and_fails_the_run(tmp_path, capsys):
    text = _HEADER + (
        "  - id: TST-01-001\n"
        "    priority: MUST\n"
        "    statement: TST-01-001 MUST do the thing\n"
        "    lint_suppress: [missing_story_reference]\n"
    )
    rc, out = _run(tmp_path, {"TST-01-001": "project"}, text=text)
    assert rc == 1
    assert "TST-01-001" in capsys.readouterr().err
    assert "lint_suppress" not in out  # the suppression was still stripped


def test_specs_dir_without_a_value_is_a_usage_error(tmp_path, capsys):
    mapping_path = tmp_path / "mapping.json"
    mapping_path.write_text("{}", encoding="utf-8")
    rc = relabel.main([str(mapping_path), "--specs-dir"])
    assert rc == 2
    assert "--specs-dir" in capsys.readouterr().err
