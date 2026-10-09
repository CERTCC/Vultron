"""``scripts/backfill_stories.py`` selects SR-11-003's population through the
linter's shared predicate (MS-02-004), so the script and the linter agree on
which protocol specs need ``lint_suppress: [missing_story_reference]``.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import yaml

from test.metadata.specs.conftest import spec_file_data

_SCRIPT = Path(__file__).parents[3] / "scripts" / "backfill_stories.py"


@pytest.fixture(scope="module")
def backfill_stories():
    spec = importlib.util.spec_from_file_location("backfill_stories", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.spec("SR-11-003")
def test_collects_only_the_specs_sr_11_003_gates(tmp_path, backfill_stories):
    """MUST-only (the recorded MS-02-003 exception): a story-less protocol
    MUST_NOT is not suppressed, because the gate does not fire on it yet."""
    data = spec_file_data(
        [
            ("TST-01-001", "MUST", "protocol", {}),
            ("TST-01-002", "MUST_NOT", "protocol", {}),
            ("TST-01-003", "SHOULD", "protocol", {}),
            (
                "TST-01-004",
                "MUST",
                "protocol",
                {"stories": ["story_2022_001"]},
            ),
            ("TST-01-005", "MUST", "project", {}),
            ("TST-01-006", "MUST", "protocol", {}),
        ]
    )
    path = tmp_path / "tst.yaml"
    path.write_text(yaml.dump(data))
    backfill_map = {"TST-01-006": ["story_2022_002"]}  # about to get stories
    assert backfill_stories._collect_protocol_must_no_stories(
        path, backfill_map
    ) == {"TST-01-001"}
