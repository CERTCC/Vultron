"""Validate the real specs/ directory against the full lint suite (SR-04).

These tests run against the actual ``specs/*.yaml`` files in the repository —
not synthetic fixtures.  They act as the CI equivalent of the pre-commit
``spec-lint`` hook, ensuring that:

- Every spec file loads without schema errors
- All relationship ``spec_id`` targets resolve to a known spec
- No hard lint errors are present

If these tests fail, the spec files contain structural errors that must be
fixed before merging.
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

from vultron.metadata.specs.lint import lint
from vultron.metadata.specs.registry import load_registry
from vultron.metadata.specs.render import main_llm_json

_SPECS_DIR = Path(__file__).parents[3] / "specs"


@pytest.fixture(scope="module")
def real_registry():
    """Load the actual specs/ directory once for all tests in this module."""
    return load_registry(_SPECS_DIR)


def test_real_specs_dir_exists():
    assert _SPECS_DIR.is_dir(), f"specs/ directory not found at {_SPECS_DIR}"


def test_real_specs_load(real_registry):
    """All spec YAML files parse without validation errors."""
    assert real_registry.files, "Registry loaded no spec files"


def test_real_specs_cross_references(real_registry):
    """Every relationship spec_id target exists in the registry."""
    errors = real_registry.validate_cross_references()
    assert (
        errors == []
    ), f"{len(errors)} broken relationship target(s) found:\n" + "\n".join(
        f"  {e}" for e in errors
    )


def test_real_specs_lint_no_hard_errors():
    """Full lint() returns exit code 0 (no hard errors) for specs/."""
    exit_code = lint(_SPECS_DIR)
    assert (
        exit_code == 0
    ), "spec-lint reported hard errors — run 'uv run spec-lint' to see details"


def test_spec_dump_entrypoint_produces_valid_json(monkeypatch):
    """main_llm_json() (the spec-dump CLI entrypoint) produces valid JSON.

    Regression test for the stale-/app/vultron import bug (#1457): if the
    schema module is resolved from a stale installation with missing enum
    values or changed field types, load_registry() will raise a Pydantic
    ValidationError before any JSON is emitted.
    """
    monkeypatch.setattr(sys, "argv", ["spec-dump", str(_SPECS_DIR)])
    buf = io.StringIO()
    monkeypatch.setattr(sys, "stdout", buf)

    main_llm_json()

    output = buf.getvalue()
    data = json.loads(output)
    assert data.get(
        "topics"
    ), "spec-dump output must include at least one topic"
    assert data.get(
        "requirements"
    ), "spec-dump output must include requirements"
