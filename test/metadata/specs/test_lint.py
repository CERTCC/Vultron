"""Tests for vultron.metadata.specs.lint (SR.2.4).

Covers: hard-error checks (duplicate IDs, dangling relationships, prefix
mismatch) and advisory warnings (testable_without_steps, rationale_too_long,
missing_tags) including lint_suppress suppression.
"""

import yaml

from vultron.metadata.specs.lint import lint

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_yaml(path, data, filename="specs.yaml"):
    (path / filename).write_text(yaml.dump(data))


def _minimal_spec(spec_id="TST-01-001", priority="MUST", extra=None):
    spec = {
        "id": spec_id,
        "priority": priority,
        "kind": "general",
        "statement": f"{spec_id} MUST do the thing",
        "rationale": "Because testing",
        "tags": ["testing"],
    }
    if extra:
        spec.update(extra)
    return {
        "id": "TST",
        "title": "Test File",
        "description": "Test spec file",
        "version": "0.1",
        "scope": ["production"],
        "groups": [
            {
                "id": "TST-01",
                "title": "Group",
                "specs": [spec],
            }
        ],
    }


# ---------------------------------------------------------------------------
# Clean cases
# ---------------------------------------------------------------------------


def test_lint_clean_dir(tmp_path, capsys):
    _write_yaml(tmp_path, _minimal_spec())
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 0
    assert "[ERROR]" not in captured.err


def test_lint_empty_dir(tmp_path):
    result = lint(tmp_path)
    assert result == 0


# ---------------------------------------------------------------------------
# Hard errors
# ---------------------------------------------------------------------------


def test_lint_duplicate_spec_ids(tmp_path, capsys):
    data = _minimal_spec("DUP-01-001")
    data["id"] = "DUP"
    data["groups"][0]["id"] = "DUP-01"
    data["groups"][0]["specs"][0]["statement"] = "DUP-01-001 MUST be unique"
    _write_yaml(tmp_path, data, "file1.yaml")
    _write_yaml(tmp_path, data, "file2.yaml")
    result = lint(tmp_path)
    assert result == 1


def test_lint_dangling_relationship(tmp_path, capsys):
    data = _minimal_spec(
        extra={
            "relationships": [
                {"rel_type": "depends_on", "spec_id": "XX-99-999"}
            ]
        }
    )
    _write_yaml(tmp_path, data)
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 1
    assert "XX-99-999" in captured.err


def test_lint_prefix_mismatch(tmp_path, capsys):
    data = {
        "id": "TST",
        "title": "Test File",
        "description": "Prefix mismatch test",
        "version": "0.1",
        "scope": ["production"],
        "groups": [
            {
                "id": "OTHER-01",  # prefix "OTHER" != file id "TST"
                "title": "Wrong Group",
                "specs": [
                    {
                        "id": "OTHER-01-001",
                        "priority": "MUST",
                        "kind": "general",
                        "statement": "OTHER-01-001 MUST be consistent",
                        "rationale": "Consistency",
                        "tags": ["testing"],
                    }
                ],
            }
        ],
    }
    _write_yaml(tmp_path, data)
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 1
    assert "OTHER-01" in captured.err


# ---------------------------------------------------------------------------
# Advisory warnings (non-blocking — return 0)
# ---------------------------------------------------------------------------


def test_lint_advisory_testable_without_steps(tmp_path, capsys):
    data = _minimal_spec(extra={"testable": False})
    _write_yaml(tmp_path, data)
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 0
    assert "[WARN]" in captured.out
    assert "testable=false" in captured.out


def test_lint_advisory_rationale_too_long(tmp_path, capsys):
    data = _minimal_spec(extra={"rationale": "x" * 501})
    _write_yaml(tmp_path, data)
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 0
    assert "[WARN]" in captured.out
    assert "rationale" in captured.out


def test_lint_advisory_missing_tags(tmp_path, capsys):
    data = _minimal_spec()
    del data["groups"][0]["specs"][0]["tags"]
    _write_yaml(tmp_path, data)
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 0
    assert "[WARN]" in captured.out
    assert "tags" in captured.out


# ---------------------------------------------------------------------------
# lint_suppress suppression
# ---------------------------------------------------------------------------


def test_lint_suppress_testable_without_steps(tmp_path, capsys):
    data = _minimal_spec(
        extra={
            "testable": False,
            "lint_suppress": ["testable_without_steps"],
        }
    )
    _write_yaml(tmp_path, data)
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 0
    assert "testable=false" not in captured.out


def test_lint_suppress_rationale_too_long(tmp_path, capsys):
    data = _minimal_spec(
        extra={
            "rationale": "x" * 501,
            "lint_suppress": ["rationale_too_long"],
        }
    )
    _write_yaml(tmp_path, data)
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 0
    assert "rationale exceeds" not in captured.out


def test_lint_suppress_missing_tags(tmp_path, capsys):
    data = _minimal_spec()
    del data["groups"][0]["specs"][0]["tags"]
    data["groups"][0]["specs"][0]["lint_suppress"] = ["missing_tags"]
    _write_yaml(tmp_path, data)
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 0
    assert "no tags" not in captured.out


# ---------------------------------------------------------------------------
# Spec ID vs group prefix check (MS-04-004)
# ---------------------------------------------------------------------------


def test_lint_spec_id_prefix_mismatch(tmp_path, capsys):
    """A spec with ID TST-01-001 living in group TST-02 must be a hard error."""
    data = {
        "id": "TST",
        "title": "Test File",
        "description": "Spec ID prefix mismatch test",
        "version": "0.1",
        "scope": ["production"],
        "groups": [
            {
                "id": "TST-02",
                "title": "Group Two",
                "specs": [
                    {
                        "id": "TST-01-001",  # prefix TST-01 != group TST-02
                        "priority": "MUST",
                        "kind": "general",
                        "statement": "TST-01-001 MUST be in group TST-01",
                        "rationale": "Prefix consistency",
                        "tags": ["testing"],
                    }
                ],
            }
        ],
    }
    _write_yaml(tmp_path, data)
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 1
    assert "TST-01-001" in captured.err
    assert "TST-02" in captured.err


def test_lint_spec_id_prefix_match_passes(tmp_path, capsys):
    """A spec ID whose prefix matches its group must not produce an error."""
    data = _minimal_spec("TST-01-001")  # lives in group TST-01 — correct
    _write_yaml(tmp_path, data)
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 0
    assert "TST-01-001" not in captured.err


# ---------------------------------------------------------------------------
# ADR reference check (dangling_adr_ref) — advisory, non-blocking
# ---------------------------------------------------------------------------


def _make_adr_dir(tmp_path, adr_numbers=None):
    """Create a fake docs/adr/ directory with stub ADR files."""
    adr_dir = tmp_path / "docs" / "adr"
    adr_dir.mkdir(parents=True)
    for num in adr_numbers or []:
        (adr_dir / f"{num}-stub.md").write_text(f"# ADR-{num}\n")
    return adr_dir


def test_lint_adr_ref_missing_emits_warn(tmp_path, capsys):
    """A rationale referencing ADR-0099 that has no file emits a [WARN]."""
    data = _minimal_spec(extra={"rationale": "Derived from ADR-0099."})
    _write_yaml(tmp_path, data)
    adr_dir = _make_adr_dir(tmp_path)  # no 0099 file
    result = lint(tmp_path, adr_dir=adr_dir)
    captured = capsys.readouterr()
    assert result == 0  # advisory only, not a hard error
    assert "[WARN]" in captured.out
    assert "ADR-0099" in captured.out


def test_lint_adr_ref_present_no_warn(tmp_path, capsys):
    """A rationale referencing ADR-0099 when the file exists emits no warning."""
    data = _minimal_spec(extra={"rationale": "Derived from ADR-0099."})
    _write_yaml(tmp_path, data)
    adr_dir = _make_adr_dir(tmp_path, ["0099"])
    result = lint(tmp_path, adr_dir=adr_dir)
    captured = capsys.readouterr()
    assert result == 0
    assert "ADR-0099" not in captured.out


def test_lint_adr_ref_no_adr_dir_skips_check(tmp_path, capsys):
    """When adr_dir does not exist the check is silently skipped."""
    data = _minimal_spec(extra={"rationale": "Derived from ADR-0099."})
    _write_yaml(tmp_path, data)
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
    _write_yaml(tmp_path, data)
    adr_dir = _make_adr_dir(tmp_path)  # no 0099 file
    result = lint(tmp_path, adr_dir=adr_dir)
    captured = capsys.readouterr()
    assert result == 0
    assert "ADR-0099" not in captured.out


def test_lint_adr_ref_no_rationale_no_warn(tmp_path, capsys):
    """A spec without a rationale field produces no ADR warning."""
    data = _minimal_spec()
    del data["groups"][0]["specs"][0]["rationale"]
    _write_yaml(tmp_path, data)
    adr_dir = _make_adr_dir(tmp_path)
    result = lint(tmp_path, adr_dir=adr_dir)
    captured = capsys.readouterr()
    assert result == 0
    assert "ADR-" not in captured.out


# ---------------------------------------------------------------------------
# Missing item-level kind is a hard error
# ---------------------------------------------------------------------------


def test_lint_missing_item_kind_is_hard_error(tmp_path, capsys):
    """A spec item missing kind: is a hard error (exit 1)."""
    data = _minimal_spec()
    del data["groups"][0]["specs"][0]["kind"]
    _write_yaml(tmp_path, data)
    result = lint(tmp_path)
    assert result == 1
