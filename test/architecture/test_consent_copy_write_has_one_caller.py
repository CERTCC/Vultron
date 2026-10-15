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
"""The consent copy write has one caller: the one apply function (CM-18-005).

``CaseParticipant.copy_consent_row()`` stores a row exactly as a ledger entry
carries it, with no transition check of its own.  It is safe only because
``apply_embargo_change()`` checks the row's starting state first, so no other
production code may call it (ADR-0124, CM-23-016).
"""

import ast

import pytest

from test.architecture import _corpus

_PACKAGE = _corpus.REPO_ROOT / "vultron"
_ALLOWED = {
    # The one apply function (ADR-0124).
    "vultron/core/models/embargo_apply.py",
    # The definition itself.
    "vultron/core/models/case_participant.py",
}


def _callers() -> set[str]:
    found: set[str] = set()
    for path, tree in _corpus.files_mentioning(
        "copy_consent_row", under=_PACKAGE
    ):
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and node.attr == "copy_consent_row"
            ):
                found.add(path.relative_to(_corpus.REPO_ROOT).as_posix())
    return found


@pytest.mark.spec("CM-18-005")
def test_only_the_apply_function_calls_the_copy_write() -> None:
    assert _callers() - _ALLOWED == set(), (
        "copy_consent_row() writes a row with no transition check; only"
        " apply_embargo_change() may call it, after it checks the row's"
        " starting state (CM-18-005, ADR-0124)"
    )


def test_the_scan_finds_the_apply_function() -> None:
    """Guards against a vacuous pass if the call moves or is renamed."""
    assert "vultron/core/models/embargo_apply.py" in _callers()
