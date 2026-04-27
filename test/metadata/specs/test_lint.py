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
        "kind": "general",
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
        "kind": "general",
        "scope": ["production"],
        "groups": [
            {
                "id": "OTHER-01",  # prefix "OTHER" != file id "TST"
                "title": "Wrong Group",
                "specs": [
                    {
                        "id": "OTHER-01-001",
                        "priority": "MUST",
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
