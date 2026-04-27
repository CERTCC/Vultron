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

from pathlib import Path

import pytest

from vultron.metadata.specs.lint import lint
from vultron.metadata.specs.registry import load_registry

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
