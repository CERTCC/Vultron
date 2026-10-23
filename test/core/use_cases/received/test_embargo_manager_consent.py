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
"""The manager's and the proposer's consent rows at the proposal commit.

EP-09-002 (#4180): committing a proposal records the proposer's row
``AGREED`` (proposing is consenting, ADR-0093) and, for a CASE_MANAGER that
is itself a stakeholder, its own row too, with no Invite to the manager.
"""

from typing import cast

import pytest

from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.enums.roles import CVDRole
from vultron.wire.as2.factories import em_propose_embargo_activity

from .test_embargo_revision_relay import (
    MANAGER,
    OTHER_A,
    PROPOSER,
    _active_case_with_revision,
    _consent_of,
    _deliver,
    _relayed_invites,
)


def _make_manager_a_stakeholder(dl, case_id: str) -> None:
    """The manager stops owning the case and gains a vendor stake."""
    case = cast(VulnerabilityCase, dl.read(case_id))
    case.attributed_to = PROPOSER
    dl.save(case)
    manager = cast(
        CaseParticipant, dl.read(case.actor_participant_index[MANAGER])
    )
    manager.case_roles = [CVDRole.CASE_MANAGER, CVDRole.VENDOR]
    dl.save(manager)


def _proposal(revision, case_id: str, proposer: str):
    return em_propose_embargo_activity(
        revision,
        context=case_id,
        actor=proposer,
        to=[MANAGER],
        id_=f"{case_id}/embargo_proposals/revision",
    )


@pytest.mark.spec("EP-09-002")
def test_committing_a_proposal_records_the_proposers_row_agreed(
    make_payload,
):
    case_id = "https://example.org/cases/mc-proposer"
    dl, revision = _active_case_with_revision(
        case_id, store_actor=MANAGER, participants=[PROPOSER, OTHER_A]
    )

    _deliver(
        dl,
        _proposal(revision, case_id, PROPOSER),
        make_payload,
        receiving_actor_id=MANAGER,
    )

    assert (
        _consent_of(dl, case_id, PROPOSER, revision.id_)
        == EmbargoConsentState.AGREED
    )
    # The invitee answers for itself; the commit asks, it does not answer.
    assert (
        _consent_of(dl, case_id, OTHER_A, revision.id_)
        == EmbargoConsentState.INVITED
    )


@pytest.mark.spec("EP-09-002")
def test_a_stakeholder_manager_records_its_own_row_with_no_invite(
    make_payload,
):
    case_id = "https://example.org/cases/mc-stakeholder"
    dl, revision = _active_case_with_revision(
        case_id, store_actor=MANAGER, participants=[PROPOSER, OTHER_A]
    )
    _make_manager_a_stakeholder(dl, case_id)

    _deliver(
        dl,
        _proposal(revision, case_id, PROPOSER),
        make_payload,
        receiving_actor_id=MANAGER,
    )

    assert (
        _consent_of(dl, case_id, MANAGER, revision.id_)
        == EmbargoConsentState.AGREED
    )
    assert MANAGER not in [r for a in _relayed_invites(dl) for r in a.to or []]


@pytest.mark.spec("EP-09-002")
def test_a_manager_that_is_the_proposer_is_recorded_agreed(make_payload):
    case_id = "https://example.org/cases/mc-manager-proposer"
    dl, revision = _active_case_with_revision(
        case_id, store_actor=MANAGER, participants=[PROPOSER, OTHER_A]
    )
    _make_manager_a_stakeholder(dl, case_id)

    _deliver(
        dl,
        _proposal(revision, case_id, MANAGER),
        make_payload,
        receiving_actor_id=MANAGER,
    )

    assert (
        _consent_of(dl, case_id, MANAGER, revision.id_)
        == EmbargoConsentState.AGREED
    )
    assert MANAGER not in [r for a in _relayed_invites(dl) for r in a.to or []]


@pytest.mark.spec("EP-09-002")
def test_a_bare_container_manager_records_nothing(make_payload):
    case_id = "https://example.org/cases/mc-container"
    dl, revision = _active_case_with_revision(
        case_id, store_actor=MANAGER, participants=[PROPOSER, OTHER_A]
    )
    case = cast(VulnerabilityCase, dl.read(case_id))
    case.attributed_to = PROPOSER
    dl.save(case)

    _deliver(
        dl,
        _proposal(revision, case_id, PROPOSER),
        make_payload,
        receiving_actor_id=MANAGER,
    )

    # The bare container is never asked, and answers nothing (ADR-0122).
    assert (
        _consent_of(dl, case_id, MANAGER, revision.id_)
        == EmbargoConsentState.UNINVITED
    )
