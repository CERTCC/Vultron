#!/usr/bin/env python

#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University
"""The Demo Integration pre-run sentinel matches the dump-manifest schema.

The demo job writes a ``dump-manifest.json`` sentinel before the demo-runner
starts (DEMOCI-10-006), so a pre-harness failure still leaves an artifact the
invariant harness can read. DEMOCI-10-012 requires that sentinel to conform to
the manifest schema of DEMOCI-10-015 and DEMOCI-10-016, which
``LedgerDumpReport.as_manifest`` writes for a real run. The sentinel lacked
``unreplicatedActors`` (#5665); these tests run the workflow's own command and
compare its output with the real manifest's keys and with the sentinel that
``write_prerun_sentinel`` writes, which the step replicates without importing
``vultron``.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest

from test.ci._workflows import REPO_ROOT, load_workflow
from vultron.demo.helpers.ledger_dump import (
    LedgerDumpReport,
    write_prerun_sentinel,
)

WORKFLOW = REPO_ROOT / ".github" / "workflows" / "demo-integration.yml"
SENTINEL_STEP = "Write pre-run sentinel manifest"
DEMO = "rv"


def _sentinel_step() -> dict[str, Any]:
    steps = load_workflow(WORKFLOW)["jobs"]["demo"]["steps"]
    matches = [s for s in steps if s.get("name") == SENTINEL_STEP]
    assert len(matches) == 1, (
        f"Expected one demo step named {SENTINEL_STEP!r}, found "
        f"{len(matches)}; update this test if the step was renamed."
    )
    step = matches[0]
    assert isinstance(step, dict)
    return step


@pytest.fixture
def sentinel(tmp_path: Path) -> dict[str, Any]:
    """Run the sentinel step's command and return the manifest it writes."""
    result = subprocess.run(
        ["bash", "-e", "-c", str(_sentinel_step()["run"])],
        check=False,
        cwd=tmp_path,
        env={"PATH": os.environ["PATH"], "DEMO": DEMO},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    manifest = tmp_path / "devlogs" / DEMO / "dump-manifest.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


@pytest.mark.spec("DEMOCI-10-012", "DEMOCI-10-015", "DEMOCI-10-016")
def test_sentinel_keys_match_the_dump_manifest_schema(
    sentinel: dict[str, Any],
) -> None:
    schema_keys = set(LedgerDumpReport(demo_name=DEMO).as_manifest())
    assert set(sentinel) == schema_keys, (
        f"Sentinel keys differ from the dump manifest's: missing "
        f"{sorted(schema_keys - set(sentinel))}, extra "
        f"{sorted(set(sentinel) - schema_keys)}."
    )


@pytest.mark.spec("DEMOCI-10-012", "DEMOCI-10-015", "DEMOCI-10-016")
def test_sentinel_records_a_runner_that_never_started(
    sentinel: dict[str, Any],
) -> None:
    assert sentinel["demoName"] == DEMO
    assert sentinel["caseId"] is None
    assert sentinel["ledgerFileCount"] == 0
    assert sentinel["targetCount"] == 0
    assert isinstance(sentinel["reason"], str) and sentinel["reason"]
    assert sentinel["actors"] == []
    assert sentinel["unreplicatedActors"] == []


@pytest.mark.spec("DEMOCI-10-012")
def test_sentinel_matches_the_python_sentinel_writer(
    sentinel: dict[str, Any], tmp_path: Path
) -> None:
    """The step replicates ``write_prerun_sentinel`` exactly, reason included."""
    written = write_prerun_sentinel(DEMO, output_root=tmp_path / "python")
    assert sentinel == json.loads(written.read_text(encoding="utf-8"))
