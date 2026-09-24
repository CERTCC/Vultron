"""The spec registry reports load failures attributed to their file.

Requirements: SR-03-008, SR-03-009, SR-04-002, MS-17-002.

Lives under ``test/metadata/specs/`` because its fixture cites a synthetic
spec ID, which ``spec-lint`` rejects anywhere else (SR-04-008).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from vultron.metadata.file_loading import MetadataLoadErrors
from vultron.metadata.specs.registry import load_registry

_UNQUOTED_COLON = "statement: the actor: sends it\n"


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


_SPEC_FILE = """\
id: TS
title: Test
description: A test spec file.
version: "1.0.0"
scope: [prototype]
groups:
- id: TS-01
  title: Group
  specs:
  - id: TS-01-001
    priority: MUST
    kind: project
    statement: Something MUST happen.
"""


@pytest.mark.spec("SR-03-008")
class TestLoadRegistry:
    def test_valid_corpus_loads(self, tmp_path):
        _write(tmp_path / "specs" / "ts.yaml", _SPEC_FILE)

        assert load_registry(tmp_path / "specs").get("TS-01-001")

    def test_yaml_fault_names_the_file(self, tmp_path):
        _write(
            tmp_path / "specs" / "ts.yaml",
            _SPEC_FILE.replace(
                "statement: Something MUST happen.",
                "statement: the actor: MUST send it",
            ),
        )

        with pytest.raises(ValueError) as info:
            load_registry(tmp_path / "specs")

        assert "specs/ts.yaml:13:" in str(info.value)
        assert "<unicode string>" not in str(info.value)

    def test_invalid_enum_names_the_file(self, tmp_path):
        _write(
            tmp_path / "specs" / "ts.yaml",
            _SPEC_FILE.replace("priority: MUST", "priority: OUGHT"),
        )

        with pytest.raises(ValueError) as info:
            load_registry(tmp_path / "specs")

        assert "specs/ts.yaml — " in str(info.value)
        assert "priority" in str(info.value)

    @pytest.mark.spec("SR-03-009")
    def test_every_failing_file_is_reported_structurally(self, tmp_path):
        _write(tmp_path / "specs" / "a.yaml", "a: 1\n" + _UNQUOTED_COLON)
        _write(
            tmp_path / "specs" / "b.yaml",
            _SPEC_FILE.replace("priority: MUST", "priority: OUGHT"),
        )

        with pytest.raises(MetadataLoadErrors) as info:
            load_registry(tmp_path / "specs")

        assert [f.path for f in info.value.failures] == [
            "specs/a.yaml",
            "specs/b.yaml",
        ]
        assert "specs/a.yaml" in str(info.value)
        assert "specs/b.yaml" in str(info.value)


@pytest.mark.spec("SR-04-002")
@pytest.mark.spec("MS-17-002")
def test_spec_lint_reports_a_syntax_fault_without_a_traceback(tmp_path):
    spec_dir = tmp_path / "specs"
    _write(spec_dir / "a.yaml", "a: 1\n" + _UNQUOTED_COLON)

    result = subprocess.run(
        [sys.executable, "-m", "vultron.metadata.specs.lint", str(spec_dir)],
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 1
    assert "[FATAL] Registry load failed" in result.stderr
    assert "specs/a.yaml:2:21" in result.stderr
    assert "Traceback" not in result.stderr
