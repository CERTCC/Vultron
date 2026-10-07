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

"""A register step keeps ``pending_embargo_proposal_index`` with the register.

The embargo register is the one record of a case's open proposals (its
``PROPOSED`` entries, ADR-0122); ``pending_embargo_proposal_index`` maps each
to the Invite that relayed it.  EP-08-003 requires a decided proposal to leave
every such record, so every register step prunes the index of any proposal
that has been decided (#3470); termination decides them all at once
(EP-08-004).  A record for an embargo the register has not recorded yet stays
(EP-09-007).
"""

import pytest

from test.support.embargo_register import activate, propose, reject, terminate
from vultron.core.models.case import VulnerabilityCase
from vultron.core.states.em import EM
from vultron.errors import VultronInvalidStateTransitionError

_OWNER = "https://example.org/actors/owner"
_E0 = "https://example.org/cases/1/embargo_events/0"
_E1 = "https://example.org/cases/1/embargo_events/1"
_E2 = "https://example.org/cases/1/embargo_events/2"
_P1 = "https://example.org/cases/1/embargo_proposals/1"
_P2 = "https://example.org/cases/1/embargo_proposals/2"


def _case_with_two_open_proposals() -> VulnerabilityCase:
    case = VulnerabilityCase(name="c", attributed_to=_OWNER)
    propose(case, _E1, _E2)
    case.pending_embargo_proposal_index.update({_E1: _P1, _E2: _P2})
    return case


@pytest.mark.spec("EP-08-003")
def test_rejection_prunes_the_proposal_from_both_records_and_only_that_one():
    case = _case_with_two_open_proposals()

    reject(case, _E1)

    assert case.proposed_embargo_ids == [_E2]
    assert case.pending_embargo_proposal_index == {_E2: _P2}
    assert case.em_state == EM.PROPOSED


@pytest.mark.spec("EP-08-003")
def test_activation_prunes_the_activated_proposal_only():
    case = _case_with_two_open_proposals()

    activate(case, _E1)

    assert case.active_embargo_id == _E1
    assert case.proposed_embargo_ids == [_E2]
    assert case.pending_embargo_proposal_index == {_E2: _P2}


@pytest.mark.spec("EP-08-003")
def test_a_refused_step_changes_neither_record():
    """Deciding an already-decided proposal is refused, and prunes nothing."""
    case = _case_with_two_open_proposals()
    reject(case, _E1)

    with pytest.raises(VultronInvalidStateTransitionError):
        reject(case, _E1)

    assert case.proposed_embargo_ids == [_E2]
    assert case.pending_embargo_proposal_index == {_E2: _P2}


@pytest.mark.spec("EP-09-007")
def test_a_step_keeps_an_index_record_the_register_has_not_recorded_yet():
    """A relayed Invite can be indexed before replay records its proposal.

    The record keeps its place until that proposal is decided, so the
    addressee's own Invite is the one it answers.
    """
    case = VulnerabilityCase(name="c", attributed_to=_OWNER)
    case.pending_embargo_proposal_index[_E1] = _P1  # index only

    activate(case, _E2)

    assert case.proposed_embargo_ids == []
    assert case.pending_embargo_proposal_index == {_E1: _P1}


@pytest.mark.spec("EP-08-003")
def test_a_step_prunes_an_index_record_for_an_already_decided_proposal():
    """An index record written after its proposal was decided is pruned."""
    case = VulnerabilityCase(name="c", attributed_to=_OWNER)
    propose(case, _E1)
    reject(case, _E1)
    case.pending_embargo_proposal_index[_E1] = _P1  # late relay record

    assert not case.proposal_is_undecided(_E1)
    propose(case, _E2)

    assert case.proposed_embargo_ids == [_E2]
    assert case.pending_embargo_proposal_index == {}


@pytest.mark.spec("EP-08-004")
def test_termination_prunes_an_index_record_the_register_never_recorded():
    """After termination nothing can be proposed, so no record survives."""
    case = VulnerabilityCase(name="c", attributed_to=_OWNER)
    activate(case, _E0)
    case.pending_embargo_proposal_index[_E1] = _P1  # index only

    terminate(case)

    assert case.pending_embargo_proposal_index == {}


def test_proposing_another_embargo_keeps_every_open_record():
    case = _case_with_two_open_proposals()

    propose(case, _E0)

    assert case.proposed_embargo_ids == [_E1, _E2, _E0]
    assert case.pending_embargo_proposal_index == {_E1: _P1, _E2: _P2}


@pytest.mark.spec("EP-08-004")
def test_termination_clears_both_records_together():
    """Termination cancels every open proposal; the index leaves with them."""
    case = VulnerabilityCase(name="Open proposals", attributed_to="urn:o")
    activate(case, _E0)
    propose(case, _E1, _E2)
    case.pending_embargo_proposal_index = {_E1: _P1, _E2: _P2}

    terminate(case)

    assert case.em_state == EM.EXITED
    assert case.proposed_embargo_ids == []
    assert case.pending_embargo_proposal_index == {}
