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

"""``spec-dump --adr``: requirements selected by the record they cite.

The selector reads each requirement's ``adr:`` edge in the record-to-
requirements direction, which is the hint source ``deepen-context`` uses in
place of reading a decision-record body (SR-07-017, MS-11-008).
"""

import json
import sys

import pytest
import yaml

from vultron.metadata.specs.llm_export import select_spec_ids, uncited_adrs
from vultron.metadata.specs.registry import load_registry
from vultron.metadata.specs.render import main_llm_json

FIXTURE_YAML = {
    "id": "MS",
    "title": "Meta",
    "description": "adr-selector fixture",
    "scope": ["prototype"],
    "groups": [
        {
            "id": "MS-01",
            "title": "Edges",
            "specs": [
                {
                    "id": "MS-01-001",
                    "priority": "MUST",
                    "kind": "process",
                    "statement": "MS-01-001 MUST cite one record",
                    "adr": ["ADR-0001"],
                },
                {
                    "id": "MS-01-002",
                    "priority": "SHOULD",
                    "kind": "process",
                    "statement": "MS-01-002 SHOULD cite two records",
                    "adr": ["ADR-0001", "ADR-0002"],
                    "relationships": [
                        {"rel_type": "depends_on", "spec_id": "MS-01-003"}
                    ],
                },
                {
                    "id": "MS-01-003",
                    "priority": "MAY",
                    "kind": "process",
                    "statement": "MS-01-003 MAY cite no record",
                },
            ],
        }
    ],
}


@pytest.fixture
def dump_dir(tmp_path):
    (tmp_path / "ms.yaml").write_text(yaml.dump(FIXTURE_YAML))
    return tmp_path


def _run(monkeypatch, capsys, *argv):
    monkeypatch.setattr(sys, "argv", ["spec-dump", *argv])
    main_llm_json()
    return capsys.readouterr()


def _exit(monkeypatch, capsys, *argv):
    monkeypatch.setattr(sys, "argv", ["spec-dump", *argv])
    with pytest.raises(SystemExit) as exc_info:
        main_llm_json()
    return exc_info.value.code, capsys.readouterr().err


def _ids(out: str) -> set[str]:
    return {r["id"] for r in json.loads(out)["requirements"]}


@pytest.mark.spec("SR-07-017")
def test_adr_selects_every_requirement_citing_the_record(dump_dir):
    registry = load_registry(dump_dir)
    assert select_spec_ids(registry, adrs=["ADR-0001"]) == {
        "MS-01-001",
        "MS-01-002",
    }
    assert select_spec_ids(registry, adrs=["ADR-0002"]) == {"MS-01-002"}


@pytest.mark.spec("SR-07-017")
def test_adr_unions_with_the_other_selectors_and_deps(dump_dir):
    registry = load_registry(dump_dir)
    assert select_spec_ids(
        registry, adrs=["ADR-0002"], spec_ids=["MS-01-001"]
    ) == {"MS-01-001", "MS-01-002"}
    assert select_spec_ids(registry, adrs=["ADR-0002"], include_deps=True) == {
        "MS-01-002",
        "MS-01-003",
    }


@pytest.mark.spec("SR-07-017")
def test_cli_adr_flag_in_json_and_text(dump_dir, monkeypatch, capsys):
    out = _run(monkeypatch, capsys, "--adr", "ADR-0002", str(dump_dir)).out
    assert _ids(out) == {"MS-01-002"}
    text = _run(
        monkeypatch, capsys, "--adr", "ADR-0001", "--text", str(dump_dir)
    )
    assert "MS-01-001 MUST" in text.out
    assert "MS-01-002 SHOULD" in text.out
    assert "MS-01-003" not in text.out
    assert text.err == ""


@pytest.mark.spec("SR-07-017")
def test_adr_counts_as_a_set_selector_for_text(dump_dir, monkeypatch, capsys):
    """``--text`` accepts ``--adr`` alone; it needs no other selector."""
    result = _run(
        monkeypatch, capsys, "--adr", "ADR-0002", "--text", str(dump_dir)
    )
    assert "MS-01-002 SHOULD" in result.out


@pytest.mark.spec("SR-07-017")
def test_record_no_requirement_cites_is_noted_not_silent(
    dump_dir, monkeypatch, capsys
):
    """A record reached only by prose selects nothing, and stderr says why."""
    result = _run(
        monkeypatch, capsys, "--adr", "ADR-0003", "--text", str(dump_dir)
    )
    assert "# 0 requirements" in result.out
    assert "no requirement names ADR-0003 in adr:" in result.err
    assert "grep -rn ADR-0003 specs/ notes/" in result.err
    assert uncited_adrs(load_registry(dump_dir), ["ADR-0001", "ADR-0003"]) == [
        "ADR-0003"
    ]


@pytest.mark.spec("SR-07-017")
@pytest.mark.parametrize("value", ["adr-0001", "ADR-1", "0127", "ADR-00012"])
def test_malformed_adr_value_exits_2(dump_dir, monkeypatch, capsys, value):
    code, err = _exit(
        monkeypatch, capsys, "--adr", value, "--text", str(dump_dir)
    )
    assert code == 2
    assert value in err
    assert "Expected ADR-NNNN" in err


@pytest.mark.spec("SR-07-015")
def test_empty_adr_selector_exits_2(dump_dir, monkeypatch, capsys):
    code, err = _exit(monkeypatch, capsys, "--adr", "", str(dump_dir))
    assert code == 2
    assert "--adr was given but names no values" in err
