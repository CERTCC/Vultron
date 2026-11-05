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
"""``set-board-field.sh`` against a stand-in ``gh`` (PAD-02-001, PAD-16-001).

A board automation can add a new issue to Project #24 before the script does;
GitHub then refuses ``addProjectV2ItemById`` with "Content already exists in
this project". These tests pin that the script reads the existing item and sets
the field on it, and that any other add failure still fails the script.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

SHARED = Path(__file__).resolve().parents[2] / ".agents/skills/shared"
FAKE_GH = Path(__file__).with_name("_fake_gh.py")
ISSUE = 4242

pytestmark = [
    pytest.mark.skipif(
        shutil.which("jq") is None, reason="set-board-field.sh needs jq"
    ),
    pytest.mark.spec("PAD-02-001", "PAD-16-001"),
]

_NODE_ID_RULE = {
    "match": [f"issue(number: {ISSUE})", "{ id }"],
    "stdout": json.dumps(
        {"data": {"repository": {"issue": {"id": f"I_{ISSUE}"}}}}
    ),
}
_UPDATE_RULE = {"match": ["updateProjectV2ItemFieldValue"], "stdout": "{}"}
_ALREADY_EXISTS = {
    "match": ["addProjectV2ItemById"],
    "stderr": "gh: Content already exists in this project\n",
    "exit": 1,
}
_EXISTING_ITEM = {
    "match": ["projectItems"],
    "stdout": json.dumps(
        {
            "data": {
                "node": {
                    "projectItems": {
                        "nodes": [
                            {"id": "PVTI_other", "project": {"id": "PVT_x"}},
                            {
                                "id": "PVTI_existing",
                                "project": {"id": "PVT_fake"},
                            },
                        ]
                    }
                }
            }
        }
    ),
}


def _run(tmp_path: Path, rules: list[dict]) -> tuple[int, str, list[str]]:
    shared = tmp_path / "shared"
    shared.mkdir()
    for script in ("set-board-field.sh", "board-id.sh"):
        shutil.copy(SHARED / script, shared)
    (shared / "board-ids.json").write_text(
        json.dumps(
            {
                "fetched_at_epoch": int(time.time()),
                "project": "PVT_fake",
                "schedule-field": "F_schedule",
                "schedule": {"Someday": "S_someday"},
            }
        )
    )
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(f'#!/bin/sh\nexec python3 "{FAKE_GH}" "$@"\n')
    gh.chmod(0o755)
    rules_file = tmp_path / "rules.json"
    rules_file.write_text(json.dumps(rules))
    log = tmp_path / "gh.log"
    result = subprocess.run(
        [
            "bash",
            str(shared / "set-board-field.sh"),
            str(ISSUE),
            "schedule",
            "Someday",
        ],
        env={
            **os.environ,
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            "FAKE_GH_LOG": str(log),
            "FAKE_GH_RULES": str(rules_file),
        },
        capture_output=True,
        text=True,
        check=False,
    )
    calls = (
        [" ".join(json.loads(line)) for line in log.read_text().splitlines()]
        if log.exists()
        else []
    )
    return result.returncode, result.stderr, calls


def _updated_item(calls: list[str]) -> str | None:
    for call in calls:
        if "updateProjectV2ItemFieldValue" in call:
            return call.split('itemId: "', 1)[1].split('"', 1)[0]
    return None


def test_a_new_item_gets_the_field(tmp_path: Path) -> None:
    added = {
        "match": ["addProjectV2ItemById"],
        "stdout": json.dumps(
            {"data": {"addProjectV2ItemById": {"item": {"id": "PVTI_new"}}}}
        ),
    }
    code, stderr, calls = _run(tmp_path, [_NODE_ID_RULE, added, _UPDATE_RULE])
    assert code == 0, stderr
    assert _updated_item(calls) == "PVTI_new"
    assert not any("projectItems" in c for c in calls)


def test_an_item_the_automation_added_first_is_reused(tmp_path: Path) -> None:
    code, stderr, calls = _run(
        tmp_path,
        [_NODE_ID_RULE, _ALREADY_EXISTS, _EXISTING_ITEM, _UPDATE_RULE],
    )
    assert code == 0, stderr
    assert _updated_item(calls) == "PVTI_existing"


def test_any_other_add_failure_fails_without_a_lookup(tmp_path: Path) -> None:
    refused = {
        "match": ["addProjectV2ItemById"],
        "stderr": "gh: Resource not accessible by integration\n",
        "exit": 1,
    }
    code, stderr, calls = _run(
        tmp_path, [_NODE_ID_RULE, refused, _UPDATE_RULE]
    )
    assert code == 1
    assert "Resource not accessible" in stderr
    assert not any("projectItems" in c for c in calls)
    assert _updated_item(calls) is None
