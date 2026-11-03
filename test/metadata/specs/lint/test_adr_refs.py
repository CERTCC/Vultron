"""Tests for vultron.metadata.specs.lint.adr_refs: ADR reference and ADR status
checks (MS-14-001, MS-14-013, SR-02-020).
"""

from typing import cast

import pytest

import vultron.metadata.specs.lint.adr_refs as lint_module
from test.metadata._adr_stubs import write_adr_stub
from test.metadata.specs._helpers import write_yaml
from test.metadata.specs.lint._helpers import (
    _make_adr_dir,
    _minimal_spec,
    _write_dated_adr,
)
from vultron.metadata.specs.lint import lint
from vultron.metadata.specs.registry import SpecRegistry


def _write_successor_stub(adr_dir, num, supersedes):
    """Write an accepted ADR that records the ADR it supersedes (MS-14-011).

    A supersession link must be recorded on both ADRs, so a fixture retiring
    an ADR also needs the successor-side ``supersedes`` entry.
    """
    write_adr_stub(adr_dir, f"{num}-stub.md", supersedes=supersedes)


def test_lint_adr_ref_missing_emits_warn(tmp_path, capsys):
    """A rationale referencing ADR-0099 that has no file emits a [WARN]."""
    data = _minimal_spec(extra={"rationale": "Derived from ADR-0099."})
    write_yaml(tmp_path, data)
    adr_dir = _make_adr_dir(tmp_path)  # no 0099 file
    result = lint(tmp_path, adr_dir=adr_dir)
    captured = capsys.readouterr()
    assert result == 0  # advisory only, not a hard error
    assert "[WARN]" in captured.out
    assert "ADR-0099" in captured.out


def test_lint_adr_ref_present_no_warn(tmp_path, capsys):
    """A rationale referencing ADR-0099 when the file exists emits no warning."""
    data = _minimal_spec(extra={"rationale": "Derived from ADR-0099."})
    write_yaml(tmp_path, data)
    adr_dir = _make_adr_dir(tmp_path, ["0099"])
    result = lint(tmp_path, adr_dir=adr_dir)
    captured = capsys.readouterr()
    assert result == 0
    assert "ADR-0099" not in captured.out


def test_lint_adr_ref_no_adr_dir_skips_check(tmp_path, capsys):
    """When adr_dir does not exist the check is silently skipped."""
    data = _minimal_spec(extra={"rationale": "Derived from ADR-0099."})
    write_yaml(tmp_path, data)
    nonexistent = tmp_path / "nonexistent" / "adr"
    result = lint(tmp_path, adr_dir=nonexistent)
    captured = capsys.readouterr()
    assert result == 0
    assert "ADR-0099" not in captured.out


def test_lint_adr_ref_suppress(tmp_path, capsys):
    """dangling_adr_ref can be suppressed via lint_suppress."""
    data = _minimal_spec(
        extra={
            "rationale": "Derived from ADR-0099.",
            "lint_suppress": ["dangling_adr_ref"],
        }
    )
    write_yaml(tmp_path, data)
    adr_dir = _make_adr_dir(tmp_path)  # no 0099 file
    result = lint(tmp_path, adr_dir=adr_dir)
    captured = capsys.readouterr()
    assert result == 0
    assert "ADR-0099" not in captured.out


def test_lint_adr_ref_rationale_without_adr_no_warn(tmp_path, capsys):
    """A rationale that names no ADR produces no ADR warning."""
    data = _minimal_spec()
    write_yaml(tmp_path, data)
    adr_dir = _make_adr_dir(tmp_path)
    result = lint(tmp_path, adr_dir=adr_dir)
    captured = capsys.readouterr()
    assert result == 0
    assert "ADR-" not in captured.out


# ---------------------------------------------------------------------------
# ADR status frontmatter (MS-14-001 hard, MS-14-013 advisory) — ADR-0041
# ---------------------------------------------------------------------------


def _write_adr(adr_dir, num, status=None, body=""):
    """Write an ADR file; omit the status line entirely when status is None."""
    fm = (
        f"---\nstatus: {status}\ncreated: 2020-01-01\nupdated: 2020-01-01\nrevision: 1\nstatus_override: test fixture\n---\n"
        if status is not None
        else "---\n---\n"
    )
    (adr_dir / f"{num}-stub.md").write_text(f"{fm}# ADR-{num}\n{body}\n")


def test_lint_adr_missing_status_is_hard_error(tmp_path, capsys):
    """An ADR with no status frontmatter is a hard error (MS-14-001)."""
    write_yaml(tmp_path, _minimal_spec())
    adr_dir = _make_adr_dir(tmp_path)
    _write_adr(adr_dir, "0099", status=None)
    result = lint(tmp_path, adr_dir=adr_dir)
    captured = capsys.readouterr()
    assert result == 1
    assert "MS-14-001" in captured.err
    assert "0099" in captured.err


def test_lint_adr_invalid_status_is_hard_error(tmp_path, capsys):
    """An ADR with an unknown status value is a hard error (MS-14-001)."""
    write_yaml(tmp_path, _minimal_spec())
    adr_dir = _make_adr_dir(tmp_path)
    _write_adr(adr_dir, "0099", status="kinda-accepted")
    result = lint(tmp_path, adr_dir=adr_dir)
    captured = capsys.readouterr()
    assert result == 1
    assert "MS-14-001" in captured.err


def test_lint_adr_superseded_status_ok(tmp_path):
    """A superseded ADR with a resolvable superseded_by target is valid."""
    write_yaml(tmp_path, _minimal_spec())
    adr_dir = _make_adr_dir(tmp_path)
    _write_successor_stub(adr_dir, "0100", supersedes="0099-stub.md")
    (adr_dir / "0099-stub.md").write_text(
        "---\nstatus: superseded\ncreated: 2020-01-01\nupdated: 2020-01-01\nrevision: 1\nsuperseded_by: 0100-stub.md\n---\n# x\n"
    )
    result = lint(tmp_path, adr_dir=adr_dir)
    assert result == 0


def test_lint_adr_superseded_inline_form_ok(tmp_path):
    """The inline 'superseded by <link>' MADR form is accepted and resolved."""
    write_yaml(tmp_path, _minimal_spec())
    adr_dir = _make_adr_dir(tmp_path)
    _write_successor_stub(adr_dir, "0100", supersedes="0099-stub.md")
    (adr_dir / "0099-stub.md").write_text(
        "---\nstatus: superseded by 0100-stub.md\ncreated: 2020-01-01\nupdated: 2020-01-01\nrevision: 1\n---\n# x\n"
    )
    result = lint(tmp_path, adr_dir=adr_dir)
    assert result == 0


def test_lint_adr_superseded_without_target_is_hard_error(tmp_path, capsys):
    """A retired ADR missing superseded_by is a hard error (MS-14-004)."""
    write_yaml(tmp_path, _minimal_spec())
    adr_dir = _make_adr_dir(tmp_path)
    (adr_dir / "0099-stub.md").write_text(
        "---\nstatus: superseded\ncreated: 2020-01-01\nupdated: 2020-01-01\nrevision: 1\n---\n# x\n"
    )
    result = lint(tmp_path, adr_dir=adr_dir)
    captured = capsys.readouterr()
    assert result == 1
    assert "superseded_by" in captured.err


def test_lint_adr_accepted_with_provisional_prose_warns(tmp_path, capsys):
    """status: accepted + provisional prose is an advisory warning (MS-14-013)."""
    write_yaml(tmp_path, _minimal_spec())
    adr_dir = _make_adr_dir(tmp_path)
    _write_adr(
        adr_dir,
        "0099",
        status="accepted",
        body="This design is formed in sand.",
    )
    result = lint(tmp_path, adr_dir=adr_dir)
    captured = capsys.readouterr()
    assert result == 0  # advisory, not a hard error
    assert "MS-14-013" in captured.out
    assert "[WARN]" in captured.out


def test_lint_adr_accepted_provisional_status_no_warn(tmp_path, capsys):
    """accepted-provisional + provisional prose is consistent — no warning."""
    write_yaml(tmp_path, _minimal_spec())
    adr_dir = _make_adr_dir(tmp_path)
    _write_adr(
        adr_dir,
        "0099",
        status="accepted-provisional",
        body="This design is formed in sand.",
    )
    result = lint(tmp_path, adr_dir=adr_dir)
    captured = capsys.readouterr()
    assert result == 0
    assert "MS-14-013" not in captured.out


# ---------------------------------------------------------------------------
# Structured adr: field references (SR-02-020) — hard error on dangling target
# ---------------------------------------------------------------------------


def test_lint_structured_adr_ref_missing_is_hard_error(tmp_path, capsys):
    """A structured adr: target with no ADR file is a hard error."""
    data = _minimal_spec(extra={"adr": ["ADR-0099"]})
    write_yaml(tmp_path, data)
    adr_dir = _make_adr_dir(tmp_path)  # no 0099 file
    result = lint(tmp_path, adr_dir=adr_dir)
    captured = capsys.readouterr()
    assert result == 1
    assert "ADR-0099" in captured.err


def test_lint_structured_adr_ref_present_ok(tmp_path, capsys):
    """A structured adr: target that resolves to a file is clean."""
    data = _minimal_spec(extra={"adr": ["ADR-0099"]})
    write_yaml(tmp_path, data)
    adr_dir = _make_adr_dir(tmp_path, ["0099"])
    result = lint(tmp_path, adr_dir=adr_dir)
    assert result == 0


def test_lint_structured_adr_ref_resolves_to_archived(tmp_path):
    """A structured adr: target in docs/adr/archived/ resolves (no error)."""
    data = _minimal_spec(extra={"adr": ["ADR-0099"]})
    write_yaml(tmp_path, data)
    adr_dir = _make_adr_dir(tmp_path)
    archived = adr_dir / "archived"
    archived.mkdir()
    (archived / "0099-stub.md").write_text(
        "---\nstatus: deprecated\ncreated: 2020-01-01\nupdated: 2020-01-01\nrevision: 1\nsuperseded_by: 0100-stub.md\n---\n# x\n"
    )
    _write_successor_stub(adr_dir, "0100", supersedes="ADR-0099")
    result = lint(tmp_path, adr_dir=adr_dir)
    assert result == 0


def test_lint_adr_status_prose_suppress(tmp_path, capsys):
    """lint_suppress: [status_prose_contradiction] silences the MS-14-013 warn."""
    write_yaml(tmp_path, _minimal_spec())
    adr_dir = _make_adr_dir(tmp_path)
    (adr_dir / "0099-stub.md").write_text(
        "---\nstatus: accepted\ncreated: 2020-01-01\nupdated: 2020-01-01\nrevision: 1\n"
        "lint_suppress: [status_prose_contradiction]\n---\n"
        "# ADR-0099\nThis ADR is formed in sand.\n"
    )
    result = lint(tmp_path, adr_dir=adr_dir)
    captured = capsys.readouterr()
    assert result == 0
    assert "MS-14-013" not in captured.out


@pytest.mark.spec("MS-14-021")
def test_lint_adr_status_disagreeing_with_epoch_is_not_a_lint_failure(
    tmp_path, capsys
):
    """The clock alone never fails the full lint: a stale status is the drift
    report's and the diff-based edit check's, not spec-lint's (#4340)."""
    write_yaml(tmp_path, _minimal_spec())
    adr_dir = _make_adr_dir(tmp_path)
    _write_dated_adr(adr_dir, "0099", "proposed", "2020-01-01")
    assert lint(tmp_path, adr_dir=adr_dir) == 0
    assert "MS-14-007" not in capsys.readouterr().err


@pytest.mark.spec("MS-14-010")
def test_lint_warns_on_a_proposed_adr_with_tested_dependents(tmp_path):
    """A tested dependent ends epoch 1 with no clock, so spec-lint can say so;
    it warns, and never tells a human to promote with an override."""
    adr_dir = _make_adr_dir(tmp_path)
    _write_dated_adr(adr_dir, "0099", "proposed", "2026-10-20")
    _write_dated_adr(adr_dir, "0098", "accepted-provisional", "2026-10-20")
    _write_dated_adr(
        adr_dir, "0097", "proposed", "2026-10-20", "status_override: held\n"
    )
    (tmp_path / "test").mkdir()
    (tmp_path / "test" / "test_dep.py").write_text("")

    class _Reg:
        all_specs = {
            "TST-01-001": type(
                "S",
                (),
                {
                    "adr": ["ADR-0099", "ADR-0098", "ADR-0097"],
                    "verification": "`test/test_dep.py` checks it",
                },
            )()
        }

    errors, warnings = lint_module._check_adr_status(
        adr_dir, cast(SpecRegistry, _Reg())
    )
    assert errors == []
    (warning,) = [w for w in warnings if "MS-14-010" in w]
    assert warning.startswith("[WARN] 0099-stub.md")
    assert "TST-01-001" in warning
    assert "status_override" not in warning
    assert not [w for w in warnings if w.startswith("[INFO]")]
