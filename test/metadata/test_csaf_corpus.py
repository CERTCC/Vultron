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
"""The optional corpus script over a clone's test documents (CSAF-05-004).

These tests build a stand-in clone from hand-written documents; the suite never
reads the CSAF Technical Committee's own test documents.
"""

import json
from pathlib import Path

import pytest

from test.wire.csaf._documents import minimal_csaf_document, section
from vultron.metadata.csaf.corpus import (
    TEST_DATA_DIR,
    TESTCASES_FILE,
    GroupCounts,
    format_report,
    main,
    run_corpus,
)
from vultron.metadata.file_loading import MetadataLoadError


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


@pytest.fixture
def clone(tmp_path: Path) -> Path:
    """A stand-in clone: one mandatory and one informative test."""
    data = tmp_path / TEST_DATA_DIR
    valid = minimal_csaf_document()
    invalid = minimal_csaf_document()
    del section(invalid, "document")["title"]
    _write(data / "mandatory/valid.json", valid)
    _write(data / "mandatory/schema-invalid.json", invalid)
    _write(data / "mandatory/schema-valid-but-failing.json", valid)
    _write(data / "informative/valid.json", valid)
    _write(data / "informative/listed-valid-but-schema-invalid.json", invalid)
    _write(
        tmp_path / TESTCASES_FILE,
        {
            "tests": [
                {
                    "id": "6.1.1",
                    "group": "mandatory",
                    "failures": [
                        {"name": "mandatory/schema-invalid.json"},
                        {"name": "mandatory/schema-valid-but-failing.json"},
                    ],
                    "valid": [{"name": "mandatory/valid.json"}],
                },
                {
                    "id": "6.3.1",
                    "group": "informative",
                    "failures": [{"name": "informative/absent.json"}],
                    "valid": [
                        {"name": "informative/valid.json"},
                        {
                            "name": (
                                "informative/listed-valid-but-schema-invalid.json"
                            )
                        },
                    ],
                },
            ]
        },
    )
    return tmp_path


@pytest.mark.spec("CSAF-05-004")
def test_counts_each_groups_verdicts(clone: Path) -> None:
    assert run_corpus(clone) == {
        "informative": GroupCounts(
            valid_accepted=1, valid_rejected=1, missing=1
        ),
        "mandatory": GroupCounts(
            valid_accepted=1, failing_accepted=1, failing_rejected=1
        ),
    }


def test_the_report_has_a_line_per_group_and_a_total(clone: Path) -> None:
    assert format_report(run_corpus(clone)).splitlines() == [
        "informative: valid 1/2 accepted, failing 0/0 rejected, 1 missing",
        "mandatory: valid 1/1 accepted, failing 1/2 rejected",
        "total: valid 2/3 accepted, failing 1/2 rejected, 1 missing",
    ]


def test_main_prints_the_report(
    clone: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--clone", str(clone)]) == 0
    assert capsys.readouterr().out.startswith("informative:")


def test_main_refuses_a_directory_without_the_index(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--clone", str(tmp_path)]) == 2
    assert "testcases.json" in capsys.readouterr().err


def test_a_tab_indented_index_is_read_as_json(clone: Path) -> None:
    index = clone / TESTCASES_FILE
    expected = run_corpus(clone)
    index.write_text(
        json.dumps(json.loads(index.read_bytes()), indent="\t"), "utf-8"
    )

    assert run_corpus(clone) == expected


def test_an_index_that_is_not_json_names_its_file(clone: Path) -> None:
    (clone / TESTCASES_FILE).write_text('{"tests": [', "utf-8")

    with pytest.raises(MetadataLoadError, match=r"testcases\.json:1:"):
        run_corpus(clone)


def test_a_malformed_index_names_its_file(clone: Path) -> None:
    (clone / TESTCASES_FILE).write_text('{"tests": [{"id": 1}]}', "utf-8")

    with pytest.raises(MetadataLoadError, match=r"testcases\.json"):
        run_corpus(clone)
