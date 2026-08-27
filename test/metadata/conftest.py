"""Session-scoped fixtures shared across test/metadata/ sub-packages."""

from __future__ import annotations

from pathlib import Path

import pytest

from vultron.metadata.specs.registry import load_registry

_SPECS_DIR = Path(__file__).parents[2] / "specs"


@pytest.fixture(scope="session")
def real_registry():
    """Load the actual specs/ directory once for the entire test session."""
    return load_registry(_SPECS_DIR)
