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

Only the receive-side commit counts: CLP-09-003 asks for a commit *for the
act*, and an explicit ``semantic_type=`` commit inside a received tree records a
consequence (``CommitNativeLedgerEntriesNode``'s genesis entries) or an
activity the actor emits, not the act received.  Crediting those would let a
handler whose act goes unledgered pass on a side entry.
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
    OUTSIDE_THE_CASE = "RK, a reply to the reporter outside the case"
    REPLICA_APPLY = "a replica applying an entry, not asserting one"
    LEDGER_MECHANICS = "an activity about the ledger itself"
    NOT_LEDGERED_BY_CLP_10_013 = "left unledgered by CLP-10-013 (ADR-0111)"
    SENT_BY_CASE_MANAGER = "CASE_MANAGER-sent; ledgered, if at all, at sending"
    PROCESSING_FAULT = "a NACK about message handling (ADR-0080)"
    UNMATCHED = "no pattern matches or the object is unresolvable"


#: MessageSemantics value -> CLP-02-013 ground, or the open issue ("#NNNN")
#: tracking the missing commit.  Nothing else may appear here.
EXEMPT: dict[str, NotACaseEvent | str] = {
    "create_report": NotACaseEvent.PRE_CASE,
    "submit_report": NotACaseEvent.PRE_CASE,
    # RK answers the reporter's Offer outside the case and never reaches the
    # CASE_MANAGER (RMB-08-003).
    "ack_report": NotACaseEvent.OUTSIDE_THE_CASE,
    "create_case_proposal": NotACaseEvent.PRE_CASE,
    # The proposer's receipt of the answer to its proposal: case proposal
    # intake, before the proposer holds any case (CP-06-001, CP-06-002).
    "accept_case_proposal": NotACaseEvent.PRE_CASE,
    "reject_case_proposal": NotACaseEvent.PRE_CASE,
    "announce_case_ledger_entry": NotACaseEvent.REPLICA_APPLY,
    "reject_case_ledger_entry": NotACaseEvent.LEDGER_MECHANICS,
    "announce_vulnerability_case": NotACaseEvent.NOT_LEDGERED_BY_CLP_10_013,
    "unknown": NotACaseEvent.UNMATCHED,
    "unknown_unresolvable_object": NotACaseEvent.UNMATCHED,
    # Received only by a participant, which never commits (CLP-09-001).
    "create_case": NotACaseEvent.SENT_BY_CASE_MANAGER,
    "announce_embargo_event_to_case": NotACaseEvent.SENT_BY_CASE_MANAGER,
    # The recommender's receipt of the CASE_MANAGER's answer, which the
    # CASE_MANAGER ledgered when it sent it (CM-16-006, CM-16-007, CM-16-010).
    "accept_actor_recommendation": NotACaseEvent.SENT_BY_CASE_MANAGER,
    "reject_actor_recommendation": NotACaseEvent.SENT_BY_CASE_MANAGER,
    "create_processing_fault": NotACaseEvent.PROCESSING_FAULT,
    "refusal_notice": NotACaseEvent.LEDGER_MECHANICS,
}


def _rows(*, tracked: bool) -> list[str]:
    """The ``EXEMPT`` rows naming an issue (*tracked*) or a ground."""
    return sorted(
        semantic
        for semantic, ground in EXEMPT.items()
        if isinstance(ground, NotACaseEvent) is not tracked
    )


@pytest.fixture(scope="module")
def committed() -> set[str]:
    return received_commit_semantics()


@pytest.mark.spec("CLP-09-003")
@pytest.mark.spec("CLP-02-013")
def test_every_routed_use_case_reaches_a_commit_or_is_exempt(
    committed: set[str],
):
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


@pytest.mark.spec("CLP-02-013")
@pytest.mark.spec("CLP-10-004")
def test_exemptions_name_routed_use_cases_that_do_not_commit(
    committed: set[str],
):
    """Ground rows are checked here; issue rows each in their own test."""
    routed = {semantic.value for semantic in use_case_map()}
    grounds = set(_rows(tracked=False))
    assert set(EXEMPT) <= routed, sorted(set(EXEMPT) - routed)
    assert grounds.isdisjoint(committed), sorted(grounds & committed)


@pytest.mark.spec("CLP-09-003")
@pytest.mark.parametrize("semantic", _rows(tracked=True))
def test_issue_row_still_reaches_no_commit(semantic: str, committed: set[str]):
    """Each issue-numbered row is checked on its own, never as a count.

    A PR that lands a tracked commit fails only its own row, and two PRs
    closing different gaps merge cleanly (#3984).
    """
    assert semantic not in committed, (
        f"{semantic} now commits: delete its EXEMPT row ({EXEMPT[semantic]})"
    )
