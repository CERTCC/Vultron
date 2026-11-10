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

"""The report tool reads through the shared reader, strictly (DRPT-01-004, CEH-02-008).

The shared reader degrades a bad row; the report tool wraps it and refuses the
file instead, so ``vultron-demo-report`` still exits non-zero on a file it
cannot parse.
"""

import json

import pytest

from vultron.demo.report import ReportError, discover_replicas, timeline


def _vendor_ledger(tmp_path, *lines: str):
    actor_dir = tmp_path / "demo" / "vendor"
    actor_dir.mkdir(parents=True)
    path = actor_dir / "x-case-ledger.jsonl"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


@pytest.mark.spec("DRPT-01-004")
@pytest.mark.parametrize("bad_row", ["{not valid json", "[1, 2]", '"text"'])
def test_any_unusable_row_refuses_the_file(tmp_path, bad_row):
    path = _vendor_ledger(tmp_path, json.dumps({"logIndex": 0}), bad_row)

    with pytest.raises(ReportError, match=rf"{path.name} line 2: Parse error"):
        discover_replicas(tmp_path)


def test_an_unreadable_file_is_a_report_error(tmp_path):
    with pytest.raises(ReportError, match="Cannot read"):
        timeline._load_jsonl(tmp_path / "missing-case-ledger.jsonl")


def test_the_report_defines_no_walker_of_its_own():
    """The JSONL walker lives in ``vultron.measure.ledger`` only (CEH-02-002)."""
    from vultron.demo.report import naming

    for module in (naming, timeline):
        for name in (
            "_first",
            "_coerce_int",
            "_actor_uri",
            "_candidate_dicts",
            "_dimension_state",
            "_collect_actor_names_from_obj",
        ):
            assert not hasattr(module, name), f"{module.__name__}.{name}"
