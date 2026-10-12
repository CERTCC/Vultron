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

"""Every routed received use case reaches a ledger commit (CLP-09-003).

A use case is exempt only on a ground CLP-02-013 lists, or by naming the open
issue that tracks its missing commit.  ``received_commit_semantics`` derives the
committing set from code (``_ledger_commit_inventory``), so a handler that
"changes nothing" and commits nothing fails here instead of being found one
case at a time.
"""

from enum import StrEnum

import pytest

from test.architecture._ledger_commit_inventory import (
    received_commit_semantics,
)
from vultron.semantic_registry import use_case_map


class NotACaseEvent(StrEnum):
    """The closed CLP-02-013 grounds for routing an activity with no entry."""

    PRE_CASE = "processed before a case exists"
    REPLICA_APPLY = "a replica applying an entry, not asserting one"
    LEDGER_MECHANICS = "an activity about the ledger itself"
    UNMATCHED = "no pattern matches or the object is unresolvable"


#: MessageSemantics value -> CLP-02-013 ground, or the open issue ("#NNNN")
#: tracking the missing commit.  Nothing else may appear here.
EXEMPT: dict[str, NotACaseEvent | str] = {
    "announce_case_ledger_entry": NotACaseEvent.REPLICA_APPLY,
    "reject_case_ledger_entry": NotACaseEvent.LEDGER_MECHANICS,
    "unknown": NotACaseEvent.UNMATCHED,
    "unknown_unresolvable_object": NotACaseEvent.UNMATCHED,
}


@pytest.mark.spec("CLP-09-003")
@pytest.mark.spec("CLP-02-013")
@pytest.mark.xfail(
    strict=True,
    reason="CLP-09-003: routed use cases reach no commit and are not yet classified. #3748.",
)
def test_every_routed_use_case_reaches_a_commit_or_is_exempt():
    committed = received_commit_semantics()
    missing = sorted(
        semantic.value
        for semantic in use_case_map()
        if semantic.value not in committed and semantic.value not in EXEMPT
    )
    assert missing == []


@pytest.mark.spec("CLP-02-013")
def test_exemptions_name_a_ground_or_an_issue():
    for semantic, ground in EXEMPT.items():
        assert isinstance(ground, NotACaseEvent) or (
            ground.startswith("#") and ground[1:].isdigit()
        ), semantic
