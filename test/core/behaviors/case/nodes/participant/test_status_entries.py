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


"""The helpers behind a trigger's checked, unwritten steps (#4295, RSH-08-006).

``context_after_followed`` validates a step as following one a trigger
stored without attaching; ``CommitParticipantStatusEntriesNode`` finds the
case from the status it records when its tree names none.
"""

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.case.nodes.participant.common import (
    ParticipantTransitionContext,
    context_after_followed,
)
from vultron.core.behaviors.case.nodes.participant.status_entries import (
    CommitParticipantStatusEntriesNode,
)
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.dimensions import RmDimension, VfDimension
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.states.cs import CS_pxa, CS_vf
from vultron.core.states.rm import RM
from vultron.errors import (
    VultronBTInternalError,
    VultronNotFoundError,
    VultronValidationError,
)

_CASE = "https://example.org/cases/followed"
_ACTOR = "https://example.org/actors/vendor"


@pytest.fixture
def dl():
    store = SqliteDataLayer("sqlite:///:memory:", actor_id=_ACTOR)
    yield store
    store.close()


def _context() -> ParticipantTransitionContext:
    record = CaseParticipant(
        id_=f"{_CASE}/participants/vendor", attributed_to=_ACTOR, context=_CASE
    )
    return ParticipantTransitionContext(
        participant=record,
        current_rm=RM.ACCEPTED,
        current_vf=CS_vf.vf,
        current_d=None,
        current_pxa=CS_pxa.pxa,
        actor_roles=[],
    )


def _stored(dl, *, actor: str = _ACTOR, case: str = _CASE) -> str:
    status = ParticipantStatus(
        attributed_to=actor,
        context=case,
        rm=RmDimension(state=RM.ACCEPTED),
        vf=VfDimension(state=CS_vf.Vf),
    )
    dl.create(status)
    return status.id_


@pytest.mark.spec("RSH-08-006")
def test_a_followed_step_is_the_baseline(dl):
    context = context_after_followed(dl, _context(), [_stored(dl)])

    assert context.current_vf == CS_vf.Vf


def test_nothing_followed_leaves_the_context(dl):
    context = _context()

    assert context_after_followed(dl, context, None) is context


@pytest.mark.parametrize(
    "owner",
    [
        {"actor": "https://example.org/actors/someone-else"},
        {"case": "https://example.org/cases/another"},
    ],
    ids=["another-actor", "another-case"],
)
def test_a_step_of_another_participant_is_refused(dl, owner):
    with pytest.raises(VultronValidationError):
        context_after_followed(dl, _context(), [_stored(dl, **owner)])


def test_a_followed_step_that_is_not_stored_is_refused(dl):
    with pytest.raises(VultronNotFoundError):
        context_after_followed(dl, _context(), ["urn:uuid:never-stored"])


def test_the_commit_node_finds_the_case_from_the_status(dl):
    node = CommitParticipantStatusEntriesNode(
        subject_actor_id=_ACTOR, case_id=None, status_ids=[_stored(dl)]
    )
    node.datalayer = dl

    assert node._written_case_id() == _CASE


def test_an_id_that_names_no_status_is_a_fault(dl):
    """A written id that reads back as no status names no case to record in."""
    record = _context().participant
    assert isinstance(record, CaseParticipant)
    dl.create(record)
    node = CommitParticipantStatusEntriesNode(
        subject_actor_id=_ACTOR, case_id=None, status_ids=[record.id_]
    )
    node.datalayer = dl

    with pytest.raises(VultronBTInternalError):
        node._written_case_id()
