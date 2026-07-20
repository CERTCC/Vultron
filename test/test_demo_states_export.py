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

"""Drift detector for the exported protocol-state artifact.

``vultron/scripts/export_states.py`` writes ``data/json/protocol_states.json``,
which the ``ui/`` demos consume instead of hardcoding the protocol's states and
transitions. This test fails when the committed JSON no longer matches a fresh
export — i.e. the protocol state machines changed but the artifact was not
regenerated.

To fix a failure here::

    uv run export-demo-states
    git add data/json/protocol_states.json
"""

import json

import pytest

from vultron.scripts.export_states import (
    OUTPUT_PATH,
    _serialize,
    build_payload,
)

REGEN_HINT = (
    "data/json/protocol_states.json is stale. The protocol state machines "
    "changed but the exported artifact was not regenerated. Run "
    "`uv run export-demo-states` and commit the result."
)


def test_exported_states_file_exists() -> None:
    assert OUTPUT_PATH.exists(), (
        f"{OUTPUT_PATH} does not exist. Run `uv run export-demo-states` "
        "and commit the result."
    )


def test_exported_states_match_committed_file() -> None:
    """The committed JSON must be byte-identical to a fresh export."""
    if not OUTPUT_PATH.exists():
        pytest.skip("artifact missing; see test_exported_states_file_exists")

    fresh = _serialize(build_payload())
    committed = OUTPUT_PATH.read_text(encoding="utf-8")
    assert committed == fresh, REGEN_HINT


def test_exported_payload_shape() -> None:
    """Guard the contract the UI relies on: four machines, each well-formed."""
    payload = build_payload()

    for key in ("rm", "em", "vfd", "pxa"):
        assert key in payload, f"missing machine '{key}' in export"
        machine = payload[key]
        assert set(machine) >= {"initial", "states", "transitions"}
        assert machine["states"], f"'{key}' has no states"
        assert machine["initial"] in machine["states"]
        for t in machine["transitions"]:
            assert set(t) == {"trigger", "source", "dest"}
            assert t["source"] in machine["states"]
            assert t["dest"] in machine["states"]


def test_exported_embargo_viability_shape() -> None:
    """Guard the cross-machine embargo-viability section the UI relies on."""
    payload = build_payload()

    assert "embargo_viability" in payload, "missing 'embargo_viability' section"
    section = payload["embargo_viability"]
    assert set(section) >= {"patterns"}
    assert section["patterns"], "embargo_viability has no patterns"

    known_flags = {"START_OK", "NO_START", "VIABLE", "NOT_VIABLE", "CAUTION"}
    # A CS-state pattern is exactly 6 chars over the vVfFdDpPxXaA (+ wildcard) alphabet.
    cs_char = set("vVfFdDpPxXaA.")
    for entry in section["patterns"]:
        assert set(entry) == {"pattern", "flags"}
        pattern = entry["pattern"]
        assert len(pattern) == 6, f"CS pattern must be 6 chars: {pattern!r}"
        assert set(pattern) <= cs_char, f"bad char in CS pattern: {pattern!r}"
        assert entry["flags"], f"pattern {pattern!r} has no flags"
        assert set(entry["flags"]) <= known_flags, (
            f"unknown viability flag(s) in {pattern!r}: {entry['flags']}"
        )


def test_committed_file_is_valid_json() -> None:
    if not OUTPUT_PATH.exists():
        pytest.skip("artifact missing; see test_exported_states_file_exists")
    # Raises if the committed file is not parseable JSON.
    json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
