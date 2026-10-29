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

"""Drift detector for the exported semantic-registry artifact.

``vultron/metadata/demo_scenarios/export_semantics.py`` writes
``ui/src/data/semantic_registry.json``, which the Log Replay demo reads instead
of keeping its own list of ledger semantic types and phrases.  This test fails
when the committed JSON no longer matches a fresh export.

To fix a failure here::

    uv run export-demo-semantics
    git add ui/src/data/semantic_registry.json
"""

import json

from vultron.metadata.demo_scenarios.export_semantics import (
    OUTPUT_PATH,
    REGEN_COMMAND,
    build_payload,
)
from vultron.metadata.generated_files import serialize_json
from vultron.metadata.msm.occasions import format_pattern
from vultron.semantic_registry import SEMANTIC_REGISTRY
from vultron.semantic_registry._entry import DISPATCHER_FALLBACKS

ARTIFACT = "ui/src/data/semantic_registry.json"

REGEN_HINT = (
    f"{ARTIFACT} is stale: SEMANTIC_REGISTRY changed but the exported "
    f"artifact was not regenerated. Run `{REGEN_COMMAND}` and commit "
    f"{ARTIFACT}."
)


def test_artifact_path_is_the_one_the_hint_names() -> None:
    assert OUTPUT_PATH.as_posix().endswith(ARTIFACT)


def test_committed_artifact_matches_a_fresh_export() -> None:
    assert OUTPUT_PATH.exists(), REGEN_HINT
    committed = OUTPUT_PATH.read_text(encoding="utf-8")
    assert committed == serialize_json(build_payload()), REGEN_HINT


def test_drift_hint_names_the_command_and_path() -> None:
    assert "uv run export-demo-semantics" in REGEN_HINT
    assert ARTIFACT in REGEN_HINT


def test_export_lists_every_registry_entry_in_registry_order() -> None:
    rows = build_payload()["entries"]
    assert [row["semanticType"] for row in rows] == [
        entry.semantics.value for entry in SEMANTIC_REGISTRY
    ]


def test_each_row_carries_the_entry_wire_summary_and_phrase() -> None:
    rows = {row["semanticType"]: row for row in build_payload()["entries"]}
    for entry in SEMANTIC_REGISTRY:
        row = rows[entry.semantics.value]
        assert set(row) == {"semanticType", "wire", "phrase"}
        assert row["phrase"] == entry.phrase
        if entry.pattern is None:
            assert entry.semantics in DISPATCHER_FALLBACKS
            assert row["wire"] is None
        else:
            assert row["wire"] == format_pattern(entry.pattern)


def test_export_carries_a_readme_warning_against_hand_edits() -> None:
    readme = build_payload()["_README"]
    assert "Do not edit by hand" in readme
    assert REGEN_COMMAND in readme


def test_committed_artifact_has_the_shape_the_ui_declares() -> None:
    """The committed file parses, and every row carries exactly the fields
    ``ui/src/semanticRegistry.ts`` declares on ``SemanticRegistryEntry``."""
    text = OUTPUT_PATH.read_text(encoding="utf-8")
    assert text.endswith("\n")
    payload = json.loads(text)
    assert set(payload) == {"_README", "entries"}
    for row in payload["entries"]:
        assert set(row) == {"semanticType", "wire", "phrase"}
        assert isinstance(row["semanticType"], str) and row["semanticType"]
        assert isinstance(row["phrase"], str) and row["phrase"]
        assert row["wire"] is None or isinstance(row["wire"], str)
