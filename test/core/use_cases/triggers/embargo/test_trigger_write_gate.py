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
"""A trigger writes shared EM state only as the CASE_MANAGER (EP-09-008).

A participant that does not hold ``CVDRole.CASE_MANAGER`` emits its proposal to
the manager, records it in the pending-assertion store, and writes no EM state;
its replica moves when the manager's commit is announced.  Strict ``xfail``
until the trigger-side write gate lands (Task opened from Concern #3918,
ADR-0113 as rewritten 2026-09-30).
"""

from datetime import datetime, timedelta, timezone
from typing import cast

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.core.models.activity import VultronActivity
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.pending_assertion import get_pending_assertion_store
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import PEC
from vultron.core.use_cases.triggers.embargo import SvcProposeEmbargoUseCase
from vultron.core.use_cases.triggers.requests import (
    ProposeEmbargoTriggerRequest,
)
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.case_participant import (
    FinderParticipant,
    VendorParticipant,
)

MANAGER = "https://example.org/actors/case-actor"


def _case_managed_by_someone_else(
    dl: SqliteDataLayer, finder_id: str
) -> VulnerabilityCase:
    """Case at ``EM.NONE`` whose CASE_MANAGER is not the finder."""
    case = VulnerabilityCase(name="Gated trigger case", attributed_to=MANAGER)
    manager = VendorParticipant(
        attributed_to=MANAGER,
        context=case.id_,
        embargo_consent_state=PEC.UNBOUND,
    )
    manager.add_role(CVDRole.CASE_MANAGER)
    finder = FinderParticipant(
        attributed_to=finder_id,
        context=case.id_,
        embargo_consent_state=PEC.UNBOUND,
    )
    case.case_participants = [manager.id_, finder.id_]
    case.actor_participant_index = {
        MANAGER: manager.id_,
        finder_id: finder.id_,
    }
    case.append_case_status(em_state=EM.NONE)
    case.active_embargo = None
    dl.create(case)
    dl.create(manager)
    dl.create(finder)
    return case


@pytest.mark.xfail(
    strict=True,
    reason=(
        "EP-09-008: a non-manager's propose trigger writes EM.PROPOSED to its "
        "own store before the CASE_MANAGER has answered. Tracked by the Task "
        "the #3918 planning PR opened; ADR-0113."
    ),
)
@pytest.mark.spec("EP-09-008")
def test_non_manager_trigger_asks_and_writes_no_em_state(
    finder_actor_and_dl: tuple[as_Service, SqliteDataLayer],
) -> None:
    """Emit to the manager, record the ask, write nothing, declare nothing."""
    finder, finder_dl = finder_actor_and_dl
    case = _case_managed_by_someone_else(finder_dl, finder.id_)
    request = ProposeEmbargoTriggerRequest(
        actor_id=finder.id_,
        case_id=case.id_,
        end_time=datetime.now(tz=timezone.utc) + timedelta(days=7),
    )

    result = SvcProposeEmbargoUseCase(
        finder_dl, request, trigger_activity=TriggerActivityAdapter(finder_dl)
    ).execute()

    updated = cast(VulnerabilityCase, finder_dl.read(case.id_))
    assert updated.current_status.em.state == EM.NONE

    queued = [
        cast(VultronActivity, finder_dl.read(i))
        for i in finder_dl.outbox_list()
    ]
    invites = [a for a in queued if a.type_ == "Invite"]
    assert len(invites) == 1
    assert invites[0].to == [MANAGER]
    assert not any(
        a.type_ == "Add" and "CaseStatus" in str(a.object_) for a in queued
    ), "a non-manager must not declare an EM state it has not been given"

    activity_id = result["activity"]["id"]
    store = get_pending_assertion_store(finder.id_)
    assert store.is_suppressed(
        case.id_, MessageSemantics.INVITE_TO_EMBARGO_ON_CASE.value, activity_id
    )
