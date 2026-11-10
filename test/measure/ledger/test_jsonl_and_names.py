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

"""The tolerant JSONL reader and the shared display-name resolver (CEH-02-001, CEH-02-008)."""

import json

import pytest

from vultron.errors import LedgerReadError
from vultron.measure.ledger import (
    UnusableRow,
    collect_actor_names,
    friendly_actor_name,
    read_ledger_file,
)


@pytest.mark.spec("CEH-02-001")
@pytest.mark.spec("CEH-02-008")
def test_a_malformed_row_degrades_to_one_unusable_row(tmp_path):
    path = tmp_path / "any-name.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps({"logIndex": 0}),
                "{not valid json",
                "",
                "[1, 2]",
                json.dumps({"logIndex": 1}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    ledger = read_ledger_file(path)

    assert [row.data["logIndex"] for row in ledger.rows] == [0, 1]
    assert [row.line for row in ledger.rows] == [1, 5]
    assert [(r.path, r.line) for r in ledger.unusable_rows] == [
        (path, 2),
        (path, 4),
    ]
    assert all("Parse error" in r.reason for r in ledger.unusable_rows)
    assert ledger.entries == [{"logIndex": 0}, {"logIndex": 1}]


def test_an_unreadable_file_raises(tmp_path):
    with pytest.raises(LedgerReadError, match="Cannot read"):
        read_ledger_file(tmp_path / "missing.jsonl")


def test_a_non_utf8_file_raises(tmp_path):
    path = tmp_path / "binary.jsonl"
    path.write_bytes(b"\xff\xfe\x00")
    with pytest.raises(LedgerReadError, match="Cannot read"):
        read_ledger_file(path)


def test_an_unusable_row_describes_itself(tmp_path):
    row = UnusableRow(path=tmp_path / "f.jsonl", line=3, reason="bad")
    assert row.describe() == f"{tmp_path / 'f.jsonl'} line 3: bad"


class TestDisplayNames:
    def test_names_come_from_inline_actor_objects(self):
        replicas = {
            "b": [
                {
                    "payloadSnapshot": {
                        "actor": {
                            "id": "https://x/actors/u1",
                            "type": "Organization",
                            "name": " Vendor ",
                        },
                        "object": [
                            {
                                "id": "https://x/actors/u2",
                                "type": "Person",
                                "name": "Rep",
                            }
                        ],
                    }
                }
            ],
            "a": [
                {
                    "payloadSnapshot": {
                        "actor": {
                            "id": "https://x/actors/u1",
                            "type": "Organization",
                            "name": "First",
                        }
                    }
                }
            ],
        }
        names = collect_actor_names(replicas)
        # Sorted replica order: "a" is scanned first, so its name wins.
        assert names == {
            "https://x/actors/u1": "First",
            "https://x/actors/u2": "Rep",
        }

    def test_a_named_uri_resolves_to_its_name(self):
        uri = "https://x/actors/0a1b2c3d4e"
        assert friendly_actor_name(uri, {uri: "Vendor"}) == "Vendor"

    def test_an_unnamed_uri_falls_back_to_its_last_segment(self):
        assert (
            friendly_actor_name("https://x/actors/case-actor") == "Case Actor"
        )
        assert (
            friendly_actor_name("https://x/actors/case-actor-a1b2c3d4")
            == "Case Actor"
        )

    @pytest.mark.parametrize("uri", [None, ""])
    def test_no_actor_reads_as_an_em_dash(self, uri):
        assert friendly_actor_name(uri) == "—"
