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
"""Standing checks for CSAF documents in reports (ADR-0184).

CSAF-05-004: the suite builds its own CSAF documents and never reads the CSAF
Technical Committee's test documents.
"""

from pathlib import Path

import pytest

from test.architecture import _corpus

_HERE = Path(__file__).resolve()
_TEST_ROOT = _corpus.REPO_ROOT / "test"
#: The CSAF Technical Committee keeps its test documents under this path of
#: its repository (CSAF-05-004).
_TC_TEST_DATA = "csaf_2.1/test/"


def _other_modules_mentioning(fragment: str) -> list[tuple[Path, str]]:
    """Return the test modules other than this one whose source holds ``fragment``."""
    return [
        (path, source)
        for path, source in _corpus.sources_mentioning(
            fragment, under=_TEST_ROOT
        )
        if path.resolve() != _HERE
    ]


@pytest.mark.spec("CSAF-05-004")
def test_the_suite_never_reads_the_tc_test_documents() -> None:
    readers = [
        str(path.relative_to(_TEST_ROOT))
        for path, _ in _other_modules_mentioning(_TC_TEST_DATA)
    ]
    assert readers == [], (
        f"CSAF-05-004: these test modules name the CSAF TC test data: {readers}"
    )
