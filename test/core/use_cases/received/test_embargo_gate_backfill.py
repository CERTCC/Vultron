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
"""Accepting the active embargo backfills withheld ledger entries (CM-10-006).

Strict ``xfail`` until the gate lands: today nothing is withheld, so the
accept fans out only its own new entry and never re-sends an earlier one.
"""

from typing import cast

import pytest

from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.states.em import EM
from vultron.core.use_cases.received.embargo import (
    AcceptInviteToEmbargoOnCaseReceivedUseCase,
)
from vultron.wire.as2.factories import (
    em_accept_embargo_activity,
    em_propose_embargo_activity,
)

from .conftest import make_embargo_case_with_actor

MANAGER_ID = "https://example.org/actors/coordinator"
SIGNATORY_ID = "https://example.org/actors/vendor"
NON_SIGNATORY_ID = "https://example.org/actors/finder"


@pytest.mark.xfail(
    strict=True,
    reason=(
        "CM-10-006: no backfill of withheld ledger entries when the embargo"
        " content gate admits a participant. Tracked in #4042; source #3917."
    ),
)
@pytest.mark.spec("CM-10-006")
def test_accepting_the_active_embargo_backfills_withheld_entries(
    make_payload,
) -> None:
    case_id = "https://example.org/cases/fanout-backfill"
    dl, _, case, embargo = make_embargo_case_with_actor(
        case_id,
        MANAGER_ID,
        extra_participants=[SIGNATORY_ID, NON_SIGNATORY_ID],
        case_manager_actor_id=MANAGER_ID,
    )
    stored = cast(VulnerabilityCase, dl.read(case.id_))
    stored.current_status.em.state = EM.ACTIVE
    object.__setattr__(stored, "active_embargo", embargo.id_)
    dl.save(stored)

    invite = em_propose_embargo_activity(
        embargo,
        context=case_id,
        actor=MANAGER_ID,
        id_=f"{case_id}/embargo_proposals/1",
    )
    dl.create(invite)

    def _receive_accept(actor_id: str) -> None:
        accept = em_accept_embargo_activity(
            invite, context=case_id, actor=actor_id
        )
        AcceptInviteToEmbargoOnCaseReceivedUseCase(
            dl,
            make_payload(accept, receiving_actor_id=MANAGER_ID),
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

    # A real commit made while the finder is outside the gate: under
    # CM-10-005 it is never sent to them.  Draining the outbox models that.
    _receive_accept(SIGNATORY_ID)
    withheld = [
        e
        for e in dl.list_objects("CaseLedgerEntry")
        if isinstance(e, CaseLedgerEntry) and e.case_id == case_id
    ]
    assert len(withheld) == 1
    while dl.outbox_pop() is not None:
        pass

    _receive_accept(NON_SIGNATORY_ID)

    backfilled = [
        activity
        for activity in (dl.read(i) for i in dl.outbox_list())
        if activity is not None
        and getattr(activity, "type_", None) == "Announce"
        and NON_SIGNATORY_ID in (getattr(activity, "to", None) or [])
        and getattr(getattr(activity, "object_", None), "id_", None)
        == withheld[0].id_
    ]
    assert backfilled, (
        "the entry withheld under the embargo gate must be backfilled once"
        " the participant accepts the active embargo"
    )
