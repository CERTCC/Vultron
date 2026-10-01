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

"""``VulnerabilityCase.discard_proposed_embargo`` — one pruner for both records.

``proposed_embargoes`` and ``pending_embargo_proposal_index`` both record open
proposals; EP-08-003 requires a decided proposal to leave every such record,
and pruning them from one place is what keeps them from drifting (#3470).
"""

import pytest

from vultron.core.models.case import VulnerabilityCase

_OWNER = "https://example.org/actors/owner"
_E1 = "https://example.org/cases/1/embargo_events/1"
_E2 = "https://example.org/cases/1/embargo_events/2"
_P1 = "https://example.org/cases/1/embargo_proposals/1"
_P2 = "https://example.org/cases/1/embargo_proposals/2"


def _case_with_two_open_proposals() -> VulnerabilityCase:
    case = VulnerabilityCase(name="c", attributed_to=_OWNER)
    case.proposed_embargoes.extend([_E1, _E2])
    case.pending_embargo_proposal_index.update({_E1: _P1, _E2: _P2})
    return case


@pytest.mark.spec("EP-08-003")
def test_discard_removes_the_proposal_from_both_records_and_only_that_one():
    case = _case_with_two_open_proposals()

    assert case.discard_proposed_embargo(_E1) is True

    assert case.proposed_embargoes == [_E2]
    assert case.pending_embargo_proposal_index == {_E2: _P2}


@pytest.mark.spec("EP-08-003")
def test_discard_is_idempotent_and_reports_no_change_the_second_time():
    case = _case_with_two_open_proposals()
    case.discard_proposed_embargo(_E1)

    assert case.discard_proposed_embargo(_E1) is False
    assert case.proposed_embargoes == [_E2]
    assert case.pending_embargo_proposal_index == {_E2: _P2}


@pytest.mark.spec("EP-08-003")
def test_discard_prunes_a_record_the_other_does_not_hold():
    """The two records can disagree (they were pruned on different paths);
    each is pruned on its own evidence."""
    case = VulnerabilityCase(name="c", attributed_to=_OWNER)
    case.pending_embargo_proposal_index[_E1] = _P1  # index only

    assert case.discard_proposed_embargo(_E1) is True
    assert case.pending_embargo_proposal_index == {}

    case.proposed_embargoes.append(_E2)  # list only
    assert case.discard_proposed_embargo(_E2) is True
    assert case.proposed_embargoes == []


def test_discard_of_an_unknown_embargo_changes_nothing():
    case = _case_with_two_open_proposals()

    assert case.discard_proposed_embargo("urn:uuid:nobody") is False
    assert case.proposed_embargoes == [_E1, _E2]
    assert case.pending_embargo_proposal_index == {_E1: _P1, _E2: _P2}


@pytest.mark.spec("EP-08-004")
def test_discard_all_clears_both_records_together_and_reports_change():
    """Termination's whole-record pruner: both records leave in one call."""
    case = VulnerabilityCase(name="Open proposals", attributed_to="urn:o")
    case.proposed_embargoes = ["urn:e1", "urn:e2"]
    case.pending_embargo_proposal_index = {
        "urn:e1": "urn:p1",
        "urn:e2": "urn:p2",
    }

    assert case.discard_all_proposed_embargoes() is True
    assert case.proposed_embargoes == []
    assert case.pending_embargo_proposal_index == {}


@pytest.mark.spec("EP-08-004")
def test_discard_all_is_idempotent_and_clears_a_record_the_other_lacks():
    """A second call reports no change; a lopsided pair is still cleared."""
    case = VulnerabilityCase(name="Open proposals", attributed_to="urn:o")
    assert case.discard_all_proposed_embargoes() is False

    case.pending_embargo_proposal_index = {"urn:e1": "urn:p1"}
    assert case.discard_all_proposed_embargoes() is True
    assert case.pending_embargo_proposal_index == {}
    assert case.discard_all_proposed_embargoes() is False
